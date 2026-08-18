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
from bot.engine import process_message

logger = logging.getLogger(__name__)


def send_whatsapp_message(to: str, message: str) -> bool:
    """Tuma ujumbe kwa mkulima kupitia WhatsApp Business API"""
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp API credentials hazikuwekwa. Ujumbe haujatumwa.")
        return False

    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
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
        logger.error(f"Imeshindwa kutuma ujumbe kwa {to}: {e}")
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

            if msg_type == "text":
                raw_text = msg.get("text", {}).get("body", "").strip()
                if raw_text and phone_number:
                    logger.info(f"Ujumbe umepokelewa kutoka {phone_number}: {raw_text[:50]}")
                    response_text = process_message(phone_number, raw_text)
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


















"""
Green API Webhook - Kwa TESTING tu (QR scan, namba yako mwenyewe)
Weka file hii kama: whatsapp/greenapi_views.py

⚠️ Tumia SIM ya majaribio, si namba kuu ya biashara (hatari ya ban).
Production itatumia Meta webhook iliyopo tayari (views.py).
"""
import json
import logging
import requests

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from bot.engine import process_message

logger = logging.getLogger(__name__)


def send_greenapi_message(chat_id: str, message: str) -> bool:
    """Tuma jibu kupitia Green API"""
    url = (
        f"{settings.GREENAPI_URL}/waInstance{settings.GREENAPI_INSTANCE_ID}"
        f"/sendMessage/{settings.GREENAPI_TOKEN}"
    )
    try:
        r = requests.post(
            url,
            json={"chatId": chat_id, "message": message},
            timeout=15,
        )
        r.raise_for_status()
        logger.info(f"[GreenAPI] Jibu limetumwa kwa {chat_id}")
        return True
    except requests.RequestException as e:
        logger.error(f"[GreenAPI] Imeshindwa kutuma: {e}")
        return False


@csrf_exempt
@require_http_methods(["POST"])
def greenapi_webhook(request):
    """Inapokea notifications kutoka Green API"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "bad_json"}, status=200)

    # Tunashughulikia incoming messages tu
    if data.get("typeWebhook") != "incomingMessageReceived":
        return JsonResponse({"status": "ignored"}, status=200)

    sender_data = data.get("senderData", {})
    chat_id = sender_data.get("chatId", "")          # "255712345678@c.us"
    phone_number = chat_id.split("@")[0]

    msg_data = data.get("messageData", {})
    msg_type = msg_data.get("typeMessage", "")

    # Text ya kawaida au extended (reply/link preview)
    if msg_type == "textMessage":
        raw_text = msg_data.get("textMessageData", {}).get("textMessage", "").strip()
    elif msg_type == "extendedTextMessage":
        raw_text = msg_data.get("extendedTextMessageData", {}).get("text", "").strip()
    else:
        send_greenapi_message(
            chat_id,
            "Samahani, kwa sasa ninaweza kushughulikia maandishi tu. 📝\n"
            "Tafadhali andika swali lako kwa maneno.",
        )
        return JsonResponse({"status": "non_text"}, status=200)

    if not raw_text or not phone_number:
        return JsonResponse({"status": "empty"}, status=200)

    logger.info(f"[GreenAPI] Ujumbe kutoka {phone_number}: {raw_text[:50]}")

    try:
        reply = process_message(phone_number, raw_text)
    except Exception as e:
        logger.error(f"[GreenAPI] Bot engine error: {e}")
        reply = "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye. 🙏"

    send_greenapi_message(chat_id, reply)
    return JsonResponse({"status": "ok"}, status=200)