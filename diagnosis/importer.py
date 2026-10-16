"""
Import ya Excel za MHD-007 (A/C/E/F) kwenda kwenye tables za diagnosis.

Inafuata MHD-007F/04_CMS_Import_Spec:
  - Upsert kwa Primary_Key (source_id) — kuimport tena kunasasisha, hakuongezi nakala.
  - Wadudu kwanza, kisha dalili, kisha rules zinazowategemea.
  - Batch nzima inarudishwa nyuma (rollback) makosa yakizidi 2%.

Dry run inaendesha import halisi ndani ya transaction kisha inairudisha
nyuma, hivyo ripoti ya preview inasema ukweli (kama dataset_ai.py).

Matumizi:
    from diagnosis.importer import import_mhd007
    report = import_mhd007(['MHD-007A_....xlsx', ...], dry_run=True)
"""
import datetime
import os
import re
from collections import OrderedDict

from django.db import transaction

from .models import (
    ConfidenceRule, DecisionRule, ErrorHandlingRule, ExplainabilityRecord,
    FarmerMessageTemplate, FollowupQuestion, Pest, RecommendationRule,
    SafetyRule, Symptom, SymptomDiagnosisMap, Treatment, TreatmentProtocolStep,
)

MAX_FAILURE_RATIO = 0.02
WORKBOOK_CODES = ('MHD-007A', 'MHD-007C', 'MHD-007E', 'MHD-007F')


class _Rollback(Exception):
    pass


class ImportReport:
    def __init__(self, dry_run):
        self.dry_run = dry_run
        self.counts = OrderedDict()   # label -> {'created': n, 'updated': n}
        self.warnings = []
        self.errors = []
        self.rows_total = 0
        self.workbooks = []
        self.rolled_back = False

    def count(self, label, created):
        c = self.counts.setdefault(label, {'created': 0, 'updated': 0})
        c['created' if created else 'updated'] += 1

    @property
    def failure_ratio(self):
        return len(self.errors) / self.rows_total if self.rows_total else 0

    def as_text(self):
        lines = [('DRY RUN — hakuna kilichohifadhiwa' if self.dry_run
                  else 'IMPORT') + f" ({', '.join(self.workbooks) or 'hakuna workbook'})"]
        for label, c in self.counts.items():
            lines.append(f"  {label:<28} mpya {c['created']:>3}   zilizosasishwa {c['updated']:>3}")
        for w in self.warnings:
            lines.append(f"  ⚠ {w}")
        for e in self.errors:
            lines.append(f"  ✗ {e}")
        if self.rolled_back:
            lines.append(f"  ROLLBACK: makosa {len(self.errors)}/{self.rows_total} "
                         f"yamezidi {MAX_FAILURE_RATIO:.0%} — hakuna kilichohifadhiwa.")
        return '\n'.join(lines)


# ─────────────────────────── Kusoma Excel ───────────────────────────

def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def _read_sheet(ws):
    """Rudisha list ya dict (header = row ya kwanza isiyo tupu)."""
    rows = [r for r in ws.iter_rows(values_only=True)
            if any(c not in (None, '') for c in r)]
    if not rows:
        return []
    header = [str(h).strip() if h is not None else '' for h in rows[0]]
    out = []
    for r in rows[1:]:
        rec = {h: _clean(v) for h, v in zip(header, r) if h}
        if any(v is not None for v in rec.values()):
            out.append(rec)
    return out


def _find_sheet(wb, name):
    """Tafuta sheet kwa jina bila namba ya mbele: 'Pest_Master' → '01_Pest_Master'."""
    for ws in wb.worksheets:
        if re.sub(r'^\d+_', '', ws.title).lower() == name.lower():
            return ws
    return None


def _workbook_code(name):
    m = re.search(r'MHD-007[A-Z]', os.path.basename(str(name)).upper())
    return m.group(0) if m else None


# ─────────────────────────── Kubadilisha thamani ───────────────────────────

def _ids(value):
    return [p.strip() for p in re.split(r'[;,]', value or '') if p.strip()]


def _float(value):
    if value is None:
        return None
    try:
        return float(str(value).replace('+', '').strip())
    except ValueError:
        return None


