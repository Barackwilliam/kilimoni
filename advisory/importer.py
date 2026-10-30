"""
Import ya Excel za MHD-001 … MHD-006 kwenda kwenye tables za advisory.

Kanuni zilezile za diagnosis/importer.py (MHD-007):
  - Upsert kwa ID ya dataset (location_id, aez_id, …) — kurudia ni salama.
  - Dry run = import halisi ndani ya transaction kisha rollback, hivyo
    ripoti ya hakiki inasema ukweli.
  - Makosa yakizidi 2% ya rows, batch nzima inarudishwa nyuma.

Kila workbook ina handler yake kwenye WORKBOOKS. Hatua zinazofuata
(mbegu, msimu, udongo, mzunguko) zinaongeza handlers hapa.
"""
import os
import re

from django.db import transaction

from diagnosis.importer import (
    MAX_FAILURE_RATIO, ImportReport, _Rollback, _find_sheet, _float, _read_sheet,
)

from .models import Aez, LocationRule, LocationSynonym, WardLocation


def workbook_code(name):
    """'MHD-001_Location…xlsx' → 'MHD-001'; 'MHD-003A_Seed…' → 'MHD-003A'."""
    base = os.path.basename(str(name)).upper()
    m = re.search(r'MHD-00[1-6][A-Z]?', base)
    return m.group(0) if m else None


def _active(row, col='cms_status'):
    status = (row.get(col) or '')
    status = str(status).lower()
    return not any(w in status for w in ('inactive', 'retired', 'rejected', 'draft only'))


