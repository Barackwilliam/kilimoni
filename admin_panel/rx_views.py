"""
Dashboard ya Injini ya Uchunguzi (rules engine, MHD-007)
========================================================

Kurasa hizi ni za mteja (KILIMONI LABS) — si za JamiiTek pekee:

  /dashboard/uchunguzi/             Data iliyopo + kupakia Excel za MHD-007
  /dashboard/uchunguzi/hakiki/      Hakiki (dry run) kabla ya kuhifadhi
  /dashboard/uchunguzi/hifadhi/     Hifadhi baada ya hakiki
  /dashboard/uchunguzi/mipangilio/  EngineSetting + kamusi ya lugha rahisi
  /dashboard/uchunguzi/kesi/        Kumbukumbu za uchunguzi (trace)
  /dashboard/conversations/<id>/    Ujumbe mmoja + trace yake kamili
"""
import os
import shutil
import tempfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bot.models import Conversation
from diagnosis import models as dm
from diagnosis.importer import import_mhd007
from diagnosis.models import DEFAULT_SETTINGS, EngineSetting, FarmerTerm

MAX_UPLOAD_MB = 15
SESSION_KEY = 'rx_upload_dir'

DATA_COUNTS = [
    ('Wadudu (007A)', dm.Pest),
    ('Magonjwa (007B)', dm.Disease),
    ('Dalili (007C)', dm.Symptom),
    ('Maswali ya kufuatilia (007C)', dm.FollowupQuestion),
    ('Kanuni za uchunguzi (007D)', dm.DiagnosisRule),
    ('Kanuni za maamuzi (007A/B)', dm.DecisionRule),
    ('Kanuni za uhakika', dm.ConfidenceRule),
    ('Tiba / IPM (007E)', dm.Treatment),
    ('Kanuni za usalama (007E)', dm.SafetyRule),
    ('Kanuni za mapendekezo (007E)', dm.RecommendationRule),
    ('Kanuni za kupandisha kwa afisa ugani (007D)', dm.EscalationRule),
]

# Maelezo ya settings kwa lugha ya mteja + aina ya thamani inayokubalika
SETTING_RULES = {
    'label_low': ('number', 0, 1, 'Uhakika wa "Low" kwenye dataset (0–1)'),
    'label_medium': ('number', 0, 1, 'Uhakika wa "Medium" (0–1)'),
    'label_high': ('number', 0, 1, 'Uhakika wa "High" (0–1)'),
    'range_strategy': ('choice', ('mid', 'min', 'max'),
                       None, 'Kwa ranges kama +0.15 hadi +0.30: katikati (mid), ndogo (min) au kubwa (max)'),
    'confidence_cap': ('number', 0.5, 1, 'Kikomo cha juu cha uhakika'),
    'diagnosis_threshold': ('number', 0.3, 1, 'Uhakika wa chini ili kutoa utambuzi'),
    'min_lead_margin': ('number', 0, 1, 'Tofauti ya chini kati ya kisababishi cha 1 na cha 2'),
    'severity_low_max': ('number', 0, 100, '% ya shamba chini ya hapa = ukali mdogo (Low)'),
    'severity_medium_max': ('number', 0, 100, '% ya shamba hadi hapa = wastani; juu yake = High'),
    'allow_product_names': ('choice', ('0', '1'), None,
                            'Taja majina ya dawa (SAFE001): 1 tu baada ya orodha ya dawa zilizosajiliwa kuidhinishwa'),
    'initial_source': ('choice', ('007D', '007A'), None, 'Chanzo cha uhakika wa mwanzo kikiwa na vingi'),
    'symptom_match_ratio': ('number', 0.1, 1, 'Sehemu ya maneno ya dalili yanayotakiwa kulingana'),
    'key_question_no_adjustment': ('number', -1, 0, 'Mabadiliko ya uhakika ishara kuu ikikataliwa (hasi)'),
    'rec_min_severity': ('choice', ('low', 'medium', 'high'), None,
                         'Ukali wa chini kabla ya kutaja kemikali (Recommendation Rule)'),
    'max_questions': ('number', 1, 10, 'Idadi ya juu ya maswali kwa uchunguzi mmoja'),
    'ai_language': ('choice', ('1', '0'), None,
                    'AI ielewe lugha ya mkulima (dalili, majibu, ukubwa wa tatizo): 1 = ndiyo, 0 = maneno tu'),
    'ai_summary': ('choice', ('1', '0'), None,
                   'AI iandike aya fupi ya kibinadamu juu ya jibu (inakaguliwa kabla ya kutumwa)'),
    'show_rules_to_farmer': ('choice', ('0', '1'), None,
                             'Onyesha namba za kanuni (DR-…, CONF…) kwa mkulima: 1 = ndiyo (kwa demo), 0 = hapana'),
}


