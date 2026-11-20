"""Bounded provider telemetry; never stores chat, credentials or coordinates."""
import logging
import time
import uuid
from threading import Lock
from flask import current_app

logger = logging.getLogger(__name__)
LOCK = Lock()
LABELS = {'active': 'AI AKTIF', 'basic': 'MODE BANTUAN DASAR',
          'unavailable': 'AI TIDAK TERSEDIA', 'unknown': 'MEMERIKSA — belum ada respons terverifikasi'}


def error_category(error):
    code = getattr(error, 'status_code', getattr(error, 'code', None))
    name = type(error).__name__.lower()
    if code == 401: return 'AUTHENTICATION_ERROR'
    if code == 403: return 'AUTHENTICATION_ERROR'
    if code == 404: return 'MODEL_NOT_FOUND'
    if code == 429: return 'RATE_LIMIT'
    if isinstance(code, int) and 500 <= code <= 599: return 'CONNECTION_ERROR'
    if code == 400: return 'CONFIGURATION_ERROR'
    if 'timeout' in name or isinstance(error, TimeoutError): return 'PROVIDER_TIMEOUT'
    if 'connect' in name or 'urlerror' in name or isinstance(error, ConnectionError): return 'CONNECTION_ERROR'
    if isinstance(error, (ValueError, KeyError, AttributeError, TypeError)): return 'INVALID_RESPONSE'
    if isinstance(error, ImportError): return 'CONFIGURATION_ERROR'
    return 'UNKNOWN_PROVIDER_ERROR'


def status(provider=None):
    from app.services.ai_service import get_ai_provider, FallbackAIProvider
    provider = provider or get_ai_provider()
    state = current_app.extensions.get('assistant_health', {})
    configured = not isinstance(provider, FallbackAIProvider)
    valid = state.get('expires', 0) > time.monotonic() and state.get('provider') == (type(provider).__name__, getattr(provider, 'model', ''))
    key = 'basic' if not configured else state.get('state', 'unknown') if valid else 'unknown'
    return {'state': key, 'label': LABELS[key], 'checked': valid,
            'ttl_seconds': 60, 'configured': configured}


def record(provider, success):
    current_app.extensions['assistant_health'] = {
        'state': 'active' if success else 'unavailable', 'expires': time.monotonic()+60,
        'provider': (type(provider).__name__, getattr(provider, 'model', ''))}


def generate(provider, message, intent, context):
    from app.services.ai_service import FallbackAIProvider
    if isinstance(provider, FallbackAIProvider):
        return provider.generate_response(message, intent, context), 'fallback'
    start = time.monotonic()
    request_id = uuid.uuid4().hex
    for attempt in range(2):
        provider.last_error = None
        try:
            answer = provider.generate_response(message, intent, context)
            if not isinstance(answer, str) or not answer.strip() or len(answer)>12000:
                raise ValueError('Invalid response')
            category = getattr(provider, 'last_error', None)
        except Exception as error:
            category = error_category(error)
        if not category:
            record(provider, True)
            logger.info('assistant request_id=%s provider=%s duration=%.2f status=success', request_id, type(provider).__name__, time.monotonic()-start)
            return answer, 'ai'
        logger.warning('assistant request_id=%s provider=%s duration=%.2f category=%s attempt=%s', request_id, type(provider).__name__, time.monotonic()-start, category, attempt+1)
        # Retry brief connection/rate failures only; never repeat slow timeouts.
        if attempt == 0 and category in {'CONNECTION_ERROR', 'RATE_LIMIT'}:
            time.sleep(0.25 * 2**attempt)
            continue
        break
    record(provider, False)
    return FallbackAIProvider().generate_response(message, intent, context), 'fallback'
