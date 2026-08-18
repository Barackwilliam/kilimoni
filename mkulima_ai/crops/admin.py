from django.contrib import admin
from .models import Zone, LocationMapping, Crop, CropProfile, SeedVariety, Intent, FarmerQuestion, Synonym, AnswerTemplate

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['zone_name', 'rain_pattern_simple', 'rainfall_band_mm', 'altitude_band_m']
    search_fields = ['zone_name']

@admin.register(LocationMapping)
class LocationMappingAdmin(admin.ModelAdmin):
    list_display = ['region_name', 'district_name', 'zone']
    list_filter = ['zone']
    search_fields = ['region_name', 'district_name']

@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ['crop_name_sw', 'crop_name_en', 'crop_group', 'priority_level', 'active_status']
    list_filter = ['crop_group', 'active_status']

@admin.register(CropProfile)
class CropProfileAdmin(admin.ModelAdmin):
    list_display = ['crop', 'zone', 'planting_window_simple', 'maturity_days_min', 'maturity_days_max']
    list_filter = ['crop', 'zone']

@admin.register(SeedVariety)
class SeedVarietyAdmin(admin.ModelAdmin):
    list_display = ['variety_name', 'crop', 'recommended_zone', 'maturity_class', 'drought_tolerance', 'verification_status']
    list_filter = ['crop', 'maturity_class', 'verification_status']
    search_fields = ['variety_name']

@admin.register(Intent)
class IntentAdmin(admin.ModelAdmin):
    list_display = ['intent_name', 'description_sw', 'required_entities']
    search_fields = ['intent_name']

@admin.register(FarmerQuestion)
class FarmerQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'crop', 'intent', 'location', 'active_status']
    list_filter = ['crop', 'intent', 'active_status']
    search_fields = ['question_text', 'keywords']

@admin.register(Synonym)
class SynonymAdmin(admin.ModelAdmin):
    list_display = ['variation', 'main_word', 'category', 'crop']
    list_filter = ['category', 'crop']
    search_fields = ['main_word', 'variation']

@admin.register(AnswerTemplate)
class AnswerTemplateAdmin(admin.ModelAdmin):
    list_display = ['answer_reference', 'intent', 'crop', 'zone', 'active_status']
    list_filter = ['intent', 'crop', 'zone', 'active_status']
    search_fields = ['answer_reference', 'answer_text_sw']
