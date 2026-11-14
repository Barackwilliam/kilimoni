"""
WhatsApp Webhook - Inapokea na kutuma messages
"""
import json
import requests
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from bot.engine import process_message, is_duplicate_message

logger = logging.getLogger(__name__)


def send_whatsapp_message(to: str, message: str) -> bool:
    """Tuma ujumbe kwa mkulima kupitia WhatsApp Business API"""
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp API credentials hazikuwekwa. Ujumbe haujatumwa.")
        return False

    url = settings.WHATSAPP_API_URL
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": message, "preview_url": False},
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Ujumbe umetumwa kwa {to}")
        return True
    except requests.RequestException as e:
        # Meta huweka sababu halisi ndani ya response body — bila hii
        # utaona '400 Bad Request' tu bila kujua tatizo ni nini.
        body = ''
        if getattr(e, 'response', None) is not None:
            body = e.response.text[:500]
        logger.error(f"Imeshindwa kutuma ujumbe kwa {to}: {e} | Meta alisema: {body}")
        return False


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    """WhatsApp webhook endpoint"""

    # ── GET: Verification handshake na Meta ──
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            logger.info("WhatsApp webhook imethhibitishwa.")
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)

    # ── POST: Incoming messages ──
    try:
        data = json.loads(request.body)
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return JsonResponse({"status": "no_message"}, status=200)

        for msg in messages:
            msg_type = msg.get("type", "")
            phone_number = msg.get("from", "")
            message_id = msg.get("id", "")

            # Meta hurudia webhook kama haikupata 200 haraka —
            # bila ukaguzi huu mkulima angepokea jibu mara mbili.
            if message_id and is_duplicate_message(message_id):
                logger.info(f"Ujumbe {message_id} umeshashughulikiwa — unarukwa.")
                continue

            if msg_type == "text":
                raw_text = msg.get("text", {}).get("body", "").strip()
                if raw_text and phone_number:
                    logger.info(f"Ujumbe umepokelewa kutoka {phone_number}: {raw_text[:50]}")
                    response_text = process_message(phone_number, raw_text, message_id=message_id)
                    send_whatsapp_message(phone_number, response_text)

            elif msg_type in ["audio", "image", "document"]:
                # Jibu kwa ujumbe ambao si maandishi
                reply = (
                    "Samahani, kwa sasa ninaweza kushughulikia maandishi tu. 📝\n"
                    "Tafadhali andika swali lako kwa maneno."
                )
                send_whatsapp_message(phone_number, reply)

        return JsonResponse({"status": "ok"}, status=200)

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({"status": "error"}, status=200)






# ============================================================
# BAILEYS WHATSAPP BRIDGE
# ============================================================

@csrf_exempt
@require_http_methods(["POST"])
def baileys_incoming(request):
    """
    Inapokea ujumbe kutoka Baileys na kuupitisha
    kwenye chatbot engine ya Kilimoni.
    """

    # --------------------------------------------------------
    # SECURITY CHECK
    # --------------------------------------------------------

    bridge_key = request.headers.get("X-Bridge-Key", "")

    expected_key = getattr(
        settings,
        "BAILEYS_BRIDGE_KEY",
        ""
    )

    if not expected_key or bridge_key != expected_key:
        logger.warning(
            "Baileys bridge unauthorized request."
        )

        return JsonResponse(
            {
                "success": False,
                "error": "Unauthorized"
            },
            status=401
        )


    # --------------------------------------------------------
    # READ REQUEST
    # --------------------------------------------------------

    try:

        data = json.loads(request.body)

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON"
            },
            status=400
        )


    # --------------------------------------------------------
    # GET DATA
    # --------------------------------------------------------

    phone = str(
        data.get("phone", "")
    ).strip()

    message = str(
        data.get("message", "")
    ).strip()

    message_id = str(
        data.get("message_id", "")
    ).strip()


    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not phone:

        return JsonResponse(
            {
                "success": False,
                "error": "Phone number is required"
            },
            status=400
        )


    if not message:

        return JsonResponse(
            {
                "success": False,
                "error": "Message is required"
            },
            status=400
        )


    # --------------------------------------------------------
    # DUPLICATE MESSAGE CHECK
    # --------------------------------------------------------

    if message_id:

        try:

            if is_duplicate_message(message_id):

                logger.info(
                    f"Baileys duplicate message ignored: {message_id}"
                )

                return JsonResponse(
                    {
                        "success": True,
                        "reply": ""
                    }
                )

        except Exception as e:

            logger.warning(
                f"Duplicate check failed: {e}"
            )


    # --------------------------------------------------------
    # PROCESS WITH KILIMONI AI ENGINE
    # --------------------------------------------------------

    try:

        logger.info(
            f"Baileys message from {phone}: {message[:100]}"
        )

        response_text = process_message(
            phone,
            message,
            message_id=message_id
        )


        # ----------------------------------------------------
        # RETURN RESPONSE TO BAILEYS
        # ----------------------------------------------------

        return JsonResponse(
            {
                "success": True,
                "reply": str(response_text)
            }
        )


    except Exception as e:

        logger.exception(
            "Baileys message processing error"
        )

        return JsonResponse(
            {
                "success": False,
                "error": str(e)
            },
            status=500
        )


