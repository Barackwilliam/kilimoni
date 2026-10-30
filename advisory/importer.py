"""
Import ya Excel za MHD-001 … MHD-006 kwenda kwenye tables za advisory.

Kanuni zilezile za diagnosis/importer.py (MHD-007):
  - Upsert kwa ID ya dataset (location_id, aez_id, …) — kurudia ni salama.
  - Dry run = import halisi ndani ya transaction kisha rollback, hivyo
    ripoti ya hakiki inasema ukweli.
  - Makosa yakizidi 2% ya rows, batch nzima inarudishwa nyuma.

Kila workbook ina handler yake kwenye WORKBOOKS. Hatua zinazofuata
(mbegu, msimu, udongo, mzunguko) zinaongeza handlers hapa.
"""
import os
import re

from django.db import transaction

from diagnosis.importer import (
    MAX_FAILURE_RATIO, ImportReport, _Rollback, _find_sheet, _float, _read_sheet,
)

from .models import (
    AdvisoryConfidenceBand, AdvisoryRule, Aez, ExplainTemplate, LocationRule, LocationSynonym,
    SeedDecisionRule, SeedIntent, VarietyAgronomy, VarietyRegistry, VarietySynonym, WardLocation,
)


def _list(value):
    return [p.strip() for p in re.split(r'[;,]', str(value or '')) if p.strip()]


def _span(value):
    """'Siku 75–90' → (75, 90); '500–1400 m' → (500, 1400); 'Siku 120' → (120, 120)."""
    text = re.sub(r'MHD-?\d+[A-Z]?', '', str(value or ''), flags=re.I)
    nums = [int(n) for n in re.findall(r'\d{2,5}', text)]
    if not nums:
        return None, None
    return nums[0], (nums[1] if len(nums) > 1 else nums[0])


def _looks_like_variety(text):
    """'SC 403', 'PAN 53', 'DK8031' — si 'Kisha tumia MHD-001'."""
    t = str(text or '').strip()
    return bool(re.fullmatch(r'[A-Za-z]{2,6}[\s-]?\d{2,5}[A-Za-z]?', t)) and not t.upper().startswith('MHD')


def _variety_key(name):
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())


def _crop(name):
    from crops.models import Crop
    if not name:
        return None
    return (Crop.objects.filter(crop_name_sw__iexact=name).first()
            or Crop.objects.filter(crop_name_en__iexact=name).first())


def workbook_code(name):
    """'MHD-001_Location…xlsx' → 'MHD-001'; 'MHD-003A_Seed…' → 'MHD-003A'."""
    base = os.path.basename(str(name)).upper()
    m = re.search(r'MHD-00[1-6][A-Z]?', base)
    return m.group(0) if m else None


def _active(row, col='cms_status'):
    status = (row.get(col) or '')
    status = str(status).lower()
    return not any(w in status for w in ('inactive', 'retired', 'rejected', 'draft only'))


