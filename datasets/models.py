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
