from django.db import models
from crops.models import Crop, Intent, Zone


class AnalyticsLog(models.Model):
    """Taarifa za matumizi ya mfumo"""
    user_id = models.PositiveIntegerField()
    phone_number = models.CharField(max_length=20)
    crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True)
    intent = models.ForeignKey(Intent, on_delete=models.SET_NULL, null=True, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    success_flag = models.BooleanField(default=False)
    response_time_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Analytics Log'
        verbose_name_plural = 'Analytics Logs'

    def __str__(self):
        return f"{self.phone_number} – {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class AdminUser(models.Model):
    """Watu wa ndani wanaoweza kusimamia dashboard"""
    ROLES = [
        ('super_admin', 'Super Admin'),
        ('content_manager', 'Content Manager'),
        ('agronomy_reviewer', 'Agronomy Reviewer'),
        ('data_manager', 'Data Manager'),
        ('viewer', 'Viewer'),
    ]
    STATUS = [('active', 'Active'), ('inactive', 'Inactive')]

    django_user = models.OneToOneField('auth.User', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=30, choices=ROLES, default='viewer')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Admin User'
        verbose_name_plural = 'Admin Users'

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"


class ContentUpdate(models.Model):
    """Historia ya mabadiliko ya content"""
    ACTION_TYPES = [
        ('create', 'Imetengenezwa'),
        ('update', 'Imebadilishwa'),
        ('delete', 'Imefutwa'),
        ('import', 'Imeingizwa (Import)'),
    ]

    admin = models.ForeignKey(AdminUser, on_delete=models.SET_NULL, null=True, blank=True)
    table_name = models.CharField(max_length=100)
    record_id = models.PositiveIntegerField()
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    change_summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Content Update'
        verbose_name_plural = 'Content Updates'

    def __str__(self):
        return f"{self.table_name} #{self.record_id} – {self.get_action_type_display()}"