class _Importer:
    def __init__(self, report):
        self.r = report

    def rows(self, wb, code, sheet_name, label, id_col, handler):
        ws = _find_sheet(wb, sheet_name)
        if ws is None:
            self.r.warnings.append(f"{code}: sheet '{sheet_name}' haipo — imerukwa")
            return
        source = f"{code}/{ws.title}"
        for row in _read_sheet(ws):
            sid = row.get(id_col)
            if not sid:
                continue
            self.r.rows_total += 1
            try:
                with transaction.atomic():
                    created = handler(str(sid).strip(), row, source)
                if created is not None:
                    self.r.count(label, created)
            except Exception as e:
                self.r.errors.append(f"{source} {sid}: {e}")

    @staticmethod
    def upsert(model, sid, source, row, **fields):
        raw = {k: v for k, v in row.items() if v is not None}
        obj, created = model.objects.update_or_create(
            source_id=sid, defaults={'source_file': source, 'raw': raw,
                                     'is_active': _active(row), **fields})
        return obj, created

    # ─────────────── MHD-001: Eneo ───────────────

    def import_001(self, wb):
        from crops.models import Zone

        def aez(sid, row, source):
            name = row.get('ecological_zone_sw') or sid
            zone = Zone.objects.filter(zone_name__iexact=name).first()
            _, created = self.upsert(
                Aez, sid, source, row, name_sw=name,
                rainfall_band_mm=row.get('rainfall_band_mm') or '',
                altitude_band_m=row.get('altitude_band_m') or '',
                planting_window_sw=row.get('planting_window_sw') or '',
                harvest_window_sw=row.get('harvest_window_sw') or '',
                **({'zone': zone} if zone else {}))
            return created

        def ward(sid, row, source):
            if not row.get('ward_name') or not row.get('district_name') or not row.get('region_name'):
                raise ValueError('ward_name, district_name na region_name zinahitajika')
            aez_id = row.get('primary_aez_id')
            aez_obj = Aez.objects.filter(source_id=aez_id).first() if aez_id else None
            if aez_id and aez_obj is None:
                self.r.warnings.append(f"{source} {sid}: AEZ '{aez_id}' haipo kwenye AEZ_Master")
            lat, lng = _float(row.get('latitude')), _float(row.get('longitude'))
            if lat is not None and not (-12.5 <= lat <= -0.9) or lng is not None and not (29 <= lng <= 41):
                self.r.warnings.append(f"{source} {sid}: coordinates ({lat}, {lng}) ziko nje ya Tanzania")
            _, created = self.upsert(
                WardLocation, sid, source, row,
                region_name=row['region_name'], district_name=row['district_name'],
                council_name=row.get('council_name') or '', division_name=row.get('division_name') or '',
                ward_name=row['ward_name'], ward_code=str(row.get('ward_code') or ''),
                latitude=lat, longitude=lng, aez=aez_obj,
                ecological_zone_sw=row.get('ecological_zone_sw') or '',
                rainfall_band_mm=row.get('rainfall_band_mm') or '',
                altitude_band_m=row.get('altitude_band_m') or '',
                planting_window_sw=row.get('planting_window_sw') or '',
                harvest_window_sw=row.get('harvest_window_sw') or '',
                search_key=row.get('location_search_key') or '')
            return created

        def synonym(sid, row, source):
            loc = WardLocation.objects.filter(source_id=row.get('location_id')).first()
            if loc is None:
                raise ValueError(f"location_id '{row.get('location_id')}' haipo")
            term = (row.get('input_term') or '').strip().lower()
            if not term:
                raise ValueError('input_term tupu')
            _, created = self.upsert(LocationSynonym, sid, source, row, term=term, location=loc)
            return created

        def rule(sid, row, source):
            _, created = self.upsert(
                LocationRule, sid, source, row, name_sw=row.get('rule_name_sw') or sid,
                trigger_sw=row.get('trigger_sw') or '', action_sw=row.get('action_sw') or '',
                farmer_response_sw=row.get('farmer_response_sw') or '',
                priority=int(_float(row.get('priority')) or 1))
            return created

        code = 'MHD-001'
        self.rows(wb, code, 'AEZ_Master', 'Kanda za kilimo (AEZ)', 'aez_id', aez)
        self.rows(wb, code, 'Production_Ward_Location_Master', 'Kata', 'location_id', ward)
        self.rows(wb, code, 'Production_Location_Synonyms', 'Visawe vya maeneo', 'synonym_id', synonym)
        self.rows(wb, code, 'Production_Location_Rules', 'Kanuni za eneo', 'rule_id', rule)

        # QA: kisawe kimoja kinachoelekeza kata nyingi ni cha wilaya/mkoa, si cha kata.
        from django.db.models import Count
        multi = (LocationSynonym.objects.values('term').annotate(n=Count('location', distinct=True))
                 .filter(n__gt=1))
        for m in multi:
            self.r.warnings.append(
                f"MHD-001 kisawe '{m['term']}' kinaelekeza kata {m['n']} tofauti — bot itakitumia "
                "kutambua wilaya/mkoa tu, si kata mahsusi")

    # ─────────────── MHD-003A: Mbegu (Release 1, 2, 3) ───────────────

    def generic_rules(self, wb, code, sheet, module):
        def rule(sid, row, source):
            _, created = self.upsert(
                AdvisoryRule, sid, source, row, module=module,
                name_sw=row.get('jina_la_sheria') or sid, trigger=row.get('trigger') or '',
                action=row.get('kitendo_cha_mfumo') or row.get('hatua_ya_AI') or '',
                farmer_message_sw=row.get('ujumbe_wa_mkulima') or '',
                priority=int(_float(row.get('kipaumbele')) or 1))
            return created
        self.rows(wb, code, sheet, 'Kanuni za ushauri', 'rule_id', rule)

    def explain_templates(self, wb, code, module):
        def tpl(sid, row, source):
            _, created = self.upsert(
                ExplainTemplate, sid, source, row, module=module,
                situation=row.get('hali') or row.get('decision_output') or row.get('rotation_decision') or '',
                template_sw=row.get('template_ya_jibu') or '', fields=row.get('fields_zinazotumika') or '')
            return created
        self.rows(wb, code, 'Explainability_Templates', 'Violezo vya maelezo', 'template_id', tpl)

    def import_003a(self, wb):
        code = 'MHD-003A'
        names = {ws.title for ws in wb.worksheets}

        if 'Sajili_Aina_Mbegu_Mahindi' in names:
            def variety(sid, row, source):
                _, created = self.upsert(
                    VarietyRegistry, sid, source, row, crop=_crop(row.get('jina_la_zao')),
                    name=row.get('jina_la_variety') or sid,
                    registrant=row.get('registrant_au_applicant') or '',
                    registration_year=str(row.get('mwaka_wa_usajili') or '')[:40],
                    authority=row.get('mamlaka_ya_usajili') or '',
                    record_status=(row.get('hali_ya_record') or '')[:200])
                return created

            def synonym(sid, row, source):
                v = VarietyRegistry.objects.filter(source_id=row.get('kitambulisho_variety')).first()
                if v is None:
                    raise ValueError(f"kitambulisho_variety '{row.get('kitambulisho_variety')}' haipo")
                _, created = self.upsert(VarietySynonym, sid, source, row, crop=v.crop,
                                         term=str(row.get('neno_la_mkulima') or '').strip().lower(), variety=v)
                return created

            self.rows(wb, code, 'Sajili_Aina_Mbegu_Mahindi', 'Aina za mbegu (sajili)', 'kitambulisho_variety', variety)
            self.rows(wb, code, 'Visawe_Aina_Mbegu', 'Visawe vya mbegu', 'synonym_id', synonym)
            self.generic_rules(wb, code, 'Sheria_AI_za_Sajili', 'seed')

        if 'Agronomy_Profile_Mahindi' in names:
            def agronomy(sid, row, source):
                v = VarietyRegistry.objects.filter(source_id=row.get('kitambulisho_variety_release1')).first()
                if v is None:
                    self.r.warnings.append(f"{source} {sid}: variety '{row.get('kitambulisho_variety_release1')}' "
                                           "haipo kwenye sajili (Release 1) — pakia Release 1 kwanza")
                dmin, dmax = _span(row.get('siku_za_kukomaa'))
                amin, amax = _span(row.get('mwinuko_unaofaa'))
                if amin is not None and (amin < 100 or amax < 100):
                    amin = amax = None          # si mita (mf. namba ya msimbo)
                _, created = self.upsert(
                    VarietyAgronomy, sid, source, row, crop=_crop(row.get('jina_la_zao')), variety=v,
                    name=row.get('jina_la_variety') or (v.name if v else sid),
                    company=row.get('kampuni_au_taasisi') or '', seed_type=row.get('aina_ya_mbegu') or '',
                    grain=(row.get('rangi_ya_punje') or '')[:200],
                    maturity_class=(row.get('daraja_la_ukomavu') or '')[:60],
                    maturity_days_min=dmin, maturity_days_max=dmax,
                    yield_text=(row.get('uwezo_wa_mavuno') or '')[:200],
                    altitude_text=(row.get('mwinuko_unaofaa') or '')[:300], altitude_min=amin, altitude_max=amax,
                    rainfall_text=(row.get('mazingira_ya_mvua') or '')[:300],
                    aez_codes=_list(row.get('AEZ_zinazofaa')),
                    priority_areas=row.get('mikoa_au_maeneo_ya_kipaumbele') or '',
                    disease_tolerance=row.get('magonjwa_yanayostahimili') or '',
                    drought_tolerance=row.get('uvumilivu_wa_ukame_au_joto') or '',
                    farmer_advice=row.get('ushauri_wa_mkulima') or '', ai_logic=row.get('logic_ya_AI') or '')
                return created

            self.rows(wb, code, 'Agronomy_Profile_Mahindi', 'Sifa za kilimo za mbegu', 'kitambulisho_profile', agronomy)
            self.generic_rules(wb, code, 'Sheria_AI_Agronomy', 'seed')

        if 'AI_Decision_Engine' in names:
            def decision(sid, row, source):
                aez = [a for a in _list(row.get('AEZ_inayotumika')) if a.upper().startswith('AEZ')]
                prio = [row.get(f'variety_kipaumbele_{i}') for i in (1, 2, 3)]
                known = {_variety_key(a.name) for a in VarietyAgronomy.objects.all()}
                prio = [p for p in prio if p and _variety_key(p) in known]
                _, created = self.upsert(
                    SeedDecisionRule, sid, source, row, crop=_crop(row.get('jina_la_zao')),
                    location_condition=row.get('hali_ya_eneo_kutoka_MHD001') or '', aez_codes=aez,
                    rain_condition=(row.get('mvua_au_msimu') or '')[:200],
                    altitude_condition=(row.get('mwinuko') or '')[:200],
                    farmer_criterion=(row.get('kigezo_cha_mkulima') or '')[:300],
                    priority_varieties=prio, ai_action=row.get('hatua_ya_AI') or '',
                    farmer_message_sw=row.get('ujumbe_wa_mkulima') or '',
                    reason=row.get('sababu_ya_pendekezo') or '', confidence=_float(row.get('confidence_score')))
                return created

            def intent(sid, row, source):
                _, created = self.upsert(
                    SeedIntent, sid, source, row, phrases=_list(row.get('maneno_ya_mkulima')),
                    intent_code=row.get('intent_iliyotambuliwa') or sid,
                    follow_up_question=row.get('swali_la_kufuata') or '',
                    suggested=_list(row.get('variety_au_hatua_inayopendekezwa')),
                    short_answer=row.get('jibu_fupi_la_AI') or '', confidence=_float(row.get('confidence_score')))
                return created

            def band(sid, row, source):
                _, created = self.upsert(
                    AdvisoryConfidenceBand, sid, source, row, module='seed', label=row.get('hali') or sid,
                    min_score=_float(row.get('score_min')) or 0, max_score=_float(row.get('score_max')) or 1,
                    meaning=row.get('maana') or '', ai_action=row.get('hatua_ya_AI') or '')
                return created

            self.rows(wb, code, 'AI_Decision_Engine', 'Kanuni za uamuzi wa mbegu', 'rule_id', decision)
            self.rows(wb, code, 'Farmer_Intent_Mapping', 'Malengo ya mkulima', 'intent_id', intent)
            self.explain_templates(wb, code, 'seed')
            self.rows(wb, code, 'Confidence_Engine', 'Viwango vya uhakika', 'confidence_id', band)
            # QA: variety zilizotajwa kwenye kanuni lakini hazina sifa za kilimo (Release 2)
            known = {_variety_key(a.name) for a in VarietyAgronomy.objects.all()}
            for r in _read_sheet(wb['AI_Decision_Engine']) if 'AI_Decision_Engine' in names else []:
                for i in (1, 2, 3):
                    v = r.get(f'variety_kipaumbele_{i}')
                    if v and _looks_like_variety(v) and _variety_key(v) not in known:
                        self.r.warnings.append(f"{code} {r.get('rule_id')}: '{v}' haina sifa za kilimo "
                                               "(Release 2) — haitapendekezwa")
            for r in _read_sheet(wb['Farmer_Intent_Mapping']) if 'Farmer_Intent_Mapping' in names else []:
                for v in _list(r.get('variety_au_hatua_inayopendekezwa')):
                    if _looks_like_variety(v) and _variety_key(v) not in known:
                        self.r.warnings.append(f"{code} {r.get('intent_id')}: '{v}' haina sifa za kilimo "
                                               "(Release 2) — haitapendekezwa")


