"""
Rules-based Diagnostic Engine — data ya MHD-007 (A/C/E/F).

Kanuni muhimu:
  - Kila record ina `source_id` (mf. PST001, SYM001, R0001) kutoka Excel ya
    mteja, ili import iweze kurudiwa (update badala ya duplicate) na trace
    iseme wazi ni rule gani imetumika.
  - `raw` inahifadhi row nzima ya Excel — columns ambazo bado hatuzitumii
    hazipotei, na tunaweza kuzitumia baadaye bila kuimport upya.
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
                                   help_text="Faili/sheet ilikotoka, mf. MHD-007A/01_Pest_Master")
    raw = models.JSONField(default=dict, blank=True,
                           help_text="Row nzima ya Excel kama ilivyoingizwa")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['source_id']


# ─────────────────────────── MHD-007A: Wadudu / Visababishi ───────────────────────────

class Pest(SourceRecord):
    """Kisababishi kinachowezekana: mdudu, ugonjwa, au sababu ya mazingira."""
    CAUSE_TYPES = [
        ('insect', 'Mdudu'),
        ('disease', 'Ugonjwa'),
        ('environmental', 'Mazingira (mvua ya mawe, upepo)'),
        ('mechanical', 'Uharibifu wa kimwili'),
        ('nutrient', 'Upungufu wa virutubisho'),
        ('other', 'Nyingine'),
    ]

    name_en = models.CharField(max_length=150)
    name_sw = models.CharField(max_length=150, blank=True)
    scientific_name = models.CharField(max_length=150, blank=True)
    cause_type = models.CharField(max_length=20, choices=CAUSE_TYPES, default='insect')
    description_sw = models.TextField(blank=True)
    key_differentiator = models.TextField(
        blank=True, help_text="Ishara inayokitenganisha na visababishi vingine")

    class Meta(SourceRecord.Meta):
        verbose_name = 'Pest / Kisababishi'
        verbose_name_plural = 'Pests / Visababishi'

    def __str__(self):
        return f"{self.source_id} — {self.name_sw or self.name_en}"


class DecisionRule(SourceRecord):
    """AI_Decision_Rules (007A), mf. R0001 symptom match → PST001 (0.65)."""
    rule_type = models.CharField(max_length=60, blank=True,
                                 help_text="mf. Symptom Match, Key Differentiator")
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, related_name='decision_rules')
    condition = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)
    confidence_label = models.CharField(max_length=20, blank=True)
    followup = models.ForeignKey('FollowupQuestion', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='decision_rules')
    action = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Decision Rule'

    def __str__(self):
        return f"{self.source_id} ({self.rule_type}) → {self.pest.source_id}"


# ─────────────────────────── MHD-007C: Dalili na maswali ───────────────────────────

class Symptom(SourceRecord):
    """Symptom_Master — dalili anayoiona mkulima."""
    growth_stage = models.CharField(max_length=60, blank=True)
    plant_part = models.CharField(max_length=60, blank=True)
    farmer_description_sw = models.TextField(help_text="Jinsi mkulima anavyoeleza")
    normalized_sw = models.TextField(blank=True)
    keywords = models.TextField(
        blank=True, help_text="Maneno ya kulinganisha, yametenganishwa kwa ';'")
    likely_pests = models.ManyToManyField(Pest, blank=True, related_name='symptoms')
    environmental_causes = models.TextField(blank=True, help_text="mf. hail; wind")
    differential_notes = models.TextField(blank=True)
    immediate_action_sw = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Symptom / Dalili'
        verbose_name_plural = 'Symptoms / Dalili'

    def keyword_list(self):
        return [k.strip().lower() for k in self.keywords.split(';') if k.strip()]

    def __str__(self):
        return f"{self.source_id} — {self.farmer_description_sw[:60]}"


class SymptomDiagnosisMap(SourceRecord):
    """Symptom_Diagnosis_Mapping, mf. MAP0001: SYM001 → PST001."""
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE, related_name='mappings')
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, related_name='mappings')
    match_strength = models.CharField(max_length=30, blank=True, help_text="mf. Medium/High")
    rule_trigger = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Symptom → Pest mapping'

    def __str__(self):
        return f"{self.source_id}: {self.symptom.source_id} → {self.pest.source_id}"


class FollowupQuestion(SourceRecord):
    """Followup_Question_Engine, mf. FU0001 (kinyesi cheusi?)."""
    symptoms = models.ManyToManyField(Symptom, blank=True, related_name='followups')
    question_sw = models.TextField()
    yes_routes_to = models.ManyToManyField(Pest, blank=True, related_name='followups_yes')
    no_routes_to = models.ManyToManyField(Pest, blank=True, related_name='followups_no')
    # Ranges kama zilivyo kwenye dataset (+0.15 hadi +0.30). Thamani ipi
    # itumike inaamuliwa na EngineSetting 'range_strategy'.
    if_yes_min = models.FloatField(null=True, blank=True)
    if_yes_max = models.FloatField(null=True, blank=True)
    if_no_min = models.FloatField(null=True, blank=True)
    if_no_max = models.FloatField(null=True, blank=True)
    is_key_differentiator = models.BooleanField(
        default=False, help_text="Jibu 'Ndiyo' linathibitisha key differentiator (CONF002)")
    priority = models.PositiveSmallIntegerField(default=100)

    class Meta(SourceRecord.Meta):
        ordering = ['priority', 'source_id']
        verbose_name = 'Follow-up Question'

    def __str__(self):
        return f"{self.source_id} — {self.question_sw[:60]}"


class ConfidenceRule(SourceRecord):
    """Confidence_Scoring, mf. CONF001 (+0.20), CONF002 (+0.30). Additive."""
    CONDITIONS = [
        ('symptom_match', 'Dalili + zao + sehemu ya mmea vinalingana'),
        ('key_differentiator', 'Follow-up inathibitisha key differentiator'),
        ('other', 'Nyingine (angalia description)'),
    ]
    condition_code = models.CharField(max_length=30, choices=CONDITIONS, default='other')
    description = models.TextField(blank=True)
    adjustment = models.FloatField(help_text="Kiasi kinachoongezwa, mf. 0.20")

    class Meta(SourceRecord.Meta):
        verbose_name = 'Confidence Rule'

    def __str__(self):
        return f"{self.source_id} ({self.adjustment:+.2f})"


# ─────────────────────────── MHD-007E: Matibabu na usalama ───────────────────────────

class Treatment(SourceRecord):
    """Treatment / IPM kwa kisababishi."""
    METHODS = [
        ('cultural', 'Kilimo bora (cultural)'),
        ('mechanical', 'Mkono / mitambo'),
        ('biological', 'Kibaiolojia'),
        ('chemical', 'Kemikali'),
        ('monitoring', 'Ufuatiliaji (scouting)'),
    ]
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, related_name='treatments')
    method = models.CharField(max_length=20, choices=METHODS, default='cultural')
    title_sw = models.CharField(max_length=200, blank=True)
    description_sw = models.TextField(blank=True)
    # SAFE001: hakuna majina ya bidhaa mpaka registry iidhinishwe — category tu.
    active_ingredient_category = models.CharField(max_length=150, blank=True)
    requires_ppe = models.BooleanField(default=False)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Treatment / IPM'

    def __str__(self):
        return f"{self.source_id} — {self.pest.source_id} ({self.get_method_display()})"


class TreatmentProtocolStep(models.Model):
    """02_Treatment_Protocols — hatua kwa hatua zenye If_Yes / If_No."""
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name='steps')
    step_no = models.PositiveSmallIntegerField()
    instruction_sw = models.TextField()
    if_yes = models.TextField(blank=True)
    if_no = models.TextField(blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['treatment', 'step_no']
        unique_together = ['treatment', 'step_no']

    def __str__(self):
        return f"{self.treatment.source_id} hatua {self.step_no}"


class SafetyRule(SourceRecord):
    """Safety_Compliance, mf. SAFE001 (dawa zilizosajiliwa tu), SAFE002 (PPE)."""
    APPLIES = [('chemical', 'Pendekezo la kemikali'), ('all', 'Kila jibu')]
    applies_to = models.CharField(max_length=20, choices=APPLIES, default='chemical')
    rule_text_sw = models.TextField()
    farmer_warning_sw = models.TextField(blank=True,
                                         help_text="Onyo linaloongezwa kwenye jibu la mkulima")

    class Meta(SourceRecord.Meta):
        verbose_name = 'Safety Rule'

    def __str__(self):
        return self.source_id


class RecommendationRule(SourceRecord):
    """AI_Recommendation_Rules, mf. REC-MZ-0001: conf ≥ 0.75 & severity ≥ High → IPM."""
    SEVERITY = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='recommendation_rules',
                             help_text="Tupu = inatumika kwa visababishi vyote")
    min_confidence = models.FloatField(default=0.75)
    min_severity = models.CharField(max_length=10, choices=SEVERITY, default='high')
    action_sw = models.TextField(blank=True)
    escalate_if_spreading = models.BooleanField(default=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Recommendation Rule'

    def __str__(self):
        return f"{self.source_id} (≥{self.min_confidence}, {self.min_severity})"


class FarmerMessageTemplate(SourceRecord):
    """05_Farmer_Message_Templates — sentensi za msingi kwa mkulima."""
    purpose = models.CharField(max_length=60, help_text="mf. diagnosis_high, uncertain, escalate")
    text_sw = models.TextField()

    class Meta(SourceRecord.Meta):
        verbose_name = 'Farmer Message Template'

    def __str__(self):
        return f"{self.source_id} ({self.purpose})"


# ─────────────────────────── MHD-007F: Explainability ───────────────────────────

class ExplainabilityRecord(SourceRecord):
    """02_Explainability_Master — kwa nini hiki, kwa nini si vingine."""
    pest = models.ForeignKey(Pest, on_delete=models.CASCADE, related_name='explanations')
    why_this_sw = models.TextField(blank=True)
    why_not_others_sw = models.TextField(blank=True)
    evidence_sw = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Explainability Record'

    def __str__(self):
        return f"{self.source_id} — {self.pest.source_id}"


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


# Chanzo kimoja cha defaults — migration na get_setting() zote zinatumia hii.
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
}


def get_setting(key, cast=float):
    """Soma setting; ikikosekana DB, tumia default ya DEFAULT_SETTINGS."""
    row = EngineSetting.objects.filter(key=key).values_list('value', flat=True).first()
    value = row if row is not None else DEFAULT_SETTINGS[key][0]
    return cast(value) if cast else value
