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

from bot.engine import process_message, is_duplicate_message

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

    # Puuza group chats — bot ni kwa mazungumzo binafsi tu.
    # ("...@g.us" ni group; kujibu humo kunaweza kusababisha spam na ban)
    if chat_id.endswith("@g.us"):
        return JsonResponse({"status": "group_ignored"}, status=200)

    message_id = data.get("idMessage", "")

    # GreenAPI hurudia webhook kama haikupata 200 haraka —
    # bila ukaguzi huu mkulima angepokea jibu lile lile mara kadhaa.
    if message_id and is_duplicate_message(message_id):
        logger.info(f"[GreenAPI] Ujumbe {message_id} umeshashughulikiwa — unarukwa.")
        return JsonResponse({"status": "duplicate"}, status=200)

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
        reply = process_message(phone_number, raw_text, message_id=message_id)
    except Exception as e:
        logger.exception(f"[GreenAPI] Bot engine error: {e}")
        reply = "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye. 🙏"

    send_greenapi_message(chat_id, reply)
    return JsonResponse({"status": "ok"}, status=200)