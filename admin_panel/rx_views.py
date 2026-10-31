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
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bot.models import Conversation
from crops.models import Crop
from diagnosis import models as dm
from diagnosis.importer import import_mhd007
from advisory import importer as adv_importer
from advisory import location as adv_location
from advisory.models import (CropFamily, RotationCompatibility, RotationRule, RotationSequence,
                             Aez, AezAlias, ClimateRisk, CropCalendar, LocationSynonym, PlantingRule,
                             SeasonProfile, SeedDecisionRule, SoilConstraint, SoilRanking, SoilSuitability,
                             SoilType, VarietyAgronomy, VarietyRegistry, WardLocation)
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
    ('Kata (MHD-001)', WardLocation),
    ('Kanda za kilimo — AEZ (MHD-001)', Aez),
    ('Visawe vya maeneo (MHD-001)', LocationSynonym),
    ('Aina za mbegu — sajili (MHD-003A)', VarietyRegistry),
    ('Mbegu zenye sifa za kilimo (MHD-003A)', VarietyAgronomy),
    ('Kanuni za uamuzi wa mbegu (MHD-003A)', SeedDecisionRule),
    ('Kalenda za mazao (MHD-006)', CropCalendar),
    ('Misimu ya kanda (MHD-006)', SeasonProfile),
    ('Kanuni za kupanda (MHD-006)', PlantingRule),
    ('Aina za udongo (MHD-004)', SoilType),
    ('Ufaafu wa udongo kwa mazao (MHD-004)', SoilSuitability),
    ('Ulinganifu wa mzunguko (MHD-006 R4)', RotationCompatibility),
    ('Mifuatano ya mzunguko (MHD-006 R4)', RotationSequence),
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

    run, error = None, None
    if saved:
        try:
            run = _run_imports(saved, dry_run=True)
        except Exception as exc:          # faili lililoharibika, n.k.
            error = f"Faili halikusomeka: {exc}"
    reports = run.reports if run else []
    can_save = bool(reports) and not error and all(not r.rolled_back for _, r in reports) \
        and any(r.workbooks for _, r in reports)
    return render(request, 'admin_panel/rx_preview.html', {
        'page': 'rx_home', 'reports': reports, 'error': error, 'skipped': skipped,
        'files': [os.path.basename(p) for p in saved], 'can_save': can_save,
        'new_crops': run.crops.missing if run else [], 'analysis': run.analysis if run else None,
        'crop_groups': Crop.CROP_GROUPS, 'schema_proposals': run.schema if run else [],
    })


class _Run:
    def __init__(self, reports, crops, analysis=None, schema=()):
        self.reports, self.crops, self.analysis, self.schema = reports, crops, analysis, list(schema)


def _run_imports(files, dry_run, crop_choices=None, schema_choices=None):
    """
    Gawa faili kwa aina: MHD-007 → uchunguzi; MHD-001…006 → ushauri.

    Hakiki (dry_run): importers zote zinaendeshwa ndani ya transaction MOJA
    inayorudishwa nyuma mwishoni — hivyo mazao mapya, viungo kati ya
    workbooks, na uchambuzi vinaona data ya upakiaji mzima kama ingehifadhiwa.
    Kuhifadhi: mazao mapya yanaundwa tu kama yamo kwenye crop_choices
    (yaliyothibitishwa na mteja kwenye hakiki).
    """
    from django.db import transaction
    from datasets import analysis as ds_analysis
    from datasets import crops as crop_intake
    from diagnosis.importer import ImportReport, _Rollback

    rx_files = [f for f in files if 'MHD-007' in os.path.basename(f).upper()]
    adv_files = [f for f in files if adv_importer.workbook_code(f)]
    unknown = [os.path.basename(f) for f in files if f not in rx_files and f not in adv_files]
    from datasets import schema as ds_schema
    intake = crop_intake.CropIntake(create=True, approved=None if dry_run else (crop_choices or {}))
    # Majina yaliyobadilishwa: hakiki inapendekeza (na kutumia yenye uhakika); kuhifadhi kunatumia yaliyothibitishwa
    proposals = ds_schema.propose(files) if dry_run else list(schema_choices or [])
    smap = ds_schema.build_map(proposals, only_default=dry_run)

    def run_all():
        reports = []
        if rx_files:
            reports.append(('Uchunguzi wa matatizo (MHD-007)', import_mhd007(rx_files, dry_run=False)))
        if adv_files:
            reports.append(('Ushauri wa kilimo (MHD-001…006)', adv_importer.import_files(adv_files, dry_run=False)))
        if unknown:
            rep = ImportReport(dry_run)
            rep.warnings.append(f"Bado hazina moduli ya kanuni (zitachambuliwa tu): {', '.join(unknown)}")
            reports.append(('Faili zisizo na moduli bado', rep))
        return reports

    with crop_intake.use(intake), ds_schema.use(smap):
        if not dry_run:
            reports = run_all()
            if proposals and not any(r.rolled_back for _, r in reports):
                ds_schema.save(proposals)
            return _Run(reports, intake, schema=proposals)
        result = {}
        try:
            with transaction.atomic():
                reports = run_all()
                for _, r in reports:
                    r.dry_run = True
                result['run'] = _Run(reports, intake, ds_analysis.analyse(
                    files, [r for _, r in reports], supported_codes=adv_importer.SUPPORTED_CODES), proposals)
                raise _Rollback()
        except _Rollback:
            pass
        from advisory.location import clear_cache
        clear_cache()
        return result['run']


def _schema_choices(post):
    """Ramani za majina zilizothibitishwa kwenye hakiki."""
    out = []
    for i in range(int(post.get('schema_total') or 0)):
        if not post.get(f'schema_add_{i}'):
            continue
        kind = post.get(f'schema_kind_{i}')
        expected, actual = (post.get(f'schema_expected_{i}') or '').strip(), (post.get(f'schema_actual_{i}') or '').strip()
        if kind in ('sheet', 'column') and expected and actual:
            out.append({'kind': kind, 'sheet': (post.get(f'schema_sheet_{i}') or '').strip(), 'expected': expected,
                        'actual': actual, 'method': post.get(f'schema_method_{i}') or 'mkono',
                        'code': post.get(f'schema_code_{i}') or ''})
    return out


def _crop_choices(post):
    """Mazao mapya yaliyothibitishwa kwenye hakiki: key → {'name_sw','name_en','group'}."""
    groups = {g for g, _ in Crop.CROP_GROUPS}
    out = {}
    for i in range(int(post.get('crop_total') or 0)):
        if not post.get(f'crop_add_{i}'):
            continue
        key = (post.get(f'crop_key_{i}') or '').strip()
        sw = (post.get(f'crop_sw_{i}') or '').strip()
        en = (post.get(f'crop_en_{i}') or '').strip()
        group = post.get(f'crop_group_{i}')
        if key and sw:
            out[key] = {'name_sw': sw, 'name_en': en or sw, 'group': group if group in groups else 'cash_crops'}
    return out


@login_required
@require_POST
def rx_confirm(request):
    files = _staged_files(request)
    if not files:
        messages.error(request, 'Hakuna faili lililosubiri kuhifadhiwa. Pakia upya.')
        return redirect('rx_home')
    try:
        run = _run_imports(files, dry_run=False, crop_choices=_crop_choices(request.POST),
                           schema_choices=_schema_choices(request.POST))
    finally:
        _cleanup_upload(request)
    reports = run.reports
    if run.schema and not any(r.rolled_back for _, r in reports):
        messages.success(request, f"Ramani za majina {len(run.schema)} zimehifadhiwa — upakiaji ujao wenye majina "
                                  "hayo utasomwa moja kwa moja.")
    made = [i for i in run.crops.missing if i['created']]
    if made:
        messages.success(request, "Mazao mapya yameongezwa: " + ', '.join(
            (run.crops.approved or {}).get(i['key'], i)['name_sw'] for i in made))
    skipped_crops = [i['raw'] for i in run.crops.missing if not i['created']]
    if skipped_crops:
        messages.warning(request, "Mazao hayakuongezwa (data yake imeingia bila zao, bot haitaitumia): "
                         + ', '.join(skipped_crops))
    for title, report in reports:
        if report.rolled_back:
            messages.error(request, f"{title}: hakuna kilichohifadhiwa — makosa yalikuwa mengi kuliko "
                                    "kiwango kinachoruhusiwa.")
        elif report.workbooks:
            created = sum(c['created'] for c in report.counts.values())
            updated = sum(c['updated'] for c in report.counts.values())
            messages.success(request, f"Data imehifadhiwa ({', '.join(report.workbooks)}): "
                                      f"mpya {created}, zilizosasishwa {updated}. Bot inaitumia mara moja.")
    return redirect('rx_home')