def _cleanup_upload(request):
    path = request.session.pop(SESSION_KEY, None)
    if path and os.path.isdir(path) and path.startswith(tempfile.gettempdir()):
        shutil.rmtree(path, ignore_errors=True)


def _staged_files(request):
    path = request.session.get(SESSION_KEY)
    if not path or not os.path.isdir(path):
        return []
    return sorted(os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.xlsx'))


# ─────────────────────────── Data + kupakia ───────────────────────────

@login_required
def rx_home(request):
    counts = [(label, model.objects.filter(is_active=True).count()) for label, model in DATA_COUNTS]
    return render(request, 'admin_panel/rx_home.html', {
        'page': 'rx_home', 'counts': counts, 'max_mb': MAX_UPLOAD_MB,
        'staged': [os.path.basename(f) for f in _staged_files(request)],
    })


@login_required
@require_POST
def rx_preview(request):
    files = request.FILES.getlist('files')
    if not files:
        messages.error(request, 'Chagua angalau faili moja la Excel (.xlsx).')
        return redirect('rx_home')

    _cleanup_upload(request)
    folder = tempfile.mkdtemp(prefix='kilimoni_mhd007_')
    saved, skipped = [], []
    for f in files:
        name = os.path.basename(f.name)
        if not name.lower().endswith('.xlsx'):
            skipped.append(f"{name}: si faili la .xlsx")
            continue
        if f.size > MAX_UPLOAD_MB * 1024 * 1024:
            skipped.append(f"{name}: limezidi MB {MAX_UPLOAD_MB}")
            continue
        dest = os.path.join(folder, name)
        with open(dest, 'wb') as out:
            for chunk in f.chunks():
                out.write(chunk)
        saved.append(dest)
    request.session[SESSION_KEY] = folder

    report = None
    error = None
    if saved:
        try:
            report = import_mhd007(saved, dry_run=True)
        except Exception as exc:          # faili lililoharibika, n.k.
            error = f"Faili halikusomeka: {exc}"
    return render(request, 'admin_panel/rx_preview.html', {
        'page': 'rx_home', 'report': report, 'error': error, 'skipped': skipped,
        'files': [os.path.basename(p) for p in saved],
        'can_save': bool(report and report.workbooks and not report.rolled_back and not error),
    })


@login_required
@require_POST
def rx_confirm(request):
    files = _staged_files(request)
    if not files:
        messages.error(request, 'Hakuna faili lililosubiri kuhifadhiwa. Pakia upya.')
        return redirect('rx_home')
    try:
        report = import_mhd007(files, dry_run=False)
    finally:
        _cleanup_upload(request)
    if report.rolled_back:
        messages.error(request, 'Hakuna kilichohifadhiwa: makosa yalikuwa mengi kuliko kiwango kinachoruhusiwa.')
    else:
        created = sum(c['created'] for c in report.counts.values())
        updated = sum(c['updated'] for c in report.counts.values())
        messages.success(request, f"Data imehifadhiwa ({', '.join(report.workbooks)}): "
                                  f"mpya {created}, zilizosasishwa {updated}. Bot inaitumia mara moja.")
    return redirect('rx_home')


@login_required
@require_POST
def rx_cancel(request):
    _cleanup_upload(request)
    messages.success(request, 'Upakiaji umeghairiwa — hakuna kilichohifadhiwa.')
    return redirect('rx_home')


# ─────────────────────────── Mipangilio + kamusi ───────────────────────────

def _validate_setting(key, raw):
    kind, a, b, _ = SETTING_RULES.get(key, ('text', None, None, ''))
    value = (raw or '').strip()
    if kind == 'choice':
        return (value, None) if value in a else (None, f"{key}: chagua mojawapo ya {', '.join(a)}")
    if kind == 'number':
        try:
            num = float(value)
        except ValueError:
            return None, f"{key}: lazima iwe namba"
        if not (a <= num <= b):
            return None, f"{key}: lazima iwe kati ya {a} na {b}"
        return value, None
    return value, None


@login_required
def rx_settings(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'settings':
            errors, changed = [], 0
            for key in DEFAULT_SETTINGS:
                if key not in request.POST:
                    continue
                value, err = _validate_setting(key, request.POST[key])
                if err:
                    errors.append(err)
                    continue
                row, _ = EngineSetting.objects.get_or_create(
                    key=key, defaults={'value': value, 'description': DEFAULT_SETTINGS[key][1]})
                if row.value != value:
                    row.value = value
                    row.save(update_fields=['value', 'updated_at'])
                    changed += 1
            for e in errors:
                messages.error(request, e)
            if changed:
                messages.success(request, f"Mipangilio {changed} imehifadhiwa.")
        elif action == 'term_add':
            term = request.POST.get('term', '').strip()
            plain = request.POST.get('plain', '').strip()
            if term and plain:
                FarmerTerm.objects.update_or_create(term=term, defaults={'plain': plain, 'is_active': True})
                messages.success(request, f"'{term}' → '{plain}' imehifadhiwa.")
            else:
                messages.error(request, 'Jaza neno la kiufundi na maneno rahisi.')
        elif action in ('term_toggle', 'term_delete'):
            t = FarmerTerm.objects.filter(pk=request.POST.get('pk')).first()
            if t and action == 'term_toggle':
                t.is_active = not t.is_active
                t.save(update_fields=['is_active', 'updated_at'])
            elif t:
                t.delete()
        return redirect('rx_settings')

    current = dict(EngineSetting.objects.values_list('key', 'value'))
    rows = []
    for key, (default, _) in DEFAULT_SETTINGS.items():
        kind, a, b, help_text = SETTING_RULES.get(key, ('text', None, None, ''))
        rows.append({'key': key, 'value': current.get(key, default), 'default': default,
                     'kind': kind, 'choices': a if kind == 'choice' else None,
                     'min': a if kind == 'number' else None, 'max': b if kind == 'number' else None,
                     'help': help_text})
    return render(request, 'admin_panel/rx_settings.html', {
        'page': 'rx_settings', 'rows': rows, 'terms': FarmerTerm.objects.all(),
    })


# ─────────────────────────── Kumbukumbu za uchunguzi ───────────────────────────

def _cause_names(ids):
    names = {p.source_id: p.name_sw for p in dm.Pest.objects.filter(source_id__in=ids)}
    names.update({d.source_id: d.name_sw for d in dm.Disease.objects.filter(source_id__in=ids)})
    return names


@login_required
def rx_cases(request):
    decision = request.GET.get('decision', '')
    qs = (Conversation.objects.select_related('user')
          .filter(message_direction='outbound', trace__mode='rules_engine',
                  trace__decision__in=['diagnosed', 'uncertain', 'no_rule_matched', 'crop_without_rules']))
    if decision:
        qs = qs.filter(trace__decision=decision)
    cases = list(qs.order_by('-created_at')[:200])
    names = _cause_names([c.trace.get('diagnosis') for c in cases if c.trace.get('diagnosis')])
    for c in cases:
        c.cause_name = names.get(c.trace.get('diagnosis'), '')
        conf = c.trace.get('confidence')
        c.conf_pct = round(conf * 100) if isinstance(conf, (int, float)) else None
    return render(request, 'admin_panel/rx_cases.html', {
        'page': 'rx_cases', 'cases': cases, 'decision': decision,
    })


DECISION_SW = {
    'diagnosed': 'Utambuzi umetolewa', 'uncertain': 'Hakuna uhakika wa kutosha',
    'no_rule_matched': 'Dalili hazilingani na kanuni', 'crop_without_rules': 'Zao halina kanuni',
    'cancelled': 'Mkulima amesitisha',
}


@login_required
def conversation_detail(request, pk):
    convo = get_object_or_404(Conversation.objects.select_related('user'), pk=pk)
    trace = convo.trace or {}
    ids = set((trace.get('scores') or {}).keys()) | {trace.get('diagnosis')}
    names = _cause_names([i for i in ids if i])
    scores = sorted(((cid, names.get(cid, cid), round(v * 100)) for cid, v in (trace.get('scores') or {}).items()),
                    key=lambda r: -r[2])
    initial = {cid: round(v.get('score', 0) * 100) for cid, v in (trace.get('initial') or {}).items()}
    evidence = []
    for ev in trace.get('evidence') or []:
        evidence.append({
            'question': ev.get('question'), 'answer': ev.get('answer'), 'via': ev.get('via'),
            'sources': ', '.join(ev.get('sources') or []),
            'deltas': [(names.get(cid, cid), round(d * 100)) for cid, d in (ev.get('deltas') or {}).items()],
        })
    # Mazungumzo yote ya mkulima huyu karibu na ujumbe huu (muktadha)
    thread = (Conversation.objects.filter(user=convo.user, created_at__lte=convo.created_at)
              .order_by('-created_at')[:12])
    return render(request, 'admin_panel/conversation_detail.html', {
        'page': 'conversations', 'c': convo, 'trace': trace, 'scores': scores, 'initial': initial,
        'evidence': evidence, 'diagnosis_name': names.get(trace.get('diagnosis'), ''),
        'decision_sw': DECISION_SW.get(trace.get('decision'), trace.get('decision') or ''),
        'gate': trace.get('gate') or {}, 'thread': list(reversed(list(thread))),
        'confidence_pct': round(trace['confidence'] * 100) if isinstance(trace.get('confidence'), (int, float)) else None,
    })
