from django.contrib import admin
from .models import (
    Pest, DecisionRule, Symptom, SymptomDiagnosisMap, FollowupQuestion,
    ConfidenceRule, Treatment, TreatmentProtocolStep, SafetyRule,
    RecommendationRule, FarmerMessageTemplate, ExplainabilityRecord,
    EngineSetting,
)


class SourceAdmin(admin.ModelAdmin):
    list_filter = ['is_active', 'crop']
    readonly_fields = ['raw', 'created_at', 'updated_at']


@admin.register(Pest)
class PestAdmin(SourceAdmin):
    list_display = ['source_id', 'name_sw', 'name_en', 'cause_type', 'is_active']
    search_fields = ['source_id', 'name_sw', 'name_en', 'scientific_name']


@admin.register(DecisionRule)
class DecisionRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'rule_type', 'pest', 'confidence', 'confidence_label']


@admin.register(Symptom)
class SymptomAdmin(SourceAdmin):
    list_display = ['source_id', 'farmer_description_sw', 'growth_stage', 'plant_part']
    search_fields = ['source_id', 'farmer_description_sw', 'keywords']
    filter_horizontal = ['likely_pests']


@admin.register(SymptomDiagnosisMap)
class SymptomDiagnosisMapAdmin(SourceAdmin):
    list_display = ['source_id', 'symptom', 'pest', 'match_strength']


@admin.register(FollowupQuestion)
class FollowupQuestionAdmin(SourceAdmin):
    list_display = ['source_id', 'question_sw', 'is_key_differentiator', 'priority']
    filter_horizontal = ['symptoms', 'yes_routes_to', 'no_routes_to']


@admin.register(ConfidenceRule)
class ConfidenceRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'condition_code', 'adjustment']


class StepInline(admin.TabularInline):
    model = TreatmentProtocolStep
    extra = 0
    exclude = ['raw']


@admin.register(Treatment)
class TreatmentAdmin(SourceAdmin):
    list_display = ['source_id', 'pest', 'method', 'active_ingredient_category', 'requires_ppe']
    inlines = [StepInline]


@admin.register(SafetyRule)
class SafetyRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'applies_to', 'rule_text_sw']


@admin.register(RecommendationRule)
class RecommendationRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'pest', 'min_confidence', 'min_severity', 'escalate_if_spreading']


@admin.register(FarmerMessageTemplate)
class FarmerMessageTemplateAdmin(SourceAdmin):
    list_display = ['source_id', 'purpose', 'text_sw']


@admin.register(ExplainabilityRecord)
class ExplainabilityRecordAdmin(SourceAdmin):
    list_display = ['source_id', 'pest', 'why_this_sw']


@admin.register(EngineSetting)
class EngineSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'description', 'updated_at']
    list_editable = ['value']