class _Importer:
    def __init__(self, report):
        self.r = report

    def rows(self, wb, code, sheet_name, label, id_col, handler):
        ws = _find_sheet(wb, sheet_name)
        if ws is None:
            self.r.warnings.append(f"{code}: sheet '{sheet_name}' haipo — imerukwa")
            return
        source = f"{code}/{ws.title}"
        for row in _read_sheet(ws):
            sid = row.get(id_col)
            if not sid:
                continue
            self.r.rows_total += 1
            try:
                with transaction.atomic():
                    created = handler(str(sid).strip(), row, source)
                if created is not None:
                    self.r.count(label, created)
            except Exception as e:
                self.r.errors.append(f"{source} {sid}: {e}")

    @staticmethod
    def upsert(model, sid, source, row, **fields):
        raw = {k: v for k, v in row.items() if v is not None}
        obj, created = model.objects.update_or_create(
            source_id=sid, defaults={'source_file': source, 'raw': raw,
                                     'is_active': _active(row), **fields})
        return obj, created

    # ─────────────── MHD-001: Eneo ───────────────

    def import_001(self, wb):
        from crops.models import Zone

        def aez(sid, row, source):
            name = row.get('ecological_zone_sw') or sid
            zone = Zone.objects.filter(zone_name__iexact=name).first()
            _, created = self.upsert(
                Aez, sid, source, row, name_sw=name,
                rainfall_band_mm=row.get('rainfall_band_mm') or '',
                altitude_band_m=row.get('altitude_band_m') or '',
                planting_window_sw=row.get('planting_window_sw') or '',
                harvest_window_sw=row.get('harvest_window_sw') or '',
                **({'zone': zone} if zone else {}))
            return created

        def ward(sid, row, source):
            if not row.get('ward_name') or not row.get('district_name') or not row.get('region_name'):
                raise ValueError('ward_name, district_name na region_name zinahitajika')
            aez_id = row.get('primary_aez_id')
            aez_obj = Aez.objects.filter(source_id=aez_id).first() if aez_id else None
            if aez_id and aez_obj is None:
                self.r.warnings.append(f"{source} {sid}: AEZ '{aez_id}' haipo kwenye AEZ_Master")
            lat, lng = _float(row.get('latitude')), _float(row.get('longitude'))
            if lat is not None and not (-12.5 <= lat <= -0.9) or lng is not None and not (29 <= lng <= 41):
                self.r.warnings.append(f"{source} {sid}: coordinates ({lat}, {lng}) ziko nje ya Tanzania")
            _, created = self.upsert(
                WardLocation, sid, source, row,
                region_name=row['region_name'], district_name=row['district_name'],
                council_name=row.get('council_name') or '', division_name=row.get('division_name') or '',
                ward_name=row['ward_name'], ward_code=str(row.get('ward_code') or ''),
                latitude=lat, longitude=lng, aez=aez_obj,
                ecological_zone_sw=row.get('ecological_zone_sw') or '',
                rainfall_band_mm=row.get('rainfall_band_mm') or '',
                altitude_band_m=row.get('altitude_band_m') or '',
                planting_window_sw=row.get('planting_window_sw') or '',
                harvest_window_sw=row.get('harvest_window_sw') or '',
                search_key=row.get('location_search_key') or '')
            return created

        def synonym(sid, row, source):
            loc = WardLocation.objects.filter(source_id=row.get('location_id')).first()
            if loc is None:
                raise ValueError(f"location_id '{row.get('location_id')}' haipo")
            term = (row.get('input_term') or '').strip().lower()
            if not term:
                raise ValueError('input_term tupu')
            _, created = self.upsert(LocationSynonym, sid, source, row, term=term, location=loc)
            return created

        def rule(sid, row, source):
            _, created = self.upsert(
                LocationRule, sid, source, row, name_sw=row.get('rule_name_sw') or sid,
                trigger_sw=row.get('trigger_sw') or '', action_sw=row.get('action_sw') or '',
                farmer_response_sw=row.get('farmer_response_sw') or '',
                priority=int(_float(row.get('priority')) or 1))
            return created

        code = 'MHD-001'
        self.rows(wb, code, 'AEZ_Master', 'Kanda za kilimo (AEZ)', 'aez_id', aez)
        self.rows(wb, code, 'Production_Ward_Location_Master', 'Kata', 'location_id', ward)
        self.rows(wb, code, 'Production_Location_Synonyms', 'Visawe vya maeneo', 'synonym_id', synonym)
        self.rows(wb, code, 'Production_Location_Rules', 'Kanuni za eneo', 'rule_id', rule)

        # QA: kisawe kimoja kinachoelekeza kata nyingi ni cha wilaya/mkoa, si cha kata.
        from django.db.models import Count
        multi = (LocationSynonym.objects.values('term').annotate(n=Count('location', distinct=True))
                 .filter(n__gt=1))
        for m in multi:
            self.r.warnings.append(
                f"MHD-001 kisawe '{m['term']}' kinaelekeza kata {m['n']} tofauti — bot itakitumia "
                "kutambua wilaya/mkoa tu, si kata mahsusi")


# Mpangilio wa import: eneo kwanza (wengine wanategemea AEZ).
WORKBOOKS = [
    ('MHD-001', 'import_001'),
]
SUPPORTED_CODES = [code for code, _ in WORKBOOKS]


def import_files(files, dry_run=False):
    """files: paths au UploadedFile. Inarudisha ImportReport."""
    import openpyxl

    report = ImportReport(dry_run)
    books = {}
    for f in files:
        code = workbook_code(getattr(f, 'name', f))
        if code not in SUPPORTED_CODES:
            report.warnings.append(f"'{os.path.basename(str(getattr(f, 'name', f)))}' bado haina importer — imerukwa")
            continue
        books[code] = openpyxl.load_workbook(f, read_only=True, data_only=True)
    report.workbooks = sorted(books)
    imp = _Importer(report)
    try:
        with transaction.atomic():
            for code, method in WORKBOOKS:
                if code in books:
                    getattr(imp, method)(books[code])
            if report.failure_ratio > MAX_FAILURE_RATIO:
                report.rolled_back = True
                raise _Rollback()
            if dry_run:
                raise _Rollback()
    except _Rollback:
        pass
    from .location import clear_cache
    clear_cache()
    return report
