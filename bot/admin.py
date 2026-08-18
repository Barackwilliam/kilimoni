from django.contrib import admin
from .models import User, Conversation, UnresolvedQuery

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'region', 'district', 'message_count', 'active_status', 'last_seen_at']
    list_filter = ['active_status']
    search_fields = ['phone_number', 'region', 'district']

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['user', 'message_direction', 'raw_message', 'detected_crop', 'detected_intent', 'created_at']
    list_filter = ['message_direction', 'detected_crop', 'detected_intent']
    search_fields = ['user__phone_number', 'raw_message']

@admin.register(UnresolvedQuery)
class UnresolvedQueryAdmin(admin.ModelAdmin):
    list_display = ['user', 'raw_message', 'reason', 'status', 'created_at']
    list_filter = ['reason', 'status']
    search_fields = ['raw_message', 'user__phone_number']
