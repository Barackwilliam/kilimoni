from django.contrib import admin

from .models import Aez, LocationRule, LocationSynonym, WardLocation


@admin.register(Aez)
class AezAdmin(admin.ModelAdmin):
    list_display = ['source_id', 'name_sw', 'rainfall_band_mm', 'altitude_band_m', 'planting_window_sw', 'zone']
    list_editable = ['zone']


@admin.register(WardLocation)
class WardLocationAdmin(admin.ModelAdmin):
    list_display = ['source_id', 'ward_name', 'district_name', 'region_name', 'aez', 'is_active']
    list_filter = ['region_name', 'aez', 'is_active']
    search_fields = ['ward_name', 'district_name', 'region_name', 'source_id']


@admin.register(LocationSynonym)
class LocationSynonymAdmin(admin.ModelAdmin):
    list_display = ['source_id', 'term', 'location']
    search_fields = ['term']


@admin.register(LocationRule)
class LocationRuleAdmin(admin.ModelAdmin):
    list_display = ['source_id', 'name_sw', 'priority']
