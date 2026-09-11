from django.contrib import admin
from .models import Subscription, Payment


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'plan_name', 'monthly_fee',
                    'status', 'due_date', 'service_active']
    list_editable = ['status', 'due_date', 'service_active']
    fieldsets = (
        ('Mteja', {'fields': ('client_name', 'plan_name', 'monthly_fee')}),
        ('Kipindi', {'fields': ('period_start', 'due_date', 'grace_days')}),
        ('Hali', {
            'fields': ('status', 'service_active'),
            'description': 'service_active ikizimwa, bot itajibu ujumbe wa '
                           'kusitishwa badala ya kufa kimya.',
        }),
        ('Maelezo', {'fields': ('notes',)}),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['paid_on', 'amount', 'method', 'period_label', 'reference']
    list_filter = ['method', 'paid_on']
    search_fields = ['reference', 'period_label']
