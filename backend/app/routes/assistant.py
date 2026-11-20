import logging
from flask import abort, make_response
from flask_login import current_user
from sqlalchemy import select
from app.extensions import db
from app.models.chat_turn import ChatTurn
from flask import Blueprint, render_template, request, jsonify, session, current_app
import time
import secrets
from app.services.assistant_runtime import status, LOCK
from app.services.assistant_service import process_assistant_chat, process_location_recommendation

logger = logging.getLogger(__name__)

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")


@assistant_bp.route('/scan', methods=['POST'])
@assistant_bp.route('/scan/correct', methods=['POST'])
@assistant_bp.route('/scan/confirm', methods=['POST'])
def scan_api():
    from app.services import medicine_scan as scan
    from werkzeug.exceptions import RequestEntityTooLarge
    try:
        if request.path.endswith('/scan'):
            upload = request.files.get('image')
            if upload is None:
                raise scan.ScanError('Pilih foto kemasan terlebih dahulu.')
            result = scan.start(upload, request.form.get('previous_scan_id'))
        else:
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                raise scan.ScanError('Permintaan harus berupa objek JSON.')
            result = scan.confirm(data) if request.path.endswith('/confirm') else scan.update(data)
        return jsonify(result)
    except scan.ScanError as error:
        return jsonify(success=False, message=error.message), error.status
    except RequestEntityTooLarge:
        return jsonify(success=False, message='Berkas terlalu besar. Kecilkan gambar sesuai batas upload aplikasi.'), 413


@assistant_bp.before_request
def rate_protection():
    if request.method != 'POST' or request.path not in {'/assistant/chat', '/assistant/location'}:
        return None
    token = session.get('assistant_rate_id')
    if not token:
        token = secrets.token_hex(16)
        session['assistant_rate_id'] = token
    now = time.monotonic()
    with LOCK:
        buckets = current_app.extensions.setdefault('assistant_rate', {})
        for key in list(buckets):
            if buckets[key][0] < now - 60: del buckets[key]
        start, count = buckets.get(token, (now, 0))
        if count >= 30 or (token not in buckets and len(buckets) >= 5000):
            return jsonify(success=False, message='Terlalu banyak pesan. Tunggu sebentar sebelum mencoba lagi.'), 429
        buckets[token] = (start, count+1)


@assistant_bp.route('/status')
def provider_status():
    # Cached observations only: opening a page never spends a generation request.
    return jsonify(status())


@assistant_bp.route("", methods=["GET"])
def chat_page():
    """
    Render the dedicated Asisten SehatWarga chat interface.
    Available to both public and authenticated citizens.
    """
    threads = []
    turns = []
    thread = request.args.get("thread")
    if current_user.is_authenticated:
        owned = select(ChatTurn).where(ChatTurn.user_id == current_user.id)
        threads = db.session.scalars(owned.where(ChatTurn.first_turn.is_(True)).order_by(ChatTurn.id.desc())).all()
        if thread:
            turns = db.session.scalars(owned.where(ChatTurn.thread == thread).order_by(ChatTurn.id)).all()
            if not turns:
                abort(404)
    elif thread:
        abort(404)
    response = make_response(render_template("assistant/chat.html", threads=threads, thread=thread,
        transcript=[{"question": turn.question, "answer": turn.answer} for turn in turns]))
    response.headers["Cache-Control"] = "private, no-store"
    return response


@assistant_bp.route("/chat", methods=["POST"])
def chat_api():
    """
    API endpoint for conversation with Asisten SehatWarga.
    Accepts JSON: { message: str, user_location?: { latitude, longitude }, conversation_history?: list }
    Returns JSON response with intent, answer, and optional facility recommendations.
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request body harus berupa JSON.",
            "message": "Permintaan tidak valid.",
        }), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Body JSON harus berupa objek."}), 400
    message = data.get("message", "")
    user_location = data.get("user_location")
    conversation_history = data.get("conversation_history")

    thread = data.get("thread")
    if thread is not None and (not isinstance(thread, str) or len(thread) != 32 or
            not current_user.is_authenticated or db.session.scalar(select(ChatTurn.id).where(
                ChatTurn.user_id == current_user.id, ChatTurn.thread == thread).limit(1)) is None):
        return jsonify(success=False, message="Percakapan tidak ditemukan."), 404

    result, status = process_assistant_chat(
        message=message,
        user_location=user_location,
        conversation_history=conversation_history,
    )
    if current_user.is_authenticated and status == 200 and result.get("success"):
        active_thread = thread or secrets.token_hex(16)
        db.session.add(ChatTurn(user_id=current_user.id, thread=active_thread, first_turn=thread is None,
                                question=message.strip(), answer=result["message"]))
        db.session.commit()
        result["thread"] = active_thread
    return jsonify(result), status


@assistant_bp.route("/location", methods=["POST"])
def location_api():
    """
    Dedicated endpoint to fetch nearest facilities after browser geolocation consent.
    Accepts JSON: { latitude: float, longitude: float, facility_type?: str }
    Returns JSON with recommended facilities and natural response message.
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request body harus berupa JSON.",
            "message": "Permintaan tidak valid.",
        }), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Body JSON harus berupa objek."}), 400
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    facility_type = data.get("facility_type")

    result, status = process_location_recommendation(
        latitude=latitude,
        longitude=longitude,
        facility_type=facility_type,
    )
    return jsonify(result), status