@login_required
def rx_locations(request):
    """Kanda (AEZ) na kata za MHD-001 + kujaribu kutambua eneo kwa maneno ya mkulima."""
    from django.db.models import Count
    if request.method == 'POST':
        from advisory.importer import apply_alias
        alias = AezAlias.objects.filter(pk=request.POST.get('alias')).first()
        if alias:
            alias.aez = Aez.objects.filter(pk=request.POST.get('aez')).first()
            alias.auto_matched = False
            alias.save()
            n = apply_alias(alias)
            messages.success(request, f"{alias.dataset} {alias.external_id} sasa → "
                                      f"{alias.aez.source_id if alias.aez else 'haijaunganishwa'} ({n} records zimesasishwa).")
        return redirect('rx_locations')
    q = request.GET.get('q', '').strip()
    result = adv_location.resolve(q) if q else None
    aezs = Aez.objects.annotate(n=Count('wards')).select_related('zone')
    regions = (WardLocation.objects.filter(is_active=True).values('region_name', 'district_name')
               .annotate(n=Count('id')).order_by('region_name', 'district_name'))
    return render(request, 'admin_panel/rx_locations.html', {
        'page': 'rx_locations', 'q': q, 'result': result, 'tried': bool(q),
        'aezs': aezs, 'regions': regions, 'ward_total': WardLocation.objects.filter(is_active=True).count(),
        'aliases': AezAlias.objects.select_related('aez'), 'all_aez': Aez.objects.all(),
    })


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
    module = request.GET.get('module', '')
    finals = {'rules_engine': ['diagnosed', 'uncertain', 'no_rule_matched', 'crop_without_rules'],
              'seed_advisor': SEED_FINAL, 'planting_advisor': PLANT_FINAL, 'soil_advisor': SOIL_FINAL,
              'rotation_advisor': ROT_FINAL}
    q = Q()
    for mode, decisions in finals.items():
        if not module or module == mode:
            q |= Q(trace__mode=mode, trace__decision__in=decisions)
    qs = Conversation.objects.select_related('user').filter(message_direction='outbound').filter(q)
    if decision:
        qs = qs.filter(trace__decision=decision)
    cases = list(qs.order_by('-created_at')[:200])
    names = _cause_names([c.trace.get('diagnosis') for c in cases if c.trace.get('diagnosis')])
    for c in cases:
        c.cause_name = names.get(c.trace.get('diagnosis'), '')
        conf = c.trace.get('confidence')
        c.conf_pct = round(conf * 100) if isinstance(conf, (int, float)) else None
    for c in cases:
        c.decision_sw = DECISION_SW.get(c.trace.get('decision'), c.trace.get('decision'))
        if c.trace.get('mode') == 'seed_advisor':
            c.cause_name = ', '.join(c.trace.get('recommended') or []) or c.trace.get('variety', '')
        elif c.trace.get('mode') == 'rotation_advisor':
            c.cause_name = ' → '.join(x for x in (c.trace.get('previous'), c.trace.get('next')) if x)
            c.decision_sw = {'recommended': 'Imependekezwa', 'avoid': 'Epuka', 'avoid_only': 'Epuka (orodha)',
                             'no_assessment': 'Hakuna tathmini'}.get(c.trace.get('decision'), c.decision_sw)
        elif c.trace.get('mode') == 'soil_advisor':
            c.cause_name = c.trace.get('soil_name', '') + (f" · {c.trace['crop']}" if c.trace.get('crop') else '')
            c.conf_pct = c.trace.get('score')
        elif c.trace.get('mode') == 'planting_advisor':
            c.cause_name = f"{c.trace.get('crop', '')} · {c.trace.get('location', '')}"

    return render(request, 'admin_panel/rx_cases.html', {
        'page': 'rx_cases', 'cases': cases, 'decision': decision, 'module': module,
    })


ROT_FINAL = ['recommended', 'avoid', 'avoid_only', 'no_assessment']
SOIL_FINAL = ['suitable', 'suitable_with_conditions', 'not_suitable_without_improvement', 'no_assessment', 'soil_info']
PLANT_FINAL = ['PANDA_SASA', 'PANDA_KWA_TAHADHARI', 'SUBIRI', 'WAIT', 'WAIT_OR_EARLY_VARIETY',
               'ALLOW_IRRIGATION_PLANTING', 'DO_NOT_PLANT', 'INFO_ONLY']
SEED_FINAL = ['recommended', 'variety_fits', 'variety_not_fit', 'variety_no_profile', 'no_suitable_variety']


