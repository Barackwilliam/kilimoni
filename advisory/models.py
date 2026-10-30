"""
Ushauri wa kilimo kwa kanuni — data ya MHD-001 hadi MHD-006.

Muundo ni uleule wa diagnosis/ (MHD-007): kila record ina source_id ya
dataset (upsert salama), row nzima ya Excel kwenye `raw`, na `is_active`.

Hatua 1 (hii): Eneo — MHD-001 Location & Agroecology Master (ngazi ya kata).
Hatua zinazofuata (mbegu, msimu, udongo, mzunguko) zinaongeza models hapa.
"""
from django.db import models

from diagnosis.models import SourceRecord


# ─────────────────────────── MHD-001: Eneo ───────────────────────────

class Aez(SourceRecord):
    """AEZ_Master — kanda za kilimo (agro-ecological zones)."""
    name_sw = models.CharField(max_length=150)
    rainfall_band_mm = models.CharField(max_length=60, blank=True)
    altitude_band_m = models.CharField(max_length=60, blank=True)
    planting_window_sw = models.CharField(max_length=120, blank=True)
    harvest_window_sw = models.CharField(max_length=120, blank=True)
    # Kiungo na kanda za zamani za bot (templates). Kinawekwa kwenye import
    # kama crops.Zone yenye jina hilohilo ipo; vinginevyo kinabaki tupu.
    zone = models.ForeignKey('crops.Zone', on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='aezs')

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kanda ya kilimo (AEZ)'
        verbose_name_plural = 'Kanda za kilimo (AEZ)'

    def __str__(self):
        return f"{self.source_id} — {self.name_sw}"


