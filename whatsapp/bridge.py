"""
Mteja wa Bridge — Django → Baileys (nakala ya mfumo wa JamiiTek)
================================================================

Bridge ya Node (whatsapp_bridge/) ni injini tu: inapokea ujumbe wa WhatsApp,
inautuma Django, na inatuma chochote Django inachoiambia. Haisubiri jibu.

  1. WhatsApp → bridge → POST /webhook/bridge/incoming/  (Django: 200 mara moja)
  2. Django → thread ya nyuma: process_message (injini ya Kilimoni)
  3. Django → POST {BRIDGE_URL}/send  {session, jid, text}
  4. bridge → WhatsApp

Kila mwito hapa haurushi exception — unarudisha {'success': False, 'error': …}.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('whatsapp.bridge')

TIMEOUT = 15


def _base_url():
    return (getattr(settings, 'BRIDGE_URL', '') or '').rstrip('/')


def _key():
    return getattr(settings, 'BRIDGE_API_KEY', '') or ''


def session_name():
    return getattr(settings, 'BAILEYS_SESSION', '') or 'kilimoni'


def is_configured():
    return bool(_base_url() and _key())


def authorized(request):
    key = _key()
    return bool(key) and request.headers.get('X-Bridge-Key', '') == key


def _request(method, path, **kwargs):
    if not is_configured():
        return {'success': False, 'error': 'BRIDGE_URL au BRIDGE_API_KEY haijawekwa'}
    url = f"{_base_url()}{path}"
    headers = {'X-Bridge-Key': _key(), 'Content-Type': 'application/json'}
    try:
        resp = requests.request(method, url, headers=headers, timeout=kwargs.pop('timeout', TIMEOUT), **kwargs)
        try:
            data = resp.json()
        except ValueError:
            return {'success': False, 'error': f'jibu si JSON ({resp.status_code})'}
        if not isinstance(data, dict):
            return {'success': False, 'error': 'jibu si sahihi'}
        if resp.status_code >= 400 and 'error' not in data:
            data['error'] = f'HTTP {resp.status_code}'
        data.setdefault('success', resp.status_code < 400)
        return data
    except requests.Timeout:
        return {'success': False, 'error': 'bridge haijajibu kwa wakati (huenda inaamka)'}
    except requests.RequestException as e:
        return {'success': False, 'error': f'bridge haifikiki: {e.__class__.__name__}'}


# ─────────────────────────── Udhibiti wa session ───────────────────────────

def health(timeout=8):
    return _request('GET', '/health', timeout=timeout)


def status(timeout=TIMEOUT):
    return _request('GET', f'/sessions/{session_name()}', timeout=timeout)


def debug(timeout=TIMEOUT):
    return _request('GET', f'/sessions/{session_name()}/debug', timeout=timeout)


def qr():
    return _request('GET', f'/sessions/{session_name()}/qr', timeout=20)


def start():
    return _request('POST', f'/sessions/{session_name()}/start', timeout=40)


def restart():
    return _request('POST', f'/sessions/{session_name()}/restart', timeout=40)


def stop():
    return _request('POST', f'/sessions/{session_name()}/stop', timeout=20)


def logout():
    """Inafuta auth — namba itahitaji kuscan QR upya."""
    return _request('POST', f'/sessions/{session_name()}/logout', timeout=40)


def ping(to, text=''):
    return _request('POST', f'/sessions/{session_name()}/ping',
                    json={'to': to, 'text': text or 'Jaribio la bridge ya Kilimoni AI.'}, timeout=25)


def prune(days=30):
    return _request('POST', '/prune', json={'days': days}, timeout=60)


# ─────────────────────────── Kutuma ───────────────────────────

def send_text(to, text, jid=''):
    """
    `jid` (tuliyoipokea) inatangulia `to`: kwa LID (tarakimu 15, '@lid') JID
    haiwezi kujengwa upya kutoka tarakimu, na jibu lingepotea kimya.
    """
    payload = {'session': session_name(), 'to': to, 'text': str(text)}
    if jid:
        payload['jid'] = jid
    data = _request('POST', '/send', json=payload)
    if not data.get('success'):
        logger.error('Bridge: kutuma kwa %s kumeshindwa — %s', jid or to, data.get('error'))
    return data


def mark_read(jid, message_id):
    if not (jid and message_id):
        return {'success': False}
    return _request('POST', '/read', json={'session': session_name(), 'jid': jid, 'message_id': message_id},
                    timeout=8)
