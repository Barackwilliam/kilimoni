"""
Rules-based Diagnostic Engine — data ya MHD-007 (A/C/E/F).

Kanuni muhimu:
  - Kila record ina `source_id` (mf. PST001, SYM001, R0001) kutoka Excel ya
    mteja, ili import iweze kurudiwa (upsert) na trace iseme wazi ni rule
    gani imetumika.
  - `raw` inahifadhi row nzima ya Excel — columns ambazo bado hatuzitumii
    hazipotei, na tunaweza kuzitumia baadaye bila kuimport upya.
  - Fields zinafuata majina ya columns za Excel (Pest_ID → source_id,
    Kiswahili_Name → name_sw, n.k.). Ramani kamili iko diagnosis/importer.py.
  - Thamani za tafsiri (Medium = ngapi, n.k.) ziko kwenye EngineSetting,
    zinabadilishwa kupitia admin bila code.
"""
from django.db import models


class SourceRecord(models.Model):
    """Msingi wa kila table inayotoka kwenye dataset ya mteja."""
    source_id = models.CharField(max_length=40, unique=True,
                                 help_text="ID ya dataset, mf. PST001")
    crop = models.ForeignKey('crops.Crop', on_delete=models.CASCADE,
                             null=True, blank=True, related_name='+')
    source_file = models.CharField(max_length=120, blank=True,
                                   help_text="Workbook/sheet ilikotoka, mf. MHD-007A/01_Pest_Master")
    raw = models.JSONField(default=dict, blank=True,
                           help_text="Row nzima ya Excel kama ilivyoingizwa")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['source_id']


# ─────────────────────────── MHD-007A: Wadudu ───────────────────────────

class Pest(SourceRecord):
    """01_Pest_Master."""
    name_en = models.CharField(max_length=150)
    name_sw = models.CharField(max_length=150, blank=True)
    scientific_name = models.CharField(max_length=150, blank=True)
    aliases = models.TextField(blank=True)
    risk_level = models.CharField(max_length=20, blank=True)
    plant_part_attacked = models.CharField(max_length=200, blank=True)
    growth_stage_attacked = models.CharField(max_length=200, blank=True)
    visible_symptoms_sw = models.TextField(blank=True)
    technical_symptoms = models.TextField(blank=True)
    similar_pests = models.TextField(blank=True)
    similar_stresses = models.TextField(blank=True)
    key_differentiator = models.TextField(blank=True)
    field_diagnosis_method = models.TextField(blank=True)
    farmer_question_examples = models.TextField(blank=True)
    ai_summary_sw = models.TextField(blank=True)
    follow_up_question_sw = models.TextField(blank=True)
    # IPM kwa ufupi (MHD-007E ina undani zaidi kwenye Treatment)
    prevention = models.TextField(blank=True)
    cultural_control = models.TextField(blank=True)
    mechanical_control = models.TextField(blank=True)
    biological_control = models.TextField(blank=True)
    botanical_control = models.TextField(blank=True)
    chemical_control_guidance = models.TextField(blank=True)
    # SAFE001: haionyeshwi kwa mkulima mpaka registry iidhinishwe.
    active_ingredients = models.TextField(blank=True)
    ppe_and_safety = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Pest / Mdudu'
        verbose_name_plural = 'Pests / Wadudu'

    def __str__(self):
        return f"{self.source_id} — {self.name_sw or self.name_en}"


# ─────────────────────────── MHD-007B: Magonjwa ───────────────────────────

