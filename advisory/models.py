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