# ============================================================
# BRIDGE MPYA (nakala ya JamiiTek) — haisubiri jibu
# ============================================================
# Bridge inatuma ujumbe hapa; tunajibu 200 mara moja na kushughulikia
# kwenye thread ya nyuma, kisha tunatuma jibu kupitia POST /send ya
# bridge. Hivyo worker wa gunicorn hashikiliwi na AI, na wakulima wengi
# wanaoandika pamoja hawapangi foleni.
#
# Njia ya zamani (/webhook/baileys/incoming/, jibu ndani ya request)
# inabaki hadi bridge ya zamani ibadilishwe kwenye Render.

import threading

from . import bridge as wa_bridge

NON_TEXT_REPLIES = {
    'image': ("📷 Nimepokea picha yako, lakini bado siwezi kusoma picha.\n\n"
              "Tafadhali nieleze kwa maneno unachokiona shambani. Mfano: "
              "_majani ya mahindi yana matundu na kuna kama vumbi la mbao_"),
    'video': ("🎥 Nimepokea video, lakini bado siwezi kuitazama.\n\n"
              "Tafadhali nieleze kwa maneno tatizo unaloliona shambani."),
    'audio': ("🎤 Nimepokea ujumbe wa sauti, lakini kwa sasa ninasoma maandishi tu.\n\n"
              "Tafadhali andika swali lako, nami nitakusaidia."),
    'document': "📄 Nimepokea faili, lakini siwezi kulifungua. Tafadhali niandikie swali lako kwa maneno.",
    'location': ("📍 Nimepokea location yako, lakini bado siwezi kuisoma.\n\n"
                 "Tafadhali niandikie jina la kata, wilaya au mkoa wako. Mfano: _niko Kongwa, Dodoma_"),
    'sticker': "🙂 Karibu! Niandikie swali lako la kilimo, nami nitakusaidia.",
}

_guard = threading.Lock()
_scheduled = set()      # phone zenye mfanyakazi kwenye process hii
_executor = None
_last_sweep = [0.0]
SWEEP_EVERY = 60        # sekunde: kuokota jumbe zilizobaki (mf. baada ya deploy)
STUCK_AFTER = 20        # sekunde: ujumbe wa 'pending' uliosubiri zaidi ya hapa unaokotwa


def _pool():
    """
    Wafanyakazi wachache, si thread kwa kila ujumbe: kila mfanyakazi ana
    muunganisho wa database, na Supabase ina kikomo cha connections.
    """
    global _executor
    if _executor is None:
        from concurrent.futures import ThreadPoolExecutor
        _executor = ThreadPoolExecutor(max_workers=getattr(settings, 'BRIDGE_WORKERS', 4),
                                       thread_name_prefix='bridge')
    return _executor


