"""
Dashboard → WhatsApp: hali ya namba ya bot, QR, na udhibiti wa bridge.

Ni ya mteja (KILIMONI LABS) — hahitaji kuingia Render ili kuscan QR,
kuanzisha upya, au kujua kama bot iko hewani.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from whatsapp import bridge

STATUS_SW = {
    'connected': ('Imeunganishwa', 'badge-green'),
    'waiting_qr': ('Inasubiri QR kuscaniwa', 'badge-yellow'),
    'starting': ('Inaanza…', 'badge-blue'),
    'disconnected': ('Imekatika — inajaribu kuunganisha upya', 'badge-red'),
    'logged_out': ('Imetoka (logout) — scan QR upya', 'badge-red'),
}


def _state():
    st = bridge.status() if bridge.is_configured() else {'success': False, 'error': 'BRIDGE_URL au BRIDGE_API_KEY haijawekwa'}
    label, badge = STATUS_SW.get(st.get('status'), ('Haijulikani', 'badge-gray'))
    if not st.get('success') and 'Session haipo' in str(st.get('error', '')):
        label, badge = 'Session haijaanzishwa', 'badge-gray'
    from django.utils.dateparse import parse_datetime
    for k in ('connected_at', 'last_message_at'):
        if st.get(k):
            st[k + '_dt'] = parse_datetime(st[k])
    return st, label, badge


def _queue_stats():
    """Foleni ya jumbe zinazoingia: zinazosubiri, zilizoshindwa (saa 24), zilizojibiwa leo."""
    from datetime import timedelta
    from django.utils import timezone
    from whatsapp.models import IncomingMessage
    from whatsapp.views import _sweep
    _sweep()                                  # okota zilizokwama (mf. baada ya deploy)
    day = timezone.now() - timedelta(hours=24)
    qs = IncomingMessage.objects
    return {'pending': qs.filter(status='pending').count(),
            'failed': qs.filter(status='failed', received_at__gte=day).count(),
            'done': qs.filter(status='done', received_at__gte=day).count(),
            'recent_failed': list(qs.filter(status='failed', received_at__gte=day).order_by('-id')[:5])}


@login_required
def wa_home(request):
    st, label, badge = _state()
    dbg = bridge.debug() if st.get('success') else {}
    return render(request, 'admin_panel/whatsapp.html', {
        'page': 'whatsapp', 'st': st, 'label': label, 'badge': badge, 'dbg': dbg,
        'configured': bridge.is_configured(), 'session': bridge.session_name(), 'q': _queue_stats(),
    })


@login_required
def wa_qr(request):
    """JSON kwa ukurasa: hali + QR (inajisasisha kila sekunde chache)."""
    data = bridge.qr() if bridge.is_configured() else {'success': False}
    label, badge = STATUS_SW.get(data.get('status'), ('Haijulikani', 'badge-gray'))
    return JsonResponse({'status': data.get('status', ''), 'label': label, 'badge': badge,
                         'qr': data.get('qr') or '', 'number': data.get('number') or '',
                         'error': '' if data.get('success') else data.get('error', '')})


# jina la function ya bridge → ujumbe wa mafanikio (inatafutwa wakati wa kubofya)
ACTIONS = {
    'start': 'Session imeanzishwa.',
    'restart': 'Session imeanzishwa upya — inaunganisha.',
    'logout': 'Namba imetolewa. Scan QR mpya ili kuunganisha namba.',
    'prune': None,
}


@login_required
@require_POST
def wa_action(request):
    action = request.POST.get('action', '')
    if action == 'logout' and request.POST.get('confirm') != 'TOA':
        messages.error(request, 'Andika TOA kuthibitisha kutoa namba (logout).')
        return redirect('wa_home')
    if action == 'ping':
        to = ''.join(ch for ch in request.POST.get('to', '') if ch.isdigit())
        if to.startswith('0'):
            to = '255' + to[1:]
        if len(to) < 9:
            messages.error(request, 'Weka namba sahihi ya kupokea ujumbe wa majaribio.')
            return redirect('wa_home')
        res = bridge.ping(to)
        (messages.success if res.get('success') else messages.error)(
            request, f"Ujumbe wa majaribio umetumwa kwa {to}. Usipoufikia, session imekufa — anzisha upya au scan QR."
            if res.get('success') else f"Imeshindwa kutuma: {res.get('error')}")
        return redirect('wa_home')
    if action not in ACTIONS:
        messages.error(request, 'Kitendo hakijulikani.')
        return redirect('wa_home')
    ok_msg = ACTIONS[action]
    res = bridge.prune(30) if action == 'prune' else getattr(bridge, action)()
    if res.get('success'):
        messages.success(request, ok_msg or f"Funguo za zamani {res.get('removed', 0)} zimefutwa.")
    else:
        messages.error(request, f"Imeshindwa: {res.get('error', 'kosa lisilojulikana')}")
    return redirect('wa_home')
