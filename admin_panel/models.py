from django.db import models
from django.utils import timezone
from datetime import timedelta


class Subscription(models.Model):
    """
    Hali ya huduma ya mteja. Kuna rekodi MOJA inayotumika.
    JamiiTek ndiye anayeibadilisha kupitia Django admin —
    mteja anaiona tu kwenye dashboard.
    """

    STATUS_CHOICES = [
        ('trial', 'Ofa ya Uzinduzi'),
        ('active', 'Imelipwa'),
        ('pending', 'Inasubiri Malipo'),
        ('overdue', 'Imechelewa'),
        ('suspended', 'Imesitishwa'),
    ]

    client_name = models.CharField(max_length=120, default='Kilimoni LABS')
    plan_name = models.CharField(max_length=120, default='Huduma ya Mwezi')
    monthly_fee = models.PositiveIntegerField(default=50000, help_text='TZS')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')

    period_start = models.DateField(default=timezone.now)
    due_date = models.DateField(help_text='Tarehe ya mwisho ya malipo ya kipindi hiki')

    grace_days = models.PositiveIntegerField(
        default=7,
        help_text='Siku za neema baada ya tarehe ya malipo kupita'
    )

    service_active = models.BooleanField(
        default=True,
        help_text='Ikizimwa, bot itajibu ujumbe wa "huduma imesitishwa"'
    )

    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Huduma (Subscription)'
        verbose_name_plural = 'Huduma (Subscription)'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.client_name} — {self.get_status_display()}"

    @property
    def days_remaining(self):
        return (self.due_date - timezone.now().date()).days

    @property
    def is_overdue(self):
        return timezone.now().date() > self.due_date

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    @property
    def grace_left(self):
        return max(0, self.grace_days - self.days_overdue)

    @classmethod
    def current(cls):
        sub = cls.objects.first()
        if not sub:
            today = timezone.now().date()
            sub = cls.objects.create(
                period_start=today,
                due_date=today + timedelta(days=30),
                status='trial',
            )
        return sub


class Payment(models.Model):
    """Rekodi ya malipo. JamiiTek ndiye anayeyaingiza."""

    METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('mixx', 'Mixx by Yas'),
        ('airtel', 'Airtel Money'),
        ('halopesa', 'HaloPesa'),
        ('bank', 'Benki'),
        ('cash', 'Taslimu'),
    ]

    amount = models.PositiveIntegerField(help_text='TZS')
    paid_on = models.DateField(default=timezone.now)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='mpesa')
    reference = models.CharField(max_length=80, blank=True, help_text='Namba ya muamala')
    period_label = models.CharField(max_length=60, blank=True, help_text='Mfano: Oktoba 2026')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Malipo'
        verbose_name_plural = 'Malipo'
        ordering = ['-paid_on', '-created_at']

    def __str__(self):
        return f"TZS {self.amount:,} — {self.period_label or self.paid_on}"
