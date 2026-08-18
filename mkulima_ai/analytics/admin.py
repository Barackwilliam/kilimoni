from django.contrib import admin
from .models import AnalyticsLog, AdminUser, ContentUpdate

@admin.register(AnalyticsLog)
class AnalyticsLogAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'crop', 'intent', 'zone', 'success_flag', 'response_time_ms', 'created_at']
    list_filter = ['success_flag', 'crop', 'intent']

@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'email', 'status', 'created_at']
    list_filter = ['role', 'status']

@admin.register(ContentUpdate)
class ContentUpdateAdmin(admin.ModelAdmin):
    list_display = ['admin', 'table_name', 'action_type', 'change_summary', 'created_at']
    list_filter = ['action_type', 'table_name']