DECISION_SW = {
    'diagnosed': 'Utambuzi umetolewa', 'uncertain': 'Hakuna uhakika wa kutosha',
    'no_rule_matched': 'Dalili hazilingani na kanuni', 'crop_without_rules': 'Zao halina kanuni',
    'cancelled': 'Mkulima amesitisha',
    'recommended': 'Mbegu zimependekezwa', 'variety_fits': 'Mbegu aliyoitaja inafaa',
    'variety_not_fit': 'Mbegu aliyoitaja haifai kanda yake', 'variety_no_profile': 'Mbegu haina sifa za kilimo',
    'no_suitable_variety': 'Hakuna mbegu iliyoorodheshwa kwa kanda', 'need_location': 'Imeuliza eneo',
    'need_crop': 'Imeuliza zao',
    'PANDA_SASA': 'Panda sasa', 'PANDA_KWA_TAHADHARI': 'Panda kwa tahadhari', 'SUBIRI': 'Subiri',
    'WAIT': 'Subiri mvua ziendelee', 'WAIT_OR_EARLY_VARIETY': 'Subiri / mbegu ya muda mfupi',
    'ALLOW_IRRIGATION_PLANTING': 'Panda kwa umwagiliaji', 'DO_NOT_PLANT': 'Usipande sasa',
    'INFO_ONLY': 'Taarifa ya jumla tu',
    'suitable': 'Udongo unafaa', 'suitable_with_conditions': 'Unafaa kwa masharti',
    'not_suitable_without_improvement': 'Haufai bila maboresho', 'no_assessment': 'Hakuna tathmini ya zao',
    'soil_info': 'Taarifa ya udongo', 'need_soil': 'Imeuliza udongo',
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


@login_required
def rx_seeds(request):
    """Mbegu za MHD-003A + kujaribu ushauri wa mbegu kwa maneno ya mkulima na eneo."""
    from crops.models import Crop
    from advisory import seed as adv_seed
    q = request.GET.get('q', '').strip()
    crop_id = request.GET.get('crop')
    crops = Crop.objects.filter(id__in=VarietyAgronomy.objects.values('crop_id'))
    crop = crops.filter(id=crop_id).first() if crop_id else crops.first()
    preview, trace = None, None
    if q and crop:
        preview, trace = adv_seed.advise(crop, adv_location.resolve(q), q, {})
    return render(request, 'admin_panel/rx_seeds.html', {
        'page': 'rx_seeds', 'q': q, 'crops': crops, 'crop': crop, 'preview': preview, 'trace': trace,
        'profiles': VarietyAgronomy.objects.filter(is_active=True).order_by('maturity_days_max'),
        'rules': SeedDecisionRule.objects.filter(is_active=True),
        'registry_only': VarietyRegistry.objects.filter(is_active=True, agronomy__isnull=True),
    })


@login_required
def rx_planting(request):
    """Wakati wa kupanda (MHD-006) + kujaribu kwa tarehe yoyote na hali ya mvua."""
    import datetime
    from crops.models import Crop
    from advisory import planting as adv_planting
    q = request.GET.get('q', '').strip()
    crops = Crop.objects.all()
    crop = crops.filter(id=request.GET.get('crop')).first() or crops.filter(crop_name_sw__iexact='mahindi').first()
    try:
        day = datetime.date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        day = None
    rain = request.GET.get('rain') or None
    preview, trace = None, None
    if q and crop:
        preview, trace = adv_planting.advise(crop, adv_location.resolve(q), q, {}, today=day, rain=rain)
    return render(request, 'admin_panel/rx_planting.html', {
        'page': 'rx_planting', 'q': q, 'crops': crops, 'crop': crop, 'date': request.GET.get('date', ''),
        'rain': rain or '', 'preview': preview, 'trace': trace,
        'seasons': SeasonProfile.objects.select_related('aez'),
        'calendars': CropCalendar.objects.select_related('aez', 'crop'),
        'risks': ClimateRisk.objects.select_related('aez'),
    })


@login_required
def rx_soil(request):
    """Udongo (MHD-004) + kujaribu ushauri wa udongo kwa maneno ya mkulima."""
    from crops.models import Crop
    from advisory import soil as adv_soil
    q = request.GET.get('q', '').strip()
    crops = Crop.objects.all()
    crop = crops.filter(id=request.GET.get('crop')).first() if request.GET.get('crop') else None
    preview, trace = None, None
    if q:
        preview, trace = adv_soil.advise(crop, q, {})
    return render(request, 'admin_panel/rx_soil.html', {
        'page': 'rx_soil', 'q': q, 'crops': crops, 'crop': crop, 'preview': preview, 'trace': trace,
        'soils': SoilType.objects.prefetch_related('synonyms'),
        'suits': SoilSuitability.objects.select_related('soil', 'crop'),
        'ranks': SoilRanking.objects.select_related('crop'), 'constraints': SoilConstraint.objects.all(),
    })


@login_required
def rx_rotation(request):
    """Mzunguko wa mazao (MHD-006 R4) + kujaribu."""
    from advisory import rotation as adv_rotation
    q = request.GET.get('q', '').strip()
    place = request.GET.get('place', '').strip()
    preview, trace = None, None
    if q:
        preview, trace = adv_rotation.advise(q, adv_location.resolve(place) if place else None, {})
    return render(request, 'admin_panel/rx_rotation.html', {
        'page': 'rx_rotation', 'q': q, 'place': place, 'preview': preview, 'trace': trace,
        'families': CropFamily.objects.all(), 'comps': RotationCompatibility.objects.order_by('previous_name', '-score'),
        'seqs': RotationSequence.objects.select_related('aez'), 'rules': RotationRule.objects.all(),
    })
