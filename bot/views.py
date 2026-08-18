import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from bot.engine import process_message
from bot.models import User


@csrf_exempt
@require_http_methods(["POST"])
def test_message(request):
    """Test endpoint - simulate WhatsApp message bila kutumia API"""
    try:
        data = json.loads(request.body)
        phone = data.get('phone', 'test_255700000000')
        message = data.get('message', '')
        if not message:
            return JsonResponse({'error': 'message inahitajika'}, status=400)
        response = process_message(phone, message)
        return JsonResponse({'response': response, 'phone': phone})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON batili'}, status=400)


@staff_member_required
def user_list(request):
    users = list(User.objects.values('id', 'phone_number', 'region', 'district', 'message_count', 'last_seen_at'))
    return JsonResponse({'users': users})