class _FarmerLock:
    """
    Mkulima mmoja → mfanyakazi mmoja kwa wakati, hata kati ya workers wa
    gunicorn (Postgres advisory lock). SQLite: process moja, haihitajiki.
    """

    def __init__(self, phone):
        import zlib
        self.key = zlib.crc32(f"kilimoni-farmer:{phone}".encode())
        self.held = False

    def __enter__(self):
        from django.db import connection
        if connection.vendor == 'postgresql':
            with connection.cursor() as c:
                c.execute("SELECT pg_advisory_lock(%s)", [self.key])
            self.held = True
        return self

    def __exit__(self, *exc):
        if self.held:
            from django.db import connection
            try:
                with connection.cursor() as c:
                    c.execute("SELECT pg_advisory_unlock(%s)", [self.key])
            except Exception:
                pass
        return False


def handle_bridge_message(payload):
    """Ujumbe mmoja: injini ya Kilimoni → jibu → bridge /send. Inarudisha kosa (str) au ''."""
    phone = str(payload.get('phone', '')).strip()
    jid = str(payload.get('jid', '')).strip()
    text = str(payload.get('text', '') or '').strip()
    msg_type = payload.get('msg_type') or 'text'
    message_id = str(payload.get('message_id', '')).strip()
    try:
        if message_id and is_duplicate_message(message_id):
            # Injini ilishamaliza (mf. worker alikufa kabla ya kutuma): tuma jibu
            # lililohifadhiwa badala ya kuendesha injini tena.
            reply = _stored_reply(message_id)
            if reply:
                logger.info(f"Bridge: jibu lililohifadhiwa linatumwa tena: {message_id}")
                res = wa_bridge.send_text(phone, reply, jid=jid)
                return '' if res.get('success') else f"kutuma: {res.get('error', '')}"[:300]
            logger.info(f"Bridge: ujumbe uliorudiwa umerukwa: {message_id}")
            return ''
        if text:
            reply = process_message(phone, text, whatsapp_type=msg_type, message_id=message_id)
        else:
            reply = NON_TEXT_REPLIES.get(msg_type, NON_TEXT_REPLIES['document'])
        if reply:
            res = wa_bridge.send_text(phone, str(reply), jid=jid)
            if not res.get('success'):
                return f"kutuma: {res.get('error', '')}"[:300]
        return ''
    except Exception as e:
        logger.exception(f"Bridge: kushughulikia ujumbe wa {phone} kumeshindwa")
        return f"{e.__class__.__name__}: {e}"[:300]


def _stored_reply(message_id):
    """Jibu (outbound) lililohifadhiwa mara baada ya ujumbe huu wa mkulima."""
    from bot.models import Conversation
    inbound = (Conversation.objects.filter(whatsapp_message_id=message_id, message_direction='inbound')
               .order_by('id').first())
    if inbound is None:
        return ''
    out = (Conversation.objects.filter(user_id=inbound.user_id, message_direction='outbound', id__gt=inbound.id)
           .order_by('id').first())
    return out.raw_message if out else ''


def process_phone(phone):
    """Shughulikia jumbe zote zinazosubiri za mkulima huyu, kwa mpangilio ziliofika."""
    from django.utils import timezone
    from .models import IncomingMessage
    with _FarmerLock(phone):
        while True:
            row = IncomingMessage.objects.filter(phone=phone, status='pending').order_by('id').first()
            if row is None:
                return
            err = handle_bridge_message(row.payload)
            row.attempts += 1
            row.status = 'failed' if err else 'done'
            row.error = err
            row.processed_at = timezone.now()
            row.save(update_fields=['attempts', 'status', 'error', 'processed_at'])


def _drain(phone):
    from django.db import connection
    from .models import IncomingMessage
    try:
        while True:
            process_phone(phone)
            with _guard:
                _scheduled.discard(phone)
            # Ujumbe ulioingia kati ya kumaliza na kuachia: endelea nao
            if not IncomingMessage.objects.filter(phone=phone, status='pending').exists():
                return
            with _guard:
                if phone in _scheduled:
                    return              # mwingine ameshauchukua
                _scheduled.add(phone)
    except Exception:
        logger.exception(f"Bridge: foleni ya {phone} imeshindwa")
        with _guard:
            _scheduled.discard(phone)
    finally:
        connection.close()              # muunganisho wa thread hii