def _range(value):
    """'+0.15 to +0.30' → (0.15, 0.30); '-0.05 to -0.20' → (-0.05, -0.20)."""
    nums = re.findall(r'[-+]?\d*\.?\d+', value or '')
    if not nums:
        return None, None
    lo, hi = float(nums[0]), float(nums[-1])
    return lo, hi


def _text(row, col):
    v = row.get(col)
    return '' if v is None else str(v)


def _norm(text):
    return re.sub(r'[^\w\s]', '', (text or '').lower()).strip()


# ─────────────────────────── Import yenyewe ───────────────────────────

class _Importer:
    def __init__(self, report):
        self.r = report
        self._crop_cache = {}

    # ---- msaada ----
    def crop(self, name):
        if not name:
            return None
        key = name.strip().lower()
        if key not in self._crop_cache:
            from django.db.models import Q
            from crops.models import Crop
            crop = Crop.objects.filter(Q(crop_name_sw__iexact=key) | Q(crop_name_en__iexact=key)).first()
            if crop is None:
                self.r.warnings.append(f"Zao '{name}' halipo kwenye Mazao — crop imeachwa tupu")
            self._crop_cache[key] = crop
        return self._crop_cache[key]

    def active(self, row, col):
        status = row.get(col)
        return True if status is None else str(status).lower() in ('active', 'approved')

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
                    created = handler(str(sid), row, source)
                if created is not None:
                    self.r.count(label, created)
            except Exception as e:  # row moja ikishindwa, nyingine zinaendelea
                self.r.errors.append(f"{source} {sid}: {e}")

    def upsert(self, model, sid, source, row, **fields):
        raw = {k: v for k, v in row.items() if v is not None}
        obj, created = model.objects.update_or_create(
            source_id=sid, defaults={'source_file': source, 'raw': raw, **fields})
        return obj, created

    def pest(self, pid, where):
        pest = Pest.objects.filter(source_id=pid).first()
        if pest is None:
            self.r.warnings.append(f"{where}: Pest '{pid}' haipo")
        return pest

    # ---- MHD-007A ----
    def import_007a(self, wb):
        def pest(sid, row, src):
            _, created = self.upsert(
                Pest, sid, src, row,
                crop=self.crop(row.get('Primary_Crop')),
                name_en=_text(row, 'English_Name'),
                name_sw=_text(row, 'Kiswahili_Name'),
                scientific_name=_text(row, 'Scientific_Name'),
                aliases=_text(row, 'Common_Aliases'),
                risk_level=_text(row, 'Tanzania_Risk_Level'),
                plant_part_attacked=_text(row, 'Plant_Part_Attacked'),
                growth_stage_attacked=_text(row, 'Growth_Stage_Attacked'),
                visible_symptoms_sw=_text(row, 'Visible_Symptoms_Kiswahili'),
                technical_symptoms=_text(row, 'Technical_Symptoms'),
                similar_pests=_text(row, 'Similar_Pests'),
                similar_stresses=_text(row, 'Similar_Diseases_or_Stresses'),
                key_differentiator=_text(row, 'Key_Differentiator'),
                field_diagnosis_method=_text(row, 'Field_Diagnosis_Method'),
                farmer_question_examples=_text(row, 'Farmer_Question_Examples'),
                ai_summary_sw=_text(row, 'AI_Summary_Kiswahili'),
                follow_up_question_sw=_text(row, 'Follow_Up_Question'),
                prevention=_text(row, 'Prevention'),
                cultural_control=_text(row, 'Cultural_Control'),
                mechanical_control=_text(row, 'Mechanical_Control'),
                biological_control=_text(row, 'Biological_Control'),
                botanical_control=_text(row, 'Botanical_Control'),
                chemical_control_guidance=_text(row, 'Chemical_Control_Guidance'),
                active_ingredients=_text(row, 'Active_Ingredient_Options_Check_Label'),
                ppe_and_safety=_text(row, 'PPE_and_Safety'),
            )
            return created
        self.rows(wb, 'MHD-007A', 'Pest_Master', 'Pest', 'Pest_ID', pest)

    def import_007a_rules(self, wb):
        """Decision rules + explainability — baada ya 007C (zinahitaji follow-ups)."""
        def rule(sid, row, src):
            pest = self.pest(row.get('Applies_To_Pest_ID'), f"{src} {sid}")
            if pest is None:
                raise ValueError(f"Applies_To_Pest_ID '{row.get('Applies_To_Pest_ID')}' haipo")
            question = _text(row, 'Follow_Up_Question')
            followup = None
            if question:
                followup = next((f for f in FollowupQuestion.objects.all()
                                 if _norm(f.question_sw) == _norm(question)), None)
                if followup is None:
                    self.r.warnings.append(f"{src} {sid}: swali halilingani na follow-up yoyote ya 007C")
            rule_type = _text(row, 'Rule_Type')
            if followup and 'differentiator' in rule_type.lower():
                FollowupQuestion.objects.filter(pk=followup.pk).update(is_key_differentiator=True)
            _, created = self.upsert(
                DecisionRule, sid, src, row,
                crop=self.crop(row.get('Crop')),
                is_active=self.active(row, 'CMS_Status'),
                rule_type=rule_type,
                pest=pest,
                input_symptom_sw=_text(row, 'Input_Symptom_Kiswahili'),
                condition_logic=_text(row, 'Condition_Logic'),
                ai_action=_text(row, 'AI_Action'),
                confidence=_float(row.get('Confidence_Score')),
                confidence_label=_text(row, 'Confidence_Level'),
                follow_up_question_sw=question,
                followup=followup,
                escalation_rule=_text(row, 'Escalation_Rule'),
            )
            return created
        self.rows(wb, 'MHD-007A', 'AI_Decision_Rules', 'Decision Rule', 'Rule_ID', rule)

        def explain(sid, row, src):
            pest = self.pest(row.get('Pest_ID'), f"{src} {sid}")
            _, created = self.upsert(
                ExplainabilityRecord, sid, src, row,
                level='pest', pest=pest,
                explanation_type=_text(row, 'Explanation_Type'),
                trigger=_text(row, 'Confidence_Trigger'),
                reason_sw=_text(row, 'AI_Explanation_Kiswahili'),
                why_not_sw=_text(row, 'Why_Not_Others'),
                farmer_message_sw=_text(row, 'Farmer_Friendly_Message'),
                linked_rules=_text(row, 'Linked_Rules'),
            )
            return created
        self.rows(wb, 'MHD-007A', 'Explainability', 'Explainability (pest)', 'Explain_ID', explain)

    # ---- MHD-007C ----
    def import_007c(self, wb):
        def symptom(sid, row, src):
            obj, created = self.upsert(
                Symptom, sid, src, row,
                crop=self.crop(row.get('Crop')),
                is_active=self.active(row, 'Record_Status'),
                symptom_code=_text(row, 'Symptom_Code'),
                farmer_symptom_sw=_text(row, 'Farmer_Symptom_Kiswahili'),
                normalized_symptom_sw=_text(row, 'Normalized_Symptom_Kiswahili'),
                farmer_symptom_en=_text(row, 'Farmer_Symptom_English'),
                plant_part=_text(row, 'Plant_Part'),
                growth_stage=_text(row, 'Growth_Stage'),
                category=_text(row, 'Symptom_Category'),
                severity_default=_text(row, 'Severity_Default'),
                likely_disease_ids=_text(row, 'Likely_Disease_IDs'),
                likely_nutrient_deficiency=_text(row, 'Likely_Nutrient_Deficiency'),
                likely_environmental_cause=_text(row, 'Likely_Environmental_Cause'),
                primary_clue_sw=_text(row, 'Primary_Diagnostic_Clue'),
                differential_diagnosis=_text(row, 'Differential_Diagnosis'),
                immediate_action_sw=_text(row, 'Immediate_Action_Kiswahili'),
                escalation_trigger_sw=_text(row, 'Escalation_Trigger_Kiswahili'),
                confidence_default=_text(row, 'AI_Confidence_Default'),
            )
            pests = [p for p in (self.pest(i, f"{src} {sid}") for i in _ids(row.get('Likely_Pest_IDs'))) if p]
            obj.likely_pests.set(pests)
            return created
        self.rows(wb, 'MHD-007C', 'Symptom_Master', 'Symptom', 'Symptom_ID', symptom)

        def mapping(sid, row, src):
            symptom = Symptom.objects.filter(source_id=row.get('Symptom_ID')).first()
            if symptom is None:
                raise ValueError(f"Symptom_ID '{row.get('Symptom_ID')}' haipo")
            target_type = _text(row, 'Diagnostic_Target_Type') or 'Pest'
            target_id = _text(row, 'Target_ID')
            pest = self.pest(target_id, f"{src} {sid}") if target_type.lower() == 'pest' else None
            _, created = self.upsert(
                SymptomDiagnosisMap, sid, src, row,
                symptom=symptom, target_type=target_type, target_id=target_id, pest=pest,
                match_strength=_text(row, 'Match_Strength'),
                required_context=_text(row, 'Required_Context'),
                rule_trigger=_text(row, 'Rule_Trigger'),
                next_action=_text(row, 'Next_Action'),
            )
            return created
        self.rows(wb, 'MHD-007C', 'Symptom_Diagnosis_Mapping', 'Symptom mapping', 'Map_ID', mapping)

        def followup(sid, row, src):
            symptom = Symptom.objects.filter(source_id=row.get('Symptom_ID')).first()
            if symptom is None and row.get('Symptom_ID'):
                self.r.warnings.append(f"{src} {sid}: Symptom_ID '{row.get('Symptom_ID')}' haipo")
            yes_min, yes_max = _range(row.get('Confidence_Impact_If_Yes'))
            no_min, no_max = _range(row.get('Confidence_Impact_If_No'))
            obj, created = self.upsert(
                FollowupQuestion, sid, src, row,
                symptom=symptom,
                question_sw=_text(row, 'Followup_Question_Kiswahili'),
                answer_type=_text(row, 'Expected_Answer_Type'),
                no_routes_text=_text(row, 'No_Routes_To'),
                if_yes_min=yes_min, if_yes_max=yes_max,
                if_no_min=no_min, if_no_max=no_max,
                purpose=_text(row, 'Purpose'),
            )
            pests = [p for p in (self.pest(i, f"{src} {sid}") for i in _ids(row.get('Yes_Routes_To'))) if p]
            obj.yes_routes_to.set(pests)
            return created
        self.rows(wb, 'MHD-007C', 'Followup_Question_Engine', 'Follow-up question', 'Question_ID', followup)

        def confidence(sid, row, src):
            adjustment = _float(row.get('Score_Adjustment'))
            if adjustment is None:
                raise ValueError(f"Score_Adjustment '{row.get('Score_Adjustment')}' si namba")
            condition = _text(row, 'Condition')
            obj, created = self.upsert(
                ConfidenceRule, sid, src, row,
                condition=condition, adjustment=adjustment,
                confidence_level=_text(row, 'Confidence_Level'),
                applied_to=_text(row, 'Applied_To'),
                explanation_sw=_text(row, 'Explanation'),
                developer_notes=_text(row, 'Developer_Notes'),
            )
            # Tunakisia condition_code mara ya kwanza tu — admin akiibadilisha,
            # import inayofuata haitaifuta.
            if created:
                low = condition.lower()
                if 'differentiator' in low:
                    obj.condition_code = 'key_differentiator'
                elif 'symptom' in low and 'plant part' in low:
                    obj.condition_code = 'symptom_match'
                obj.save(update_fields=['condition_code'])
            return created
        self.rows(wb, 'MHD-007C', 'Confidence_Scoring', 'Confidence rule', 'Rule_ID', confidence)

        def explain(sid, row, src):
            symptom = Symptom.objects.filter(source_id=row.get('Symptom_ID')).first()
            _, created = self.upsert(
                ExplainabilityRecord, sid, src, row,
                level='symptom', symptom=symptom,
                reason_sw=_text(row, 'AI_Reason_Kiswahili'),
                why_not_sw=_text(row, 'Why_Not_Enough_Kiswahili'),
                next_step_sw=_text(row, 'Likely_Next_Step_Kiswahili'),
                linked_rules=_text(row, 'Linked_Rules'),
            )
            return created
        self.rows(wb, 'MHD-007C', 'Explainability', 'Explainability (symptom)', 'Explainability_ID', explain)

    # ---- MHD-007E ----
    def _pest_by_name(self, linked):
        parts = [_norm(p) for p in (linked or '').split('/') if p.strip()]
        for pest in Pest.objects.all():
            names = {_norm(pest.name_en), _norm(pest.name_sw)}
            if any(p in names for p in parts):
                return pest
        return None

    def import_007e(self, wb):
        def treatment(sid, row, src):
            linked = _text(row, 'Linked_Diagnosis')
            pest = self._pest_by_name(linked)
            if pest is None:
                self.r.warnings.append(f"{src} {sid}: '{linked}' haijaunganishwa na Pest yoyote")
            _, created = self.upsert(
                Treatment, sid, src, row,
                crop=self.crop(row.get('Crop')),
                linked_diagnosis=linked, pest=pest,
                diagnosis_category=_text(row, 'Diagnosis_Category'),
                severity=_text(row, 'Severity'),
                plant_part=_text(row, 'Plant_Part'),
                growth_stage=_text(row, 'Growth_Stage'),
                objective=_text(row, 'Treatment_Objective'),
                immediate_action_sw=_text(row, 'Immediate_Action_Kiswahili'),
                cultural_control=_text(row, 'Cultural_Control'),
                mechanical_control=_text(row, 'Mechanical_Control'),
                biological_control=_text(row, 'Biological_Control'),
                botanical_control=_text(row, 'Botanical_Control'),
                chemical_control_guidance=_text(row, 'Chemical_Control_Guidance'),
                active_ingredient_examples=_text(row, 'Active_Ingredient_Examples'),
                resistance_management=_text(row, 'Resistance_Management'),
                ppe_requirements=_text(row, 'PPE_Requirements'),
                pre_harvest_interval=_text(row, 'Pre_Harvest_Interval'),
                re_entry_interval=_text(row, 'Re_Entry_Interval'),
                food_safety_warning_sw=_text(row, 'Food_Safety_Warning'),
                when_to_escalate=_text(row, 'When_To_Escalate'),
                farmer_message_sw=_text(row, 'Farmer_Message_Kiswahili'),
                extension_officer_note=_text(row, 'Extension_Officer_Note'),
            )
            return created
        self.rows(wb, 'MHD-007E', 'Treatment_IPM_Master', 'Treatment', 'Treatment_ID', treatment)

        def step(sid, row, src):
            treatment = Treatment.objects.filter(source_id=row.get('Treatment_ID')).first()
            if treatment is None:
                raise ValueError(f"Treatment_ID '{row.get('Treatment_ID')}' haipo")
            order = _float(row.get('Step_Order'))
            if order is None:
                raise ValueError("Step_Order haipo")
            _, created = self.upsert(
                TreatmentProtocolStep, sid, src, row,
                treatment=treatment, step_order=int(order),
                step_name=_text(row, 'Step_Name'),
                farmer_action_sw=_text(row, 'Farmer_Action_Kiswahili'),
                decision_point=_text(row, 'Decision_Point'),
                if_yes=_text(row, 'If_Yes'), if_no=_text(row, 'If_No'),
                safety_note=_text(row, 'Safety_Note'),
            )
            return created
        self.rows(wb, 'MHD-007E', 'Treatment_Protocols', 'Protocol step', 'Protocol_ID', step)

        def safety(sid, row, src):
            _, created = self.upsert(
                SafetyRule, sid, src, row,
                topic=_text(row, 'Topic'), rule=_text(row, 'Rule'),
                farmer_message_sw=_text(row, 'Farmer_Message_Kiswahili'),
                developer_note=_text(row, 'Developer_Note'),
                cms_field=_text(row, 'CMS_Field'),
            )
            return created
        self.rows(wb, 'MHD-007E', 'Safety_Compliance', 'Safety rule', 'Safety_ID', safety)

        def recommendation(sid, row, src):
            min_conf = _float(row.get('Confidence_Min'))
            _, created = self.upsert(
                RecommendationRule, sid, src, row,
                diagnosis_category=_text(row, 'Linked_Diagnosis_Category'),
                condition=_text(row, 'Condition'),
                ai_action=_text(row, 'AI_Action'),
                template_sw=_text(row, 'Recommendation_Template_Kiswahili'),
                min_confidence=0.75 if min_conf is None else min_conf,
                escalation=_text(row, 'Escalation'),
                cms_action_code=_text(row, 'CMS_Action_Code'),
            )
            return created
        self.rows(wb, 'MHD-007E', 'AI_Recommendation_Rules', 'Recommendation rule', 'Rule_ID', recommendation)

        def template(sid, row, src):
            words = _float(row.get('Max_Length_Words'))
            _, created = self.upsert(
                FarmerMessageTemplate, sid, src, row,
                use_case=_text(row, 'Use_Case'),
                diagnosis_category=_text(row, 'Diagnosis_Category'),
                message_sw=_text(row, 'Message_Kiswahili'),
                tone=_text(row, 'Tone'),
                max_words=int(words) if words else None,
                template_key=_text(row, 'CMS_Template_Key'),
            )
            return created
        self.rows(wb, 'MHD-007E', 'Farmer_Message_Templates', 'Farmer message template', 'Template_ID', template)

    # ---- MHD-007F ----
    def import_007f(self, wb):
        def explain(sid, row, src):
            _, created = self.upsert(
                ExplainabilityRecord, sid, src, row,
                level='scenario',
                explanation_type=_text(row, 'Scenario'),
                trigger=_text(row, 'Trigger'),
                reason_sw=_text(row, 'AI_Reasoning_Kiswahili'),
                farmer_message_sw=_text(row, 'Farmer_Explanation_Kiswahili'),
                confidence_basis=_text(row, 'Confidence_Basis'),
                escalation_condition=_text(row, 'Escalation_Condition'),
                linked_rules=_text(row, 'Linked_Workbook'),
            )
            return created
        self.rows(wb, 'MHD-007F', 'Explainability_Master', 'Explainability (scenario)', 'Explainability_ID', explain)

        def error(sid, row, src):
            _, created = self.upsert(
                ErrorHandlingRule, sid, src, row,
                error_code=_text(row, 'Error_Code'),
                trigger=_text(row, 'Trigger'),
                user_message_sw=_text(row, 'User_Message_Kiswahili'),
                system_action=_text(row, 'System_Action'),
                developer_log=_text(row, 'Developer_Log'),
                severity=_text(row, 'Severity'),
                blocking=_text(row, 'CMS_Blocking').lower() == 'yes',
            )
            return created
        self.rows(wb, 'MHD-007F', 'Error_Handling_Rules', 'Error handling rule', 'Error_ID', error)


