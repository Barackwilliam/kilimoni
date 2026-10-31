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
    CropFamily, RotationCompatibility, RotationRule, RotationSequence,
    SoilConstraint, SoilProperty, SoilRanking, SoilSuitability, SoilSynonym, SoilType,
    AezAlias, ClimateRisk, CropCalendar, PlantingRule, SeasonProfile,
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

    # ─────────────── MHD-004: Udongo (R1, R2, R3) ───────────────

    def import_004(self, wb):
        code = 'MHD-004'
        names = {ws.title for ws in wb.worksheets}

        def soil_ref(sid, where):
            soil = SoilType.objects.filter(source_id=sid).first() if sid else None
            if sid and soil is None:
                self.r.warnings.append(f"{where}: udongo '{sid}' haupo kwenye Soil_Master_Registry (R1)")
            return soil

        if 'Soil_Master_Registry' in names:
            def wrb(sid, row, source):
                _, created = self.upsert(
                    SoilType, sid, source, row, kind='wrb', wrb_name=row.get('jina_la_udongo_WRB') or '',
                    name_sw=row.get('jina_la_kiswahili') or sid, farmer_name=row.get('jina_la_kawaida_kwa_mkulima') or '',
                    description_sw=row.get('sifa_kwa_lugha_rahisi') or '',
                    environment_sw=row.get('mazingira_ambako_hupatikana_mara_nyingi') or '',
                    ai_usage=row.get('matumizi_katika_Mkulima_AI') or '', caution_sw=row.get('tahadhari_ya_awali') or '')
                return created

            def local(sid, row, source):
                _, created = self.upsert(
                    SoilType, sid, source, row, kind='local', wrb_name='',
                    name_sw=row.get('jina_la_kiswahili') or sid, farmer_name=row.get('jina_la_udongo_kawaida') or '',
                    description_sw=row.get('sifa_rahisi') or '', ai_usage=row.get('matumizi_katika_AI') or '')
                return created

            def synonym(sid, row, source):
                soil = soil_ref(row.get('soil_id_inayolingana'), f"{source} {sid}")
                if soil is None:
                    raise ValueError('udongo haupo')
                _, created = self.upsert(SoilSynonym, sid, source, row,
                                         term=str(row.get('neno_la_mkulima') or '').strip().lower(), soil=soil)
                return created

            self.rows(wb, code, 'Soil_Master_Registry', 'Aina za udongo', 'soil_id', wrb)
            self.rows(wb, code, 'Soil_Local_Texture_Registry', 'Aina za udongo', 'soil_local_id', local)
            self.rows(wb, code, 'Soil_Synonyms', 'Visawe vya udongo', 'synonym_id', synonym)
            self.generic_rules(wb, code, 'Soil_Decision_Rules', 'soil')

        if 'Soil_Property_Profile' in names:
            def prop(sid, row, source):
                soil = soil_ref(row.get('soil_id_release1'), f"{source} {sid}")
                if soil is None:
                    raise ValueError('udongo haupo')
                _, created = self.upsert(
                    SoilProperty, sid, source, row, soil=soil, texture=(row.get('texture_kawaida') or '')[:300],
                    drainage=(row.get('drainage_kawaida') or '')[:300],
                    water_holding=(row.get('uwezo_wa_kushika_maji') or '')[:100],
                    ph_tendency=(row.get('pH_tendency') or '')[:100],
                    organic_matter=(row.get('organic_matter_tendency') or '')[:100],
                    fertility=(row.get('fertility_rating_awali') or '')[:100],
                    main_challenges=row.get('changamoto_kuu') or '',
                    management=row.get('soil_management_recommendation') or '',
                    advisory_sw=row.get('AI_advisory_kiswahili') or '', confidence=_float(row.get('confidence_score')))
                return created

            def constraint(sid, row, source):
                _, created = self.upsert(
                    SoilConstraint, sid, source, row, name_sw=row.get('jina_la_changamoto') or sid,
                    farmer_signs_sw=row.get('dalili_kwa_mkulima') or '',
                    soil_groups=_list(row.get('soil_groups_husika')),
                    first_action_sw=row.get('hatua_ya_awali') or '', message_sw=row.get('ujumbe_wa_AI') or '')
                return created

            self.rows(wb, code, 'Soil_Property_Profile', 'Sifa za udongo', 'soil_property_id', prop)
            self.rows(wb, code, 'Soil_Constraint_Master', 'Changamoto za udongo', 'constraint_id', constraint)
            self.generic_rules(wb, code, 'Soil_Property_AI_Rules', 'soil')

        if 'Soil_Crop_Suitability_Master' in names:
            def suit(sid, row, source):
                soil = soil_ref(row.get('soil_id'), f"{source} {sid}")
                if soil is None:
                    raise ValueError('udongo haupo')
                _, created = self.upsert(
                    SoilSuitability, sid, source, row, soil=soil, crop=_crop(row.get('jina_la_zao')),
                    score=int(_float(row.get('suitability_score')) or 0) or None,
                    rating=(row.get('suitability_rating') or '')[:40], ai_action=row.get('hatua_ya_AI') or '',
                    reason_sw=row.get('sababu_kuu') or '', limitations_sw=row.get('vikwazo_vinavyoweza_kutokea') or '',
                    improvements_sw=row.get('maboresho_kabla_ya_kupanda') or '')
                return created

            def rank(sid, row, source):
                soil = SoilType.objects.filter(source_id=row.get('soil_id')).first()
                if soil is None:
                    self.r.warnings.append(f"{source} {sid}: udongo '{row.get('soil_id')}' "
                                           f"({row.get('jina_la_udongo_WRB')}) haupo kwenye R1 — utaonyeshwa kwa jina tu")
                _, created = self.upsert(
                    SoilRanking, sid, source, row, soil=soil, crop=_crop(row.get('jina_la_zao')),
                    soil_wrb=row.get('jina_la_udongo_WRB') or '',
                    score=int(_float(row.get('suitability_score')) or 0) or None,
                    rank=int(_float(row.get('rank_kwa_zao')) or 0) or None)
                return created

            self.rows(wb, code, 'Soil_Crop_Suitability_Master', 'Ufaafu wa udongo kwa mazao', 'suitability_id', suit)
            self.rows(wb, code, 'Crop_Top_Soil_Ranking', 'Udongo bora kwa mazao', 'rank_id', rank)
            self.generic_rules(wb, code, 'Soil_Crop_AI_Rules', 'soil')
            self.explain_templates(wb, code, 'soil')

    # ─────────────── MHD-006: Wakati wa kupanda (R1, R2, R3) ───────────────

    def _aez(self, row, ext_col='aez_id', sw_col=None, en_col='aez_name'):
        ext = row.get(ext_col)
        if not ext:
            return '', None
        alias = AezAlias.objects.filter(dataset='MHD-006', external_id=ext).first()
        if alias:
            return ext, alias.aez
        return ext, map_aez('MHD-006', ext, row.get(sw_col) if sw_col else '', row.get(en_col) or '')

    def import_006(self, wb):
        code = 'MHD-006'
        names = {ws.title for ws in wb.worksheets}

        if 'National_Crop_Calendar_Master' in names:
            def zone(sid, row, source):
                map_aez(code, sid, row.get('jina_la_kiswahili') or '', row.get('aez_name_en') or '',
                        extra={'rainfall_pattern': (row.get('rainfall_pattern') or '')[:120],
                               'rainfall_months': (row.get('rainfall_months_general') or '')[:120]})
                return None

            def calendar(sid, row, source):
                ext, aez = self._aez(row)
                crop = _crop(row.get('jina_la_zao'))
                if crop is None:
                    self.r.warnings.append(f"{source} {sid}: zao '{row.get('jina_la_zao')}' halipo kwenye Mazao")
                _, created = self.upsert(
                    CropCalendar, sid, source, row, crop=crop, ext_aez_id=ext, aez=aez,
                    farming_system=(row.get('farming_system') or '')[:200],
                    main_season=(row.get('main_season') or '')[:100],
                    secondary_season=(row.get('secondary_or_irrigation_season') or '')[:200],
                    early_window=row.get('early_planting_window') or '',
                    normal_window=row.get('normal_planting_window') or '',
                    late_window=row.get('late_planting_window') or '',
                    harvest_window=row.get('expected_harvest_window') or '',
                    min_days=int(_float(row.get('minimum_days')) or 0) or None,
                    avg_days=int(_float(row.get('average_days')) or 0) or None,
                    max_days=int(_float(row.get('maximum_days')) or 0) or None,
                    priority=(row.get('recommendation_priority') or '')[:30],
                    confidence=_float(row.get('confidence_score')),
                    advisory_sw=row.get('AI_calendar_advisory') or '', explain_sw=row.get('explainability_text') or '')
                return created

            self.rows(wb, code, 'AEZ_Calendar_Zones', 'Kanda za kalenda', 'aez_id', zone)
            self.rows(wb, code, 'National_Crop_Calendar_Master', 'Kalenda za mazao', 'calendar_id', calendar)
            self.generic_rules(wb, code, 'Calendar_AI_Rules', 'planting')
            self.explain_templates(wb, code, 'planting')

        if 'AEZ_Seasonal_Master' in names:
            def season(sid, row, source):
                ext, aez = self._aez(row, sw_col='jina_la_kiswahili', en_col='aez_name_en')
                if not AezAlias.objects.filter(dataset=code, external_id=ext).exists():
                    aez = map_aez(code, ext, row.get('jina_la_kiswahili') or '', row.get('aez_name_en') or '')
                _, created = self.upsert(
                    SeasonProfile, sid, source, row, ext_aez_id=ext, aez=aez,
                    name_sw=row.get('jina_la_kiswahili') or '', rainfall_pattern=(row.get('rainfall_pattern') or '')[:120],
                    onset_window=row.get('rainfall_onset_window') or '',
                    cessation_window=row.get('rainfall_cessation_window') or '',
                    peak_months=row.get('peak_rainfall_months') or '',
                    lgp_min=int(_float(row.get('lgp_min_days')) or 0) or None,
                    lgp_avg=int(_float(row.get('lgp_avg_days')) or 0) or None,
                    lgp_max=int(_float(row.get('lgp_max_days')) or 0) or None,
                    reliability=(row.get('seasonal_reliability') or '')[:40],
                    dry_spell_risk=(row.get('dry_spell_risk') or '')[:40],
                    advisory_sw=row.get('AI_seasonal_advisory') or '')
                return created

            def by_aez(field_map):
                def handler(sid, row, source):
                    ext = row.get('aez_id')
                    sp = SeasonProfile.objects.filter(ext_aez_id=ext).first()
                    if sp is None:
                        raise ValueError(f"hakuna AEZ_Seasonal_Master ya {ext}")
                    for model_field, col in field_map.items():
                        setattr(sp, model_field, row.get(col) or '')
                    sp.raw = {**sp.raw, sid: {k: v for k, v in row.items() if v is not None}}
                    sp.save()
                    return False
                return handler

            def risk(sid, row, source):
                ext, aez = self._aez(row)
                _, created = self.upsert(
                    ClimateRisk, sid, source, row, ext_aez_id=ext, aez=aez,
                    risk_type=(row.get('risk_type') or '')[:60], risk_level=(row.get('risk_level') or '')[:40],
                    risk_window=(row.get('risk_window') or '')[:120], farmer_message_sw=row.get('farmer_message_sw') or '')
                return created

            self.rows(wb, code, 'AEZ_Seasonal_Master', 'Misimu ya kanda', 'season_profile_id', season)
            self.rows(wb, code, 'Rainfall_Onset_Intelligence', 'Misimu ya kanda', 'onset_id',
                      by_aez({'onset_message_sw': 'farmer_message_sw', 'onset_trigger_sw': 'reliable_planting_trigger'}))
            self.rows(wb, code, 'Rainfall_Cessation_Intelligence', 'Misimu ya kanda', 'cessation_id',
                      by_aez({'cessation_message_sw': 'farmer_message_sw'}))
            self.rows(wb, code, 'Length_Growing_Period', 'Misimu ya kanda', 'lgp_id',
                      by_aez({'lgp_logic': 'variety_maturity_logic'}))
            self.rows(wb, code, 'Climate_Risk_Intelligence', 'Hatari za hali ya hewa', 'risk_id', risk)
            self.generic_rules(wb, code, 'AI_Seasonal_Rules', 'planting')
            self.explain_templates(wb, code, 'planting')

        if 'Planting_Decision_Engine' in names:
            sheets = [
                ('Planting_Decision_Engine', 'decision_rule_id', 'decision', 'decision_output', 'input_condition'),
                ('Planting_Eligibility_Rules', 'eligibility_id', 'eligibility', 'decision_output', 'conditions_required'),
                ('Planting_Window_Validation', 'window_rule_id', 'window', 'AI_decision', 'condition'),
                ('Variety_Selection_Logic', 'variety_logic_id', 'variety_logic', 'planting_context', 'lgp_condition'),
                ('Alternative_Crop_Rules', 'alternative_id', 'alternative', '', 'trigger_condition'),
                ('Irrigation_Override_Rules', 'irrigation_rule_id', 'irrigation', 'AI_decision', 'condition'),
                ('Climate_Exception_Rules', 'exception_id', 'climate_exception', 'AI_decision', 'trigger'),
                ('Rule_Precedence', 'precedence_id', 'precedence', 'rule_group', 'conflict_resolution'),
            ]
            for sheet, id_col, kind, dec_col, cond_col in sheets:
                def handler(sid, row, source, kind=kind, dec_col=dec_col, cond_col=cond_col):
                    ext, aez = self._aez(row) if row.get('aez_id') else ('', None)
                    extra = {k: v for k, v in row.items() if v is not None and k not in (
                        'farmer_message_sw', 'hadhi_ya_CMS', 'source_ids', 'toleo', 'tarehe')}
                    _, created = self.upsert(
                        PlantingRule, sid, source, row, kind=kind,
                        decision=(row.get(dec_col) or '')[:60] if dec_col else '',
                        condition=row.get(cond_col) or '', farmer_message_sw=row.get('farmer_message_sw') or '',
                        ext_aez_id=ext or '', aez=aez, extra=extra,
                        confidence=_float(row.get('confidence_score')),
                        priority=int(_float(row.get('priority_level') or row.get('priority')
                                            or row.get('priority_order')) or 0))
                    return created
                self.rows(wb, code, sheet, 'Kanuni za kupanda', id_col, handler)
            self.explain_templates_sheet(wb, code, 'Decision_Explainability', 'planting')

        if 'Crop_Rotation_Family_Master' in names:
            def family(sid, row, source):
                name = row.get('jina_la_zao') or ''
                _, created = self.upsert(
                    CropFamily, sid, source, row, crop=_crop(name), crop_name=name,
                    category=(row.get('crop_category') or '')[:60], rotation_group=(row.get('rotation_group') or '')[:60],
                    botanical_family=(row.get('botanical_family') or '')[:60],
                    nutrient_role=(row.get('nutrient_role') or '')[:60], note=row.get('rotation_note') or '')
                return created

            def compat(sid, row, source):
                prev, nxt = row.get('previous_crop') or '', row.get('next_crop') or ''
                _, created = self.upsert(
                    RotationCompatibility, sid, source, row, previous_name=prev, next_name=nxt,
                    previous_crop=_crop(prev), next_crop=_crop(nxt),
                    score=int(_float(row.get('compatibility_score')) or 0) if row.get('compatibility_score') is not None else None,
                    rating=(row.get('compatibility_rating') or '')[:30], ai_action=row.get('AI_action') or '',
                    benefit_logic=row.get('rotation_benefit_logic') or '', risk_logic=row.get('rotation_risk_logic') or '')
                return created

            def sequence(sid, row, source):
                ext, aez = self._aez(row)
                seasons = [row.get(c) for c in ('year_1_or_season_1', 'year_2_or_season_2', 'year_3_or_season_3')
                           if row.get(c)]
                _, created = self.upsert(
                    RotationSequence, sid, source, row, ext_aez_id=ext or '', aez=aez,
                    system=(row.get('rotation_system') or sid)[:200], seasons=seasons,
                    recommended_for=(row.get('recommended_for') or '')[:200],
                    main_benefit=row.get('main_benefit') or '', advisory_sw=row.get('AI_advisory_sw') or '')
                return created

            def soil_rule(sid, row, source):
                _, created = self.upsert(
                    RotationRule, sid, source, row, kind='soil',
                    condition=(row.get('soil_condition_from_MHD004') or '')[:200],
                    recommended=row.get('recommended_rotation_action') or '', avoid=row.get('avoid_rotation_action') or '',
                    farmer_message_sw=row.get('farmer_message_sw') or '')
                return created

            def break_rule(sid, row, source):
                _, created = self.upsert(
                    RotationRule, sid, source, row, kind='break', condition=(row.get('risk_group') or '')[:200],
                    recommended=row.get('recommended_break_crop_group') or '', avoid=row.get('avoid_following') or '',
                    min_break=(row.get('minimum_break_period') or '')[:100],
                    farmer_message_sw=row.get('farmer_message_sw') or '')
                return created

            self.rows(wb, code, 'Crop_Rotation_Family_Master', 'Familia za mazao', 'crop_id', family)
            self.rows(wb, code, 'Rotation_Compatibility_Master', 'Ulinganifu wa mzunguko', 'compatibility_id', compat)
            self.rows(wb, code, 'Rotation_Sequence_Master', 'Mifuatano ya mzunguko', 'sequence_id', sequence)
            self.rows(wb, code, 'Soil_Fertility_Rotation_Rules', 'Kanuni za mzunguko', 'soil_rotation_id', soil_rule)
            self.rows(wb, code, 'Pest_Disease_Break_Rules', 'Kanuni za mzunguko', 'break_rule_id', break_rule)
            self.generic_rules(wb, code, 'Rotation_AI_Rules', 'rotation')
            self.explain_templates(wb, code, 'rotation')


    def qa_006(self):
        code = 'MHD-006'
        # QA: AEZ za MHD-006 zina namba tofauti na MHD-001 — onyesha ulinganisho
        for alias in AezAlias.objects.filter(dataset=code):
            if alias.aez is None:
                self.r.warnings.append(
                    f"{code} {alias.external_id} ({alias.name_sw or alias.name_en}): haijaunganishwa na AEZ ya MHD-001 "
                    "— weka kwenye dashboard (Maeneo na Kanda); data yake haitatumika mpaka hapo")
            elif alias.aez.source_id != alias.external_id:
                self.r.warnings.append(
                    f"{code} {alias.external_id} ({alias.name_sw or alias.name_en}) ≠ MHD-001 {alias.external_id}; "
                    f"imeunganishwa kwa jina na MHD-001 {alias.aez.source_id} ({alias.aez.name_sw}) — thibitisha")

    def explain_templates_sheet(self, wb, code, sheet, module):
        def tpl(sid, row, source):
            _, created = self.upsert(
                ExplainTemplate, sid, source, row, module=module,
                situation=row.get('decision_output') or row.get('hali') or '',
                template_sw=row.get('template_ya_jibu') or '', fields=row.get('fields_zinazotumika') or '')
            return created
        self.rows(wb, code, sheet, 'Violezo vya maelezo', 'template_id', tpl)

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
    """
    Workbooks zenye msimbo mmoja zina releases: MHD-003A sajili → agronomy →
    uamuzi; MHD-006 kalenda → msimu → planting engine → mzunguko.
    """
    names = {ws.title for ws in wb.worksheets}
    for i, sheet in enumerate(('Sajili_Aina_Mbegu_Mahindi', 'Agronomy_Profile_Mahindi', 'AI_Decision_Engine',
                               'Soil_Master_Registry', 'Soil_Property_Profile', 'Soil_Crop_Suitability_Master',
                               'National_Crop_Calendar_Master', 'AEZ_Seasonal_Master',
                               'Planting_Decision_Engine', 'Crop_Rotation_Family_Master'), 1):
        if sheet in names:
            return i
    return 99