class Disease(SourceRecord):
    """01_Disease_Master. source_id = Disease_ID (DIS001)."""
    record_id = models.CharField(max_length=40, blank=True, help_text="Record_ID, mf. MHD007B-REC001")
    name_en = models.CharField(max_length=150)
    name_sw = models.CharField(max_length=200, blank=True)
    causal_agent = models.CharField(max_length=200, blank=True)
    pathogen_type = models.CharField(max_length=60, blank=True)
    disease_group = models.CharField(max_length=60, blank=True)
    plant_part_affected = models.CharField(max_length=200, blank=True)
    growth_stage_affected = models.CharField(max_length=200, blank=True)
    favourable_conditions = models.TextField(blank=True)
    transmission = models.TextField(blank=True)
    visible_symptoms_sw = models.TextField(blank=True)
    technical_symptoms = models.TextField(blank=True)
    key_diagnostic_feature = models.TextField(blank=True)
    similar_problems = models.TextField(blank=True)
    differentiator = models.TextField(blank=True)
    field_diagnosis_method = models.TextField(blank=True)
    confirmation_method = models.TextField(blank=True)
    severity_level = models.CharField(max_length=20, blank=True)
    urgency = models.CharField(max_length=20, blank=True)
    prevention_sw = models.TextField(blank=True)
    cultural_control_sw = models.TextField(blank=True)
    sanitation_control_sw = models.TextField(blank=True)
    resistant_variety_advice = models.TextField(blank=True)
    biological_control_sw = models.TextField(blank=True)
    chemical_control_safety_text = models.TextField(blank=True)
    ipm_recommendation_sw = models.TextField(blank=True)
    farmer_question_examples = models.TextField(blank=True)
    ai_summary_sw = models.TextField(blank=True)
    follow_up_question_sw = models.TextField(blank=True)
    escalation_trigger = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Disease / Ugonjwa'
        verbose_name_plural = 'Diseases / Magonjwa'

    def __str__(self):
        return f"{self.source_id} — {self.name_sw or self.name_en}"


# ─────────────────────────── MHD-007C: Dalili na maswali ───────────────────────────

class Symptom(SourceRecord):
    """01_Symptom_Master."""
    symptom_code = models.CharField(max_length=40, blank=True)
    farmer_symptom_sw = models.TextField()
    normalized_symptom_sw = models.TextField(blank=True)
    farmer_symptom_en = models.TextField(blank=True)
    plant_part = models.CharField(max_length=60, blank=True)
    growth_stage = models.CharField(max_length=60, blank=True)
    category = models.CharField(max_length=60, blank=True)
    severity_default = models.CharField(max_length=20, blank=True)
    likely_pests = models.ManyToManyField(Pest, blank=True, related_name='symptoms')
    likely_disease_ids = models.CharField(max_length=200, blank=True,
                                          help_text="MHD-007B bado haijaletwa")
    likely_nutrient_deficiency = models.TextField(blank=True)
    likely_environmental_cause = models.TextField(blank=True)
    primary_clue_sw = models.TextField(blank=True)
    differential_diagnosis = models.TextField(blank=True)
    immediate_action_sw = models.TextField(blank=True)
    escalation_trigger_sw = models.TextField(blank=True)
    confidence_default = models.CharField(max_length=20, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Symptom / Dalili'
        verbose_name_plural = 'Symptoms / Dalili'

    def __str__(self):
        return f"{self.source_id} — {self.farmer_symptom_sw[:50]} ({self.growth_stage})"


class SymptomDiagnosisMap(SourceRecord):
    """02_Symptom_Diagnosis_Mapping, mf. MAP0001: SYM001 → PST001."""
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE, related_name='mappings')
    target_type = models.CharField(max_length=30, default='Pest')
    target_id = models.CharField(max_length=40,
                                 help_text="Pest_ID au Disease_ID")
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='mappings')
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='mappings')
    match_strength = models.CharField(max_length=30, blank=True)
    required_context = models.TextField(blank=True)
    rule_trigger = models.TextField(blank=True)
    next_action = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Symptom → Diagnosis mapping'

    def __str__(self):
        return f"{self.source_id}: {self.symptom.source_id} → {self.target_id}"


class FollowupQuestion(SourceRecord):
    """03_Followup_Question_Engine, mf. FU0001 (kinyesi cheusi?)."""
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='followups')
    question_sw = models.TextField()
    answer_type = models.CharField(max_length=60, blank=True)
    yes_routes_to = models.ManyToManyField(Pest, blank=True, related_name='followups_yes')
    no_routes_text = models.TextField(blank=True,
                                      help_text="Kwenye dataset ni maelezo, si IDs")
    # Ranges kama zilivyo kwenye dataset (+0.15 to +0.30). Thamani ipi
    # itumike inaamuliwa na EngineSetting 'range_strategy'.
    if_yes_min = models.FloatField(null=True, blank=True)
    if_yes_max = models.FloatField(null=True, blank=True)
    if_no_min = models.FloatField(null=True, blank=True)
    if_no_max = models.FloatField(null=True, blank=True)
    purpose = models.TextField(blank=True)
    # Importer inaiweka True ikiwa swali hili ndilo la Decision Rule ya
    # "Key Differentiator" (R0002) — CONF002 inatumika kwa jibu la Ndiyo.
    is_key_differentiator = models.BooleanField(default=False)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Follow-up Question'

    def __str__(self):
        return f"{self.source_id} — {self.question_sw[:60]}"