def import_mhd007(files, dry_run=False):
    """
    files: list ya paths au file objects (mf. UploadedFile) — jina lazima
    liwe na code ya workbook (MHD-007A, …). Inarudisha ImportReport.
    """
    import openpyxl

    report = ImportReport(dry_run)
    books = {}
    for f in files:
        name = getattr(f, 'name', f)
        code = _workbook_code(name)
        if code not in WORKBOOK_CODES:
            report.warnings.append(f"'{os.path.basename(str(name))}' si MHD-007A/C/E/F — imerukwa")
            continue
        books[code] = openpyxl.load_workbook(f, read_only=True, data_only=True)
    report.workbooks = sorted(books)
    for code in WORKBOOK_CODES:
        if code not in books:
            report.warnings.append(f"{code} haikupakiwa — data yake iliyopo haijaguswa")

    imp = _Importer(report)
    # Mpangilio unafuata 007F/04_CMS_Import_Spec: wadudu → dalili → rules.
    steps = [
        ('MHD-007A', imp.import_007a),
        ('MHD-007C', imp.import_007c),
        ('MHD-007A', imp.import_007a_rules),
        ('MHD-007E', imp.import_007e),
        ('MHD-007F', imp.import_007f),
    ]
    try:
        with transaction.atomic():
            for code, step in steps:
                if code in books:
                    step(books[code])
            if report.failure_ratio > MAX_FAILURE_RATIO:
                report.rolled_back = True
                raise _Rollback()
            if dry_run:
                raise _Rollback()
    except _Rollback:
        pass
    return report
