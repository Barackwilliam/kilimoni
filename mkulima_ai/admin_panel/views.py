from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from crops.models import Crop, Zone, Intent, AnswerTemplate, FarmerQuestion, Synonym, SeedVariety, CropProfile, LocationMapping
from bot.models import User, Conversation, UnresolvedQuery
from analytics.models import AnalyticsLog, AdminUser, ContentUpdate


# ── Auth ──────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_home')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard_home')
        messages.error(request, 'Jina la mtumiaji au nenosiri si sahihi.')
    return render(request, 'admin_panel/login.html')


def logout_view(request):
    logout(request)
    return redirect('dashboard_login')


# ── Dashboard Home ──────────────────────────────
@login_required
def home(request):
    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)

    total_users = User.objects.count()
    total_conversations = Conversation.objects.filter(message_direction='inbound').count()
    today_messages = Conversation.objects.filter(
        message_direction='inbound',
        created_at__date=today
    ).count()
    unresolved_count = UnresolvedQuery.objects.filter(status='pending').count()

    success_rate = 0
    total_logs = AnalyticsLog.objects.count()
    if total_logs:
        success_count = AnalyticsLog.objects.filter(success_flag=True).count()
        success_rate = round((success_count / total_logs) * 100, 1)

    # Top intents
    top_intents = (
        AnalyticsLog.objects.filter(intent__isnull=False)
        .values('intent__intent_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Top crops
    top_crops = (
        AnalyticsLog.objects.filter(crop__isnull=False)
        .values('crop__crop_name_sw')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Recent conversations
    recent_convos = Conversation.objects.filter(
        message_direction='inbound'
    ).select_related('user', 'detected_crop', 'detected_intent').order_by('-created_at')[:10]

    # Messages per day (last 7 days)
    daily_stats = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = Conversation.objects.filter(
            message_direction='inbound',
            created_at__date=day
        ).count()
        daily_stats.append({'day': day.strftime('%d %b'), 'count': count})

    context = {
        'total_users': total_users,
        'total_conversations': total_conversations,
        'today_messages': today_messages,
        'unresolved_count': unresolved_count,
        'success_rate': success_rate,
        'top_intents': top_intents,
        'top_crops': top_crops,
        'recent_convos': recent_convos,
        'daily_stats': daily_stats,
        'page': 'home',
    }
    return render(request, 'admin_panel/home.html', context)


# ── Conversations ───────────────────────────────
@login_required
def conversations(request):
    search = request.GET.get('q', '')
    direction = request.GET.get('direction', '')
    convos = Conversation.objects.select_related('user', 'detected_crop', 'detected_intent', 'detected_zone')

    if search:
        convos = convos.filter(
            Q(user__phone_number__icontains=search) |
            Q(raw_message__icontains=search)
        )
    if direction:
        convos = convos.filter(message_direction=direction)

    convos = convos.order_by('-created_at')[:200]
    return render(request, 'admin_panel/conversations.html', {
        'conversations': convos, 'search': search, 'page': 'conversations'
    })


# ── Users ───────────────────────────────────────
@login_required
def users_list(request):
    search = request.GET.get('q', '')
    users = User.objects.all()
    if search:
        users = users.filter(
            Q(phone_number__icontains=search) |
            Q(region__icontains=search) |
            Q(district__icontains=search)
        )
    users = users.order_by('-last_seen_at')
    return render(request, 'admin_panel/users.html', {
        'users': users, 'search': search, 'page': 'users'
    })


# ── Crops ────────────────────────────────────────
@login_required
def crops_list(request):
    crops = Crop.objects.all().order_by('priority_level')
    return render(request, 'admin_panel/crops_list.html', {'crops': crops, 'page': 'crops'})


@login_required
def crop_add(request):
    if request.method == 'POST':
        try:
            Crop.objects.create(
                crop_name_sw=request.POST['crop_name_sw'],
                crop_name_en=request.POST['crop_name_en'],
                crop_group=request.POST['crop_group'],
                priority_level=int(request.POST.get('priority_level', 1)),
                active_status=request.POST.get('active_status', 'active'),
            )
            messages.success(request, 'Zao limeongezwa.')
            return redirect('crops_list')
        except Exception as e:
            messages.error(request, f'Hitilafu: {e}')
    return render(request, 'admin_panel/crop_form.html', {
        'action': 'Ongeza', 'page': 'crops',
        'crop_groups': Crop.CROP_GROUPS,
    })


@login_required
def crop_edit(request, pk):
    crop = get_object_or_404(Crop, pk=pk)
    if request.method == 'POST':
        try:
            crop.crop_name_sw = request.POST['crop_name_sw']
            crop.crop_name_en = request.POST['crop_name_en']
            crop.crop_group = request.POST['crop_group']
            crop.priority_level = int(request.POST.get('priority_level', 1))
            crop.active_status = request.POST.get('active_status', 'active')
            crop.save()
            messages.success(request, 'Zao limebadilishwa.')
            return redirect('crops_list')
        except Exception as e:
            messages.error(request, f'Hitilafu: {e}')
    return render(request, 'admin_panel/crop_form.html', {
        'crop': crop, 'action': 'Hariri', 'page': 'crops',
        'crop_groups': Crop.CROP_GROUPS,
    })


# ── Answer Templates ─────────────────────────────
@login_required
def templates_list(request):
    search = request.GET.get('q', '')
    templates = AnswerTemplate.objects.select_related('intent', 'crop', 'zone').all()
    if search:
        templates = templates.filter(
            Q(answer_reference__icontains=search) |
            Q(answer_text_sw__icontains=search)
        )
    templates = templates.order_by('-created_at')
    return render(request, 'admin_panel/templates_list.html', {
        'templates': templates, 'search': search, 'page': 'templates'
    })


@login_required
def template_add(request):
    if request.method == 'POST':
        try:
            crop_id = request.POST.get('crop')
            zone_id = request.POST.get('zone')
            AnswerTemplate.objects.create(
                answer_reference=request.POST['answer_reference'],
                intent_id=request.POST['intent'],
                crop_id=crop_id if crop_id else None,
                zone_id=zone_id if zone_id else None,
                answer_text_sw=request.POST['answer_text_sw'],
                follow_up_question=request.POST.get('follow_up_question', ''),
                caution_note=request.POST.get('caution_note', ''),
                active_status=request.POST.get('active_status', 'active'),
            )
            messages.success(request, 'Template imeongezwa.')
            return redirect('templates_list')
        except Exception as e:
            messages.error(request, f'Hitilafu: {e}')
    return render(request, 'admin_panel/template_form.html', {
        'action': 'Ongeza',
        'intents': Intent.objects.all(),
        'crops': Crop.objects.filter(active_status='active'),
        'zones': Zone.objects.all(),
        'page': 'templates',
    })


@login_required
def template_edit(request, pk):
    template = get_object_or_404(AnswerTemplate, pk=pk)
    if request.method == 'POST':
        try:
            crop_id = request.POST.get('crop')
            zone_id = request.POST.get('zone')
            template.answer_reference = request.POST['answer_reference']
            template.intent_id = request.POST['intent']
            template.crop_id = crop_id if crop_id else None
            template.zone_id = zone_id if zone_id else None
            template.answer_text_sw = request.POST['answer_text_sw']
            template.follow_up_question = request.POST.get('follow_up_question', '')
            template.caution_note = request.POST.get('caution_note', '')
            template.active_status = request.POST.get('active_status', 'active')
            template.save()
            messages.success(request, 'Template imebadilishwa.')
            return redirect('templates_list')
        except Exception as e:
            messages.error(request, f'Hitilafu: {e}')
    return render(request, 'admin_panel/template_form.html', {
        'template': template, 'action': 'Hariri',
        'intents': Intent.objects.all(),
        'crops': Crop.objects.filter(active_status='active'),
        'zones': Zone.objects.all(),
        'page': 'templates',
    })


# ── Unresolved Queries ───────────────────────────
@login_required
def unresolved_list(request):
    queries = UnresolvedQuery.objects.select_related(
        'user', 'detected_crop', 'detected_intent'
    ).filter(status='pending').order_by('-created_at')
    return render(request, 'admin_panel/unresolved.html', {
        'queries': queries, 'page': 'unresolved'
    })


@login_required
def unresolved_resolve(request, pk):
    query = get_object_or_404(UnresolvedQuery, pk=pk)
    if request.method == 'POST':
        query.status = request.POST.get('status', 'resolved')
        query.resolution_notes = request.POST.get('notes', '')
        query.reviewed_by = request.user.username
        query.save()
        messages.success(request, 'Swali limeshughulikiwa.')
    return redirect('unresolved_list')


# ── Synonyms ─────────────────────────────────────
@login_required
def synonyms_list(request):
    synonyms = Synonym.objects.select_related('crop').order_by('main_word')
    return render(request, 'admin_panel/synonyms.html', {
        'synonyms': synonyms, 'page': 'synonyms',
        'crops': Crop.objects.filter(active_status='active'),
        'categories': Synonym.CATEGORIES,
    })


@login_required
def synonym_add(request):
    if request.method == 'POST':
        try:
            crop_id = request.POST.get('crop')
            Synonym.objects.create(
                main_word=request.POST['main_word'].lower().strip(),
                variation=request.POST['variation'].lower().strip(),
                category=request.POST['category'],
                crop_id=crop_id if crop_id else None,
            )
            messages.success(request, 'Synonym imeongezwa.')
        except Exception as e:
            messages.error(request, f'Hitilafu: {e}')
    return redirect('synonyms_list')


# ── Test Bot ──────────────────────────────────────
@login_required
def test_bot(request):
    response_text = ''
    test_message = ''
    if request.method == 'POST':
        test_message = request.POST.get('message', '')
        if test_message:
            from bot.engine import process_message
            response_text = process_message('test_admin_255000000000', test_message)
    return render(request, 'admin_panel/test_bot.html', {
        'response': response_text,
        'test_message': test_message,
        'page': 'test_bot',
    })


# ── CSV Import ─────────────────────────────────────────
@login_required
def csv_import_view(request):
    result = None
    if request.method == 'POST' and request.FILES.get('csv_file'):
        import_type = request.POST.get('import_type', '')
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Tafadhali pakia faili la CSV tu (.csv)')
        else:
            from admin_panel.csv_import import run_import
            result = run_import(import_type, csv_file)
            if result.get('error'):
                messages.error(request, f"Hitilafu: {result['error']}")
            else:
                msg = (f"✅ {result['label']}: Mpya {result['created']}, "
                       f"Zilizoboreshwa {result['updated']}, "
                       f"Makosa {len(result.get('errors', []))}")
                messages.success(request, msg)

    from admin_panel.csv_import import IMPORT_TYPES
    return render(request, 'admin_panel/csv_import.html', {
        'result': result,
        'import_types': {k: v[0] for k, v in IMPORT_TYPES.items()},
        'page': 'csv_import',
    })


# ── Analytics Full ──────────────────────────────────────
@login_required
def analytics_view(request):
    from analytics.models import AnalyticsLog
    from django.db.models import Count, Avg
    from datetime import timedelta

    total_logs = AnalyticsLog.objects.count()
    success_logs = AnalyticsLog.objects.filter(success_flag=True).count()
    success_rate = round((success_logs / total_logs * 100), 1) if total_logs else 0
    avg_response = AnalyticsLog.objects.aggregate(avg=Avg('response_time_ms'))['avg'] or 0

    top_intents = (
        AnalyticsLog.objects.filter(intent__isnull=False)
        .values('intent__intent_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    top_crops = (
        AnalyticsLog.objects.filter(crop__isnull=False)
        .values('crop__crop_name_sw')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    top_zones = (
        AnalyticsLog.objects.filter(zone__isnull=False)
        .values('zone__zone_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:7]
    )

    # Daily stats last 14 days
    from django.utils import timezone
    today = timezone.now().date()
    daily_stats = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        count = AnalyticsLog.objects.filter(created_at__date=day).count()
        success = AnalyticsLog.objects.filter(created_at__date=day, success_flag=True).count()
        daily_stats.append({'day': day.strftime('%d %b'), 'count': count, 'success': success})

    return render(request, 'admin_panel/analytics.html', {
        'total_logs': total_logs,
        'success_logs': success_logs,
        'success_rate': success_rate,
        'avg_response_ms': round(avg_response),
        'top_intents': top_intents,
        'top_crops': top_crops,
        'top_zones': top_zones,
        'daily_stats': daily_stats,
        'page': 'analytics',
    })