def _release_order(wb):
    """MHD-003A ina workbooks 3 zenye msimbo mmoja: sajili → agronomy → uamuzi."""
    names = {ws.title for ws in wb.worksheets}
    if 'Sajili_Aina_Mbegu_Mahindi' in names:
        return 1
    if 'Agronomy_Profile_Mahindi' in names:
        return 2
    return 3


# Mpangilio wa import: eneo kwanza (wengine wanategemea AEZ).
WORKBOOKS = [
    ('MHD-001', 'import_001'),
    ('MHD-003A', 'import_003a'),
]
SUPPORTED_CODES = [code for code, _ in WORKBOOKS]


def import_files(files, dry_run=False):
    """files: paths au UploadedFile. Inarudisha ImportReport."""
    import openpyxl

    report = ImportReport(dry_run)
    books = {}
    for f in files:
        code = workbook_code(getattr(f, 'name', f))
        if code not in SUPPORTED_CODES:
            report.warnings.append(f"'{os.path.basename(str(getattr(f, 'name', f)))}' bado haina importer — imerukwa")
            continue
        books.setdefault(code, []).append(openpyxl.load_workbook(f, read_only=True, data_only=True))
    report.workbooks = sorted(books)
    imp = _Importer(report)
    try:
        with transaction.atomic():
            for code, method in WORKBOOKS:
                for wb in sorted(books.get(code, []), key=_release_order):
                    getattr(imp, method)(wb)
            if report.failure_ratio > MAX_FAILURE_RATIO:
                report.rolled_back = True
                raise _Rollback()
            if dry_run:
                raise _Rollback()
    except _Rollback:
        pass
    from .location import clear_cache
    clear_cache()
    return report