def schedule(phone):
    with _guard:
        if phone in _scheduled:
            return
        _scheduled.add(phone)
    _pool().submit(_drain, phone)


def _sweep():
    """
    Kila dakika: okota jumbe zilizobaki 'pending' (mf. Django ilizimwa katikati
    ya kazi) na futa kumbukumbu za zamani za foleni.
    """
    import time
    from datetime import timedelta
    from django.utils import timezone
    from .models import IncomingMessage
    now = time.time()
    with _guard:
        if now - _last_sweep[0] < SWEEP_EVERY:
            return
        _last_sweep[0] = now
    try:
        cutoff = timezone.now() - timedelta(seconds=STUCK_AFTER)
        phones = (IncomingMessage.objects.filter(status='pending', received_at__lt=cutoff)
                  .values_list('phone', flat=True).distinct()[:200])
        for phone in phones:
            schedule(phone)
        IncomingMessage.objects.filter(status='done', received_at__lt=timezone.now() - timedelta(days=7)).delete()
    except Exception:
        logger.exception("Bridge: sweep ya foleni imeshindwa")


@csrf_exempt
@require_http_methods(["POST"])
def bridge_incoming(request):
    """Bridge → Django. Inajibu mara moja, inashughulikia nyuma."""
    if not wa_bridge.authorized(request):
        logger.warning("Bridge: ombi lisilo na ufunguo sahihi.")
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=401)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON si sahihi"}, status=400)
    if not isinstance(payload, dict) or not str(payload.get('phone', '')).strip():
        return JsonResponse({"success": False, "error": "phone inahitajika"}, status=400)
    if payload.get('session') and payload['session'] != wa_bridge.session_name():
        return JsonResponse({"success": False, "error": "Session haijulikani"}, status=404)

    # Hifadhi kwanza (foleni ya kudumu) — ID ya ujumbe ni ya kipekee: marudio yanakataliwa hapa
    from django.db import IntegrityError, transaction
    from .models import IncomingMessage
    phone = str(payload['phone']).strip()
    message_id = str(payload.get('message_id', '')).strip() or None
    try:
        with transaction.atomic():
            IncomingMessage.objects.create(phone=phone, message_id=message_id, payload=payload)
    except IntegrityError:
        return JsonResponse({"success": True, "skipped": "duplicate"})

    if getattr(settings, 'BRIDGE_INLINE', False):
        process_phone(phone)
    else:
        schedule(phone)
        _sweep()
    return JsonResponse({"success": True})


@csrf_exempt
def bridge_sessions(request):
    """Bridge ikianza inauliza: 'session zipi niziinue?' — Kilimoni ina moja."""
    if not wa_bridge.authorized(request):
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=401)
    return JsonResponse({"success": True, "sessions": [wa_bridge.session_name()]})


def healthz(request):
    """
    Kwa UptimeRobot/Render: inaiweka service hai (plan ya bure inalala bila
    maombi ya HTTP, na jumbe za WhatsApp haziwezi kuiamsha), na inaokota
    jumbe zilizokwama hata kama hakuna ujumbe mpya unaoingia.
    Haihitaji kuingia; haitoi taarifa za siri.
    """
    try:
        _sweep()
    except Exception:
        pass
    bridge_ok = None
    if wa_bridge.is_configured():
        h = wa_bridge.health(timeout=2)
        bridge_ok = bool(h.get('success'))
    import os
    # Toleo lililoko live (Render inaweka RENDER_GIT_COMMIT): wanaojaribu wajue
    # kama wanajaribu marekebisho ya karibuni.
    version = (os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GIT_COMMIT') or '')[:7]
    return JsonResponse({'ok': True, 'bridge': bridge_ok, 'version': version})
