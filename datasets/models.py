"""
Maktaba ya dataset
==================

SchemaAlias: ramani ya majina yaliyobadilishwa kwenye dataset ya mteja
(sheet au column) → jina ambalo injini inalitarajia. Inaundwa mteja
akithibitisha pendekezo kwenye hakiki; upakiaji unaofuata wenye majina
hayo unasomwa moja kwa moja.
"""
from django.db import models


class SchemaAlias(models.Model):
    KINDS = [('sheet', 'Sheet'), ('column', 'Column')]
    kind = models.CharField(max_length=10, choices=KINDS)
    sheet = models.CharField(max_length=120, blank=True,
                             help_text="Kwa column: sheet inayotarajiwa (jina la injini)")
    expected = models.CharField(max_length=120, help_text="Jina ambalo injini inalitarajia")
    actual = models.CharField(max_length=120, help_text="Jina lililopo kwenye dataset ya mteja")
    method = models.CharField(max_length=20, blank=True, help_text="jina / ai / mkono")
    code = models.CharField(max_length=12, blank=True, help_text="Workbook, mf. MHD-004")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['kind', 'sheet', 'actual']
        ordering = ['code', 'kind', 'sheet', 'expected']
        verbose_name = 'Ramani ya jina (dataset)'
        verbose_name_plural = 'Ramani za majina (dataset)'

    def __str__(self):
        where = f"{self.sheet}." if self.sheet else ''
        return f"{where}{self.actual} → {self.expected}"


class DatasetUpload(models.Model):
    """Kila workbook iliyohifadhiwa kupitia dashboard + uchambuzi wake wakati huo."""
    STATUS = [('engine', 'Inatumiwa na injini'), ('stored', 'Imehifadhiwa tu — moduli bado')]
    file_name = models.CharField(max_length=255)
    code = models.CharField(max_length=12, blank=True, db_index=True)
    family = models.CharField(max_length=255, blank=True, db_index=True,
                              help_text="Jina la faili bila toleo — upakiaji mpya wa familia ileile unachukua nafasi ya zamani")
    status = models.CharField(max_length=10, choices=STATUS)
    engine = models.CharField(max_length=80, blank=True, help_text="Moduli iliyoisoma")
    data_rows = models.PositiveIntegerField(default=0)
    crops = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    sheets = models.JSONField(default=list, blank=True)
    high = models.PositiveIntegerField(default=0)
    medium = models.PositiveIntegerField(default=0)
    uploaded_by = models.CharField(max_length=150, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Upakiaji wa dataset'
        verbose_name_plural = 'Upakiaji wa dataset'

    def __str__(self):
        return f"{self.code or self.file_name} ({self.uploaded_at:%Y-%m-%d})"


class DatasetSheet(models.Model):
    """Sheet ya workbook isiyo na moduli bado — imehifadhiwa kikamilifu ili isipotee."""
    upload = models.ForeignKey(DatasetUpload, on_delete=models.CASCADE, related_name='stored_sheets')
    code = models.CharField(max_length=12, blank=True, db_index=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, default='data')
    columns = models.JSONField(default=list, blank=True)
    id_col = models.CharField(max_length=120, blank=True)
    row_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['code', 'name']


class DatasetRow(models.Model):
    sheet = models.ForeignKey(DatasetSheet, on_delete=models.CASCADE, related_name='rows')
    row_id = models.CharField(max_length=120, blank=True, db_index=True)
    data = models.JSONField(default=dict)

    class Meta:
        ordering = ['id']
