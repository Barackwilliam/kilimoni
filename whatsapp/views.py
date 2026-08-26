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
