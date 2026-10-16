from django.contrib import admin
from .models import (
    Pest, DecisionRule, Symptom, SymptomDiagnosisMap, FollowupQuestion,
    ConfidenceRule, Treatment, TreatmentProtocolStep, SafetyRule,
    RecommendationRule, FarmerMessageTemplate, ExplainabilityRecord,
    ErrorHandlingRule, EngineSetting,
)


class SourceAdmin(admin.ModelAdmin):
    list_filter = ['is_active']
    readonly_fields = ['source_file', 'raw', 'created_at', 'updated_at']


@admin.register(Pest)
class PestAdmin(SourceAdmin):
    list_display = ['source_id', 'name_sw', 'name_en', 'risk_level', 'is_active']
    search_fields = ['source_id', 'name_sw', 'name_en', 'scientific_name']


@admin.register(Symptom)
class SymptomAdmin(SourceAdmin):
    list_display = ['source_id', 'farmer_symptom_sw', 'growth_stage', 'plant_part', 'is_active']
    search_fields = ['source_id', 'farmer_symptom_sw', 'normalized_symptom_sw']
    filter_horizontal = ['likely_pests']


@admin.register(SymptomDiagnosisMap)
class SymptomDiagnosisMapAdmin(SourceAdmin):
    list_display = ['source_id', 'symptom', 'target_type', 'target_id', 'match_strength']


@admin.register(FollowupQuestion)
class FollowupQuestionAdmin(SourceAdmin):
    list_display = ['source_id', 'question_sw', 'symptom', 'if_yes_min', 'if_yes_max',
                    'is_key_differentiator']
    filter_horizontal = ['yes_routes_to']


@admin.register(ConfidenceRule)
class ConfidenceRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'condition', 'condition_code', 'adjustment']
    list_editable = ['condition_code']


@admin.register(DecisionRule)
class DecisionRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'rule_type', 'pest', 'confidence', 'confidence_label', 'followup']


class StepInline(admin.TabularInline):
    model = TreatmentProtocolStep
    extra = 0
    fields = ['source_id', 'step_order', 'step_name', 'farmer_action_sw', 'if_yes', 'if_no']


@admin.register(Treatment)
class TreatmentAdmin(SourceAdmin):
    list_display = ['source_id', 'linked_diagnosis', 'pest', 'severity']
    inlines = [StepInline]


@admin.register(SafetyRule)
class SafetyRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'topic', 'rule']


@admin.register(RecommendationRule)
class RecommendationRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'diagnosis_category', 'condition', 'min_confidence']


@admin.register(FarmerMessageTemplate)
class FarmerMessageTemplateAdmin(SourceAdmin):
    list_display = ['source_id', 'use_case', 'diagnosis_category', 'message_sw']


@admin.register(ExplainabilityRecord)
class ExplainabilityRecordAdmin(SourceAdmin):
    list_display = ['source_id', 'level', 'pest', 'symptom', 'explanation_type']
    list_filter = ['level', 'is_active']


@admin.register(ErrorHandlingRule)
class ErrorHandlingRuleAdmin(SourceAdmin):
    list_display = ['source_id', 'error_code', 'severity', 'blocking']


@admin.register(EngineSetting)
class EngineSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'description', 'updated_at']
    list_editable = ['value']