# ─────────────── AEZ za MHD-006 → AEZ za MHD-001 ───────────────

AEZ_STOP = {'kanda', 'ya', 'za', 'na', 'wa', 'yenye', 'ukanda', 'nusu', 'wastani', 'the', 'zone', 'belt'}


def _aez_tokens(name):
    words = set(re.findall(r'[a-z]+', (name or '').lower())) - AEZ_STOP
    return {'kame' if w == 'ukame' else w for w in words}


def apply_alias(alias):
    """Baada ya mteja kubadilisha ulinganisho wa AEZ: sasisha records zote za kanda hiyo."""
    if alias.dataset != 'MHD-006':
        return 0
    n = 0
    for model in (CropCalendar, SeasonProfile, ClimateRisk, PlantingRule):
        n += model.objects.filter(ext_aez_id=alias.external_id).update(aez=alias.aez)
    return n


def map_aez(dataset, ext_id, name_sw='', name_en='', report=None, extra=None):
    """Unganisha AEZ ya dataset nyingine na AEZ ya MHD-001 kwa majina (si kwa namba)."""
    alias = AezAlias.objects.filter(dataset=dataset, external_id=ext_id).first()
    if alias and not alias.auto_matched:
        return alias.aez                       # mteja ameweka mwenyewe — usibadilishe
    tokens = _aez_tokens(name_sw) or _aez_tokens(name_en)
    scored = []
    for a in Aez.objects.all():
        t = _aez_tokens(a.name_sw)
        common = tokens & t
        if common:
            scored.append((len(common) / len(tokens | t), a))
    scored.sort(key=lambda x: -x[0])
    match = None
    if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        match = scored[0][1]
    alias, _ = AezAlias.objects.update_or_create(
        dataset=dataset, external_id=ext_id,
        defaults={'name_sw': name_sw or (alias.name_sw if alias else ''),
                  'name_en': name_en or (alias.name_en if alias else ''),
                  'aez': match, 'auto_matched': True, **(extra or {})})
    return match


# Mpangilio wa import: eneo kwanza (wengine wanategemea AEZ).
WORKBOOKS = [
    ('MHD-001', 'import_001'),
    ('MHD-003A', 'import_003a'),
    ('MHD-004', 'import_004'),
    ('MHD-006', 'import_006'),
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
            if 'MHD-006' in books:
                imp.qa_006()
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
