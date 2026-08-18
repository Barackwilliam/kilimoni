from django.db import models
from crops.models import Crop, Intent, Zone


class User(models.Model):
    """Watumiaji wanaotuma maswali kupitia WhatsApp"""
    LANGUAGES = [
        ('sw', 'Kiswahili'),
        ('en', 'English'),
    ]
    STATUS = [('active', 'Active'), ('blocked', 'Blocked')]

    phone_number = models.CharField(max_length=20, unique=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    preferred_language = models.CharField(max_length=5, choices=LANGUAGES, default='sw')
    region = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    active_status = models.CharField(max_length=20, choices=STATUS, default='active')
    message_count = models.PositiveIntegerField(default=0)
    session_state = models.JSONField(default=dict, blank=True)
    last_crop_id = models.IntegerField(null=True, blank=True)
    last_intent = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-last_seen_at']
        verbose_name = 'Mkulima'
        verbose_name_plural = 'Wakulima'

    def __str__(self):
        return self.phone_number

    def get_display_name(self):
        if self.district:
            return f"{self.phone_number} ({self.district})"
        if self.region:
            return f"{self.phone_number} ({self.region})"
        return self.phone_number


class Conversation(models.Model):
    """Kila ujumbe unaotumwa na mkulima na kila jibu linalorudishwa"""
    DIRECTIONS = [
        ('inbound', 'Kutoka kwa Mkulima'),
        ('outbound', 'Kutoka kwa Mfumo'),
    ]
    MESSAGE_TYPES = [
        ('text', 'Maandishi'),
        ('audio', 'Sauti'),
        ('image', 'Picha'),
        ('document', 'Hati'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    message_direction = models.CharField(max_length=10, choices=DIRECTIONS)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    raw_message = models.TextField()
    normalized_text = models.TextField(blank=True)
    detected_crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True)
    detected_intent = models.ForeignKey(Intent, on_delete=models.SET_NULL, null=True, blank=True)
    detected_location = models.CharField(max_length=100, blank=True)
    detected_zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    response_reference = models.CharField(max_length=200, blank=True)
    whatsapp_message_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Mazungumzo'
        verbose_name_plural = 'Mazungumzo'

    def __str__(self):
        return f"{self.user.phone_number} [{self.message_direction}] – {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class UnresolvedQuery(models.Model):
    """Maswali ambayo mfumo haujaelewa au haujapata jibu"""
    REASONS = [
        ('no_intent', 'Intent Haijatambuliwa'),
        ('no_crop', 'Zao Halijapatikana'),
        ('no_answer', 'Jibu Halijapatikana'),
        ('no_location', 'Eneo Halijatambuliwa'),
        ('other', 'Sababu Nyingine'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Inasubiri Review'),
        ('resolved', 'Imeshughulikiwa'),
        ('ignored', 'Imepuuzwa'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='unresolved_queries')
    raw_message = models.TextField()
    normalized_text = models.TextField(blank=True)
    detected_crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True)
    detected_intent = models.ForeignKey(Intent, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=50, choices=REASONS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.CharField(max_length=100, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Swali Lisiloshughulikiwa'
        verbose_name_plural = 'Maswali Yasiyoshughulikiwa'

    def __str__(self):
        return f"{self.user.phone_number}: {self.raw_message[:60]}"