class ConfidenceRule(SourceRecord):
    """04_Confidence_Scoring, mf. CONF001 (+0.20), CONF002 (+0.30). Additive."""
    CONDITIONS = [
        ('symptom_match', 'Dalili + zao + sehemu ya mmea vinalingana'),
        ('key_differentiator', 'Follow-up inathibitisha key differentiator'),
        ('other', 'Nyingine (angalia condition)'),
    ]
    condition = models.TextField()
    condition_code = models.CharField(max_length=30, choices=CONDITIONS, default='other',
                                      help_text="Inakisiwa na importer; inaweza kubadilishwa hapa")
    adjustment = models.FloatField(help_text="mf. 0.20")
    confidence_level = models.CharField(max_length=30, blank=True)
    applied_to = models.CharField(max_length=60, blank=True)
    explanation_sw = models.TextField(blank=True)
    developer_notes = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Confidence Rule'

    def __str__(self):
        return f"{self.source_id} ({self.adjustment:+.2f})"


class DecisionRule(SourceRecord):
    """
    02_AI_Decision_Rules za MHD-007A (pest, mf. R0001 → PST001, 0.65) na
    MHD-007B (disease, mf. MHD007B-RUL001 → DIS001, 0.82). Moja tu kati ya
    pest/disease imejazwa.
    """
    rule_type = models.CharField(max_length=60, blank=True)
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='decision_rules')
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='decision_rules')
    context_requirements = models.TextField(blank=True)
    differential_check = models.TextField(blank=True)
    input_symptom_sw = models.TextField(blank=True)
    condition_logic = models.TextField(blank=True)
    ai_action = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)
    confidence_label = models.CharField(max_length=20, blank=True)
    follow_up_question_sw = models.TextField(blank=True)
    followup = models.ForeignKey(FollowupQuestion, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='decision_rules',
                                 help_text="Imeunganishwa kwa maandishi ya swali")
    escalation_rule = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Decision Rule'

    def __str__(self):
        target = self.pest or self.disease
        return f"{self.source_id} ({self.rule_type}) → {target.source_id if target else '?'}"


# ─────────────────────────── MHD-007D: Decision engine ───────────────────────────
# 007D inataja visababishi kwa JINA ("Fall Armyworm / Funza Jeshi Vamizi"),
# si kwa ID. Importer inatafuta Pest/Disease inayolingana na kuhifadhi ID yake
# kwenye *_cause_id (PST001 / DIS001); tupu = haijaunganishwa (onyo la import).

