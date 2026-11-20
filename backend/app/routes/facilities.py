from flask import Blueprint, render_template, request, abort
from sqlalchemy import select
from app.extensions import db
from app.models.health_facility import HealthFacility

facilities_bp = Blueprint("facilities", __name__, url_prefix="/facilities")

FACILITY_TYPE_LABELS = {
    "PUSKESMAS": "Puskesmas",
    "CLINIC": "Klinik",
    "HOSPITAL": "Rumah Sakit",
    "DENTAL_CLINIC": "Klinik Gigi",
    "OTHER": "Lainnya",
}


@facilities_bp.route("")
def list_facilities():
    return render_template("public/facilities/list.html", show_facility_details=True)


@facilities_bp.route("/<int:facility_id>")
def detail_facility(facility_id):
    facility = db.session.execute(
        select(HealthFacility).filter_by(id=facility_id, is_active=True)
    ).scalar_one_or_none()

    if not facility:
        abort(404)

    map_facility = None
    if facility.latitude is not None and facility.longitude is not None:
        map_facility = {
            "id": facility.id,
            "name": facility.name,
            "code": facility.facility_code,
            "type_label": FACILITY_TYPE_LABELS.get(facility.facility_type, facility.facility_type),
            "address": facility.address or "",
            "city": facility.city or "",
            "phone": facility.phone or "-",
            "lat": float(facility.latitude),
            "lng": float(facility.longitude),
        }

    return render_template(
        "public/facilities/detail.html",
        facility=facility,
        type_label=FACILITY_TYPE_LABELS.get(facility.facility_type, facility.facility_type),
        map_facility=map_facility,
    )


@facilities_bp.get("/mapbox-search")
def mapbox_search():
    from flask import jsonify
    from app.services.mapbox_service import search, MapboxError
    try:
        result = search(query=request.args.get('query', '').strip(),
                        city=request.args.get('city', 'Lamongan').strip(),
                        facility_type=request.args.get('facility_type', 'HOSPITAL'),
                        lat=request.args.get('lat'), lng=request.args.get('lng'))
        response = jsonify(result)
    except MapboxError as error:
        response = jsonify(error=str(error))
        response.status_code = error.status
        if error.status == 429:
            response.headers['Retry-After'] = '60'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'strict-origin'
    return response