class WardLocation(SourceRecord):
    """Production_Ward_Location_Master — kila kata na kanda yake."""
    region_name = models.CharField(max_length=100, db_index=True)
    district_name = models.CharField(max_length=100, db_index=True)
    council_name = models.CharField(max_length=150, blank=True)
    division_name = models.CharField(max_length=100, blank=True)
    ward_name = models.CharField(max_length=100, db_index=True)
    ward_code = models.CharField(max_length=20, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    aez = models.ForeignKey(Aez, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='wards')
    ecological_zone_sw = models.CharField(max_length=150, blank=True)
    rainfall_band_mm = models.CharField(max_length=60, blank=True)
    altitude_band_m = models.CharField(max_length=60, blank=True)
    planting_window_sw = models.CharField(max_length=120, blank=True)
    harvest_window_sw = models.CharField(max_length=120, blank=True)
    search_key = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        ordering = ['region_name', 'district_name', 'ward_name']
        verbose_name = 'Kata'
        verbose_name_plural = 'Kata (MHD-001)'

    def __str__(self):
        return f"{self.ward_name}, {self.district_name}, {self.region_name}"


class LocationSynonym(SourceRecord):
    """Production_Location_Synonyms — maneno ya mkulima → kata."""
    term = models.CharField(max_length=150, db_index=True)
    location = models.ForeignKey(WardLocation, on_delete=models.CASCADE, related_name='synonyms')

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kisawe cha eneo'
        verbose_name_plural = 'Visawe vya maeneo'

    def __str__(self):
        return f"{self.term} → {self.location}"


class LocationRule(SourceRecord):
    """Production_Location_Rules."""
    name_sw = models.CharField(max_length=200)
    trigger_sw = models.TextField(blank=True)
    action_sw = models.TextField(blank=True)
    farmer_response_sw = models.TextField(blank=True)
    priority = models.IntegerField(default=1)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kanuni ya eneo'
        verbose_name_plural = 'Kanuni za eneo'


# ─────────────────────────── MHD-003A: Mbegu ───────────────────────────

class VarietyRegistry(SourceRecord):
    """Release 1 — Sajili_Aina_Mbegu_Mahindi (utambulisho wa variety, TOSCI)."""
    name = models.CharField(max_length=120)
    registrant = models.CharField(max_length=200, blank=True)
    registration_year = models.CharField(max_length=40, blank=True)
    authority = models.CharField(max_length=60, blank=True)
    record_status = models.CharField(max_length=200, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Aina ya mbegu (sajili)'
        verbose_name_plural = 'Sajili ya aina za mbegu'

    def __str__(self):
        return self.name


class VarietySynonym(SourceRecord):
    """Visawe_Aina_Mbegu — jinsi wakulima wanavyoandika jina la mbegu."""
    term = models.CharField(max_length=120, db_index=True)
    variety = models.ForeignKey(VarietyRegistry, on_delete=models.CASCADE, related_name='synonyms')

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kisawe cha mbegu'
        verbose_name_plural = 'Visawe vya mbegu'


class VarietyAgronomy(SourceRecord):
    """Release 2 — Agronomy_Profile (sifa za kilimo za kila variety)."""
    variety = models.ForeignKey(VarietyRegistry, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='agronomy')
    name = models.CharField(max_length=120)
    company = models.CharField(max_length=200, blank=True)
    seed_type = models.CharField(max_length=60, blank=True)
    grain = models.CharField(max_length=200, blank=True)
    maturity_class = models.CharField(max_length=60, blank=True)
    maturity_days_min = models.IntegerField(null=True, blank=True)
    maturity_days_max = models.IntegerField(null=True, blank=True)
    yield_text = models.CharField(max_length=200, blank=True)
    altitude_text = models.CharField(max_length=300, blank=True)
    altitude_min = models.IntegerField(null=True, blank=True)
    altitude_max = models.IntegerField(null=True, blank=True)
    rainfall_text = models.CharField(max_length=300, blank=True)
    aez_codes = models.JSONField(default=list, blank=True)
    priority_areas = models.TextField(blank=True)
    disease_tolerance = models.TextField(blank=True)
    drought_tolerance = models.TextField(blank=True)
    farmer_advice = models.TextField(blank=True)
    ai_logic = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Sifa za kilimo za mbegu'
        verbose_name_plural = 'Sifa za kilimo za mbegu'

    def __str__(self):
        return f"{self.name} ({self.maturity_class})"

    @property
    def days_text(self):
        if self.maturity_days_min and self.maturity_days_max:
            return f"siku {self.maturity_days_min}–{self.maturity_days_max}"
        return ''


class SeedDecisionRule(SourceRecord):
    """Release 3 — AI_Decision_Engine: hali ya eneo + kigezo → varieties kwa kipaumbele."""
    location_condition = models.TextField(blank=True)
    aez_codes = models.JSONField(default=list, blank=True)
    rain_condition = models.CharField(max_length=200, blank=True)
    altitude_condition = models.CharField(max_length=200, blank=True)
    farmer_criterion = models.CharField(max_length=300, blank=True)
    priority_varieties = models.JSONField(default=list, blank=True)
    ai_action = models.TextField(blank=True)
    farmer_message_sw = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kanuni ya uamuzi wa mbegu'
        verbose_name_plural = 'Kanuni za uamuzi wa mbegu'


class SeedIntent(SourceRecord):
    """Farmer_Intent_Mapping — mkulima anataka nini (mapema, mavuno mengi…)."""
    phrases = models.JSONField(default=list, blank=True)
    intent_code = models.CharField(max_length=60)
    follow_up_question = models.TextField(blank=True)
    suggested = models.JSONField(default=list, blank=True)
    short_answer = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Lengo la mkulima (mbegu)'
        verbose_name_plural = 'Malengo ya mkulima (mbegu)'


class AdvisoryRule(SourceRecord):
    """Sheria_AI_* za kila moduli (trigger → kitendo → ujumbe)."""
    module = models.CharField(max_length=30, db_index=True)
    name_sw = models.CharField(max_length=200)
    trigger = models.TextField(blank=True)
    action = models.TextField(blank=True)
    farmer_message_sw = models.TextField(blank=True)
    priority = models.IntegerField(default=1)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kanuni ya ushauri'
        verbose_name_plural = 'Kanuni za ushauri'


class ExplainTemplate(SourceRecord):
    """Explainability_Templates za kila moduli ({variety}, {rainfall_band}…)."""
    module = models.CharField(max_length=30, db_index=True)
    situation = models.CharField(max_length=200, blank=True)
    template_sw = models.TextField()
    fields = models.CharField(max_length=300, blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kiolezo cha maelezo'
        verbose_name_plural = 'Violezo vya maelezo'


class AdvisoryConfidenceBand(SourceRecord):
    """Confidence_Engine za moduli za ushauri."""
    module = models.CharField(max_length=30, db_index=True)
    label = models.CharField(max_length=40)
    min_score = models.FloatField()
    max_score = models.FloatField()
    meaning = models.TextField(blank=True)
    ai_action = models.TextField(blank=True)

    class Meta(SourceRecord.Meta):
        verbose_name = 'Kiwango cha uhakika (ushauri)'
        verbose_name_plural = 'Viwango vya uhakika (ushauri)'