class DiagnosisRule(SourceRecord):
    """01_Diagnosis_Decision_Rules, mf. DR-MZ-0001 (FAW, base 0.90)."""
    input_symptom_sw = models.TextField(blank=True)
    normalized_symptom = models.TextField(blank=True)
    plant_part = models.CharField(max_length=60, blank=True)
    growth_stage = models.CharField(max_length=60, blank=True)
    condition_code = models.CharField(max_length=30, blank=True)
    likely_diagnosis = models.CharField(max_length=200)
    cause_id = models.CharField(max_length=40, blank=True)
    diagnosis_category = models.CharField(max_length=30, blank=True)
    trigger_conditions = models.TextField(blank=True)
    exclusion_conditions = models.TextField(blank=True)
    follow_up_question_sw = models.TextField(blank=True)
    if_answer_yes = models.TextField(blank=True)
    if_answer_no = models.TextField(blank=True)
    base_confidence = models.FloatField(null=True, blank=True)
    adjusted_confidence_high = models.FloatField(null=True, blank=True)
    adjusted_confidence_low = models.FloatField(null=True, blank=True)
    severity = models.CharField(max_length=20, blank=True)
    urgency = models.CharField(max_length=20, blank=True)
    next_action = models.TextField(blank=True)
    explainability_id = models.CharField(max_length=40, blank=True)
    cms_action_code = models.CharField(max_length=40, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Diagnosis Rule (007D)'

    def __str__(self):
        return f"{self.source_id} — {self.likely_diagnosis} ({self.growth_stage})"


class DifferentialDiagnosis(SourceRecord):
    """02_Differential_Diagnosis, mf. DD-MZ-0001: FAW vs Stem Borer."""
    symptom_group = models.TextField(blank=True)
    primary_diagnosis = models.CharField(max_length=200)
    primary_cause_id = models.CharField(max_length=40, blank=True)
    alternative_diagnosis = models.CharField(max_length=200)
    alternative_cause_id = models.CharField(max_length=40, blank=True)
    shared_symptoms = models.TextField(blank=True)
    differentiating_feature = models.TextField(blank=True)
    question_sw = models.TextField(blank=True)
    decision_logic = models.TextField(blank=True)
    if_yes_adjustment = models.FloatField(null=True, blank=True)
    if_no_adjustment = models.FloatField(null=True, blank=True)
    priority = models.CharField(max_length=20, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Differential Diagnosis'
        verbose_name_plural = 'Differential Diagnoses'

    def __str__(self):
        return f"{self.source_id}: {self.primary_diagnosis} vs {self.alternative_diagnosis}"


class FollowUpNode(SourceRecord):
    """03_Follow_Up_Logic, mf. FU-MZ-0001 → NODE_FAW_2."""
    rule_group = models.CharField(max_length=40, blank=True, help_text="mf. FAW")
    question_sw = models.TextField()
    answer_type = models.CharField(max_length=60, blank=True)
    yes_action = models.TextField(blank=True)
    no_action = models.TextField(blank=True)
    unknown_action = models.TextField(blank=True)
    adjustment_yes = models.FloatField(null=True, blank=True)
    adjustment_no = models.FloatField(null=True, blank=True)
    next_node = models.CharField(max_length=40, blank=True)
    cms_field = models.CharField(max_length=60, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Follow-up Node (007D)'

    def __str__(self):
        return f"{self.source_id} — {self.question_sw[:60]}"


class ConfidenceBand(SourceRecord):
    """04_Confidence_Scoring ya 007D. source_id = jina la band (mf. 'High')."""
    min_score = models.FloatField()
    max_score = models.FloatField()
    meaning = models.TextField(blank=True)
    system_action = models.TextField(blank=True)
    farmer_message_sw = models.TextField(blank=True)
    escalation_needed = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ['-min_score']
        verbose_name = 'Confidence Band'

    def __str__(self):
        return f"{self.source_id} ({self.min_score:.2f}–{self.max_score:.2f})"


class EscalationRule(SourceRecord):
    """05_Escalation_Rules, mf. ESC-MZ-001 (ugonjwa hatari → afisa ugani)."""
    trigger = models.CharField(max_length=200, blank=True)
    condition = models.TextField(blank=True)
    ai_action = models.TextField(blank=True)
    farmer_message_sw = models.TextField(blank=True)
    escalate_to = models.CharField(max_length=60, blank=True)
    priority = models.CharField(max_length=20, blank=True)
    cms_action_code = models.CharField(max_length=40, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Escalation Rule'

    def __str__(self):
        return f"{self.source_id} — {self.trigger}"


# ─────────────────────────── MHD-007E: Matibabu na usalama ───────────────────────────

class Treatment(SourceRecord):
    """01_Treatment_IPM_Master. Dataset inaiunganisha kwa jina (Linked_Diagnosis)."""
    linked_diagnosis = models.CharField(max_length=200)
    pest = models.ForeignKey(Pest, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='treatments')
    diagnosis_category = models.CharField(max_length=30, blank=True)
    severity = models.CharField(max_length=20, blank=True)
    plant_part = models.CharField(max_length=100, blank=True)
    growth_stage = models.CharField(max_length=100, blank=True)
    objective = models.TextField(blank=True)
    immediate_action_sw = models.TextField(blank=True)
    cultural_control = models.TextField(blank=True)
    mechanical_control = models.TextField(blank=True)
    biological_control = models.TextField(blank=True)
    botanical_control = models.TextField(blank=True)
    chemical_control_guidance = models.TextField(blank=True)
    # SAFE001: haionyeshwi kwa mkulima mpaka registry iidhinishwe.
    active_ingredient_examples = models.TextField(blank=True)
    resistance_management = models.TextField(blank=True)
    ppe_requirements = models.TextField(blank=True)
    pre_harvest_interval = models.TextField(blank=True)
    re_entry_interval = models.TextField(blank=True)
    food_safety_warning_sw = models.TextField(blank=True)
    when_to_escalate = models.TextField(blank=True)
    farmer_message_sw = models.TextField(blank=True)
    extension_officer_note = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Treatment / IPM'

    def __str__(self):
        return f"{self.source_id} — {self.linked_diagnosis}"


class TreatmentProtocolStep(SourceRecord):
    """02_Treatment_Protocols — hatua kwa hatua zenye If_Yes / If_No."""
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name='steps')
    step_order = models.PositiveSmallIntegerField()
    step_name = models.CharField(max_length=100, blank=True)
    farmer_action_sw = models.TextField()
    decision_point = models.TextField(blank=True)
    if_yes = models.TextField(blank=True)
    if_no = models.TextField(blank=True)
    safety_note = models.TextField(blank=True)

    class Meta:
        ordering = ['treatment', 'step_order']
        verbose_name = 'Treatment Protocol Step'

    def __str__(self):
        return f"{self.treatment.source_id} hatua {self.step_order}: {self.step_name}"


class SafetyRule(SourceRecord):
    """03_Safety_Compliance, mf. SAFE001 (dawa zilizosajiliwa tu), SAFE002 (PPE)."""
    topic = models.CharField(max_length=100, blank=True)
    rule = models.TextField()
    farmer_message_sw = models.TextField(blank=True)
    developer_note = models.TextField(blank=True)
    cms_field = models.CharField(max_length=60, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Safety Rule'

    def __str__(self):
        return f"{self.source_id} — {self.topic}"


class RecommendationRule(SourceRecord):
    """04_AI_Recommendation_Rules, mf. REC-MZ-0001: conf ≥ 0.75 & severity ≥ High → IPM."""
    diagnosis_category = models.CharField(max_length=30, blank=True)
    condition = models.TextField(blank=True)
    ai_action = models.TextField(blank=True)
    template_sw = models.TextField(blank=True)
    min_confidence = models.FloatField(default=0.75)
    escalation = models.TextField(blank=True)
    cms_action_code = models.CharField(max_length=40, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Recommendation Rule'

    def __str__(self):
        return f"{self.source_id} (≥{self.min_confidence})"


class FarmerMessageTemplate(SourceRecord):
    """05_Farmer_Message_Templates."""
    use_case = models.CharField(max_length=60)
    diagnosis_category = models.CharField(max_length=30, blank=True)
    message_sw = models.TextField()
    tone = models.CharField(max_length=30, blank=True)
    max_words = models.PositiveSmallIntegerField(null=True, blank=True)
    template_key = models.CharField(max_length=60, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Farmer Message Template'

    def __str__(self):
        return f"{self.source_id} ({self.use_case})"


# ─────────────────────────── Explainability (007A, 007C, 007F) ───────────────────────────

class ExplainabilityRecord(SourceRecord):
    """
    Maelezo ya "kwa nini" yanatoka sheets 5 zenye umbo tofauti:
      pest     — MHD-007A/03_Explainability (EXP0001…)
      symptom  — MHD-007C/05_Explainability (EXP001…)
      scenario — MHD-007F/02_Explainability_Master (EXP-CAT-001…)
      disease  — MHD-007B/03_Explainability (MHD007B-EXP001…)
      decision — MHD-007D/06_Explainability (EXP-MZ-0001…), kwa DiagnosisRule
    """
    LEVELS = [('pest', 'Pest'), ('symptom', 'Symptom'), ('scenario', 'Scenario'),
              ('disease', 'Disease'), ('decision', 'Diagnosis rule')]
    level = models.CharField(max_length=10, choices=LEVELS)
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='explanations')
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='explanations')
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='explanations')
    explanation_type = models.CharField(max_length=60, blank=True,
                                        help_text="mf. Diagnosis Reason, au Scenario ya 007F")
    trigger = models.TextField(blank=True)
    reason_sw = models.TextField(blank=True)
    why_not_sw = models.TextField(blank=True, help_text="Why_Not_Others / Why_Not_Enough")
    farmer_message_sw = models.TextField(blank=True)
    next_step_sw = models.TextField(blank=True)
    confidence_basis = models.TextField(blank=True)
    escalation_condition = models.TextField(blank=True)
    linked_rules = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Explainability Record'

    def __str__(self):
        return f"{self.source_id} ({self.level})"


class ErrorHandlingRule(SourceRecord):
    """MHD-007F 06_Error_Handling_Rules, mf. ERR001 LOW_CONFIDENCE."""
    error_code = models.CharField(max_length=60)
    trigger = models.TextField(blank=True)
    user_message_sw = models.TextField()
    system_action = models.TextField(blank=True)
    developer_log = models.CharField(max_length=100, blank=True)
    severity = models.CharField(max_length=20, blank=True)
    blocking = models.BooleanField(default=False)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Error Handling Rule'

    def __str__(self):
        return f"{self.source_id} {self.error_code}"


# ─────────────────────────── Mipangilio ya injini ───────────────────────────

class EngineSetting(models.Model):
    """
    Tafsiri za kanuni ambazo mteja bado hajazijibu (handover Sehemu 8).
    Defaults zinaingizwa na migration 0002; zinabadilishwa kupitia admin.
    """
    key = models.CharField(max_length=60, unique=True)
    value = models.CharField(max_length=60)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Engine Setting'

    def __str__(self):
        return f"{self.key} = {self.value}"


class FarmerTerm(models.Model):
    """
    Kamusi ya lugha rahisi: neno/kifungu cha kiufundi cha dataset → maneno
    ambayo mkulima anaelewa. Inatumika na diagnosis/plain.py kabla jibu
    halijatumwa. Mteja anaibadilisha kwenye dashboard.
    """
    term = models.CharField(max_length=200, unique=True,
                            help_text='Neno au kifungu kama kilivyo kwenye dataset (mf. frass)')
    plain = models.CharField(max_length=300,
                             help_text='Maneno rahisi ya Kiswahili (mf. kinyesi cha funza)')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['term']
        verbose_name = 'Neno la mkulima'
        verbose_name_plural = 'Kamusi ya lugha rahisi'

    def __str__(self):
        return f"{self.term} → {self.plain}"


# Chanzo kimoja cha defaults — get_setting() inaitumia; migration 0002 ina nakala.
DEFAULT_SETTINGS = {
    'label_low': ('0.40', 'Confidence ya "Low" kwenye dataset'),
    'label_medium': ('0.65', 'Confidence ya "Medium" (kama R0001)'),
    'label_high': ('0.85', 'Confidence ya "High" (kama R0002)'),
    'range_strategy': ('mid', 'Thamani ya ranges (+0.15–+0.30): mid, min au max'),
    'confidence_cap': ('0.95', 'Kikomo cha juu cha confidence'),
    'diagnosis_threshold': ('0.75', 'Kiwango cha chini kutoa uchunguzi'),
    'min_lead_margin': ('0.15', 'Tofauti ya chini kati ya wa kwanza na wa pili'),
    'severity_low_max': ('10', 'Ukubwa (%) chini ya hapa = Low'),
    'severity_medium_max': ('30', 'Ukubwa (%) hadi hapa = Medium; juu = High'),
    'allow_product_names': ('0', 'SAFE001: 1 tu baada ya registry ya dawa kuidhinishwa'),
    'initial_source': ('007D', 'Chanzo cha score ya mwanzo kikiwa na vingi: 007D au 007A'),
    'symptom_match_ratio': ('0.5', 'Sehemu ya maneno ya dalili yanayotakiwa kulingana'),
    'key_question_no_adjustment': ('-0.125', 'Ishara kuu ikikataliwa (katikati ya -0.05..-0.20 ya 007C)'),
    'rec_min_severity': ('high', 'Severity ya chini kwa Recommendation Rule (low/medium/high)'),
    'max_questions': ('4', 'Idadi ya juu ya maswali ya kufuatilia kwa uchunguzi mmoja'),
    'show_rules_to_farmer': ('0', 'Onyesha kanuni (DR-…, CONF…) na chanzo kwenye jibu la mkulima: 1 = ndiyo (demo), 0 = trace tu'),
}


def get_setting(key, cast=float):
    """Soma setting; ikikosekana DB, tumia default ya DEFAULT_SETTINGS."""
    row = EngineSetting.objects.filter(key=key).values_list('value', flat=True).first()
    value = row if row is not None else DEFAULT_SETTINGS[key][0]
    return cast(value) if cast else value
