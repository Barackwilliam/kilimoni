"""
Foleni ya jumbe zinazoingia kutoka bridge
==========================================

Kila ujumbe unahifadhiwa hapa KABLA Django haijajibu bridge "200". Kisha
mfanyakazi aliyeshika kufuli ya mkulima (Postgres advisory lock) anashughulikia
jumbe zote za mkulima huyo kwa mpangilio ziliofika (id).

Kwa nini si foleni ya kumbukumbu (memory) pekee:
  - gunicorn ina workers kadhaa: ujumbe 1 unaweza kufika worker A na ujumbe 2
    worker B; foleni ya memory ingehakikisha mpangilio ndani ya worker mmoja tu.
  - Django ikizimwa/kudeploy katikati, jumbe zilizosubiri zingepotea kimya.
"""
from django.db import models


class IncomingMessage(models.Model):
    STATUS = [('pending', 'Inasubiri'), ('done', 'Imejibiwa'), ('failed', 'Imeshindwa')]
    phone = models.CharField(max_length=32, db_index=True)
    message_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS, default='pending', db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['phone', 'status', 'id'])]
        verbose_name = 'Ujumbe unaoingia (foleni)'
        verbose_name_plural = 'Foleni ya jumbe zinazoingia'

    def __str__(self):
        return f"{self.phone} #{self.id} ({self.status})"
