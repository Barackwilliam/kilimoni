"""
Maktaba ya dataset
==================

  - store(): workbook isiyo na moduli ya kanuni bado (mf. MHD-005 mbolea, au
    faili lisilo na msimbo) inahifadhiwa kikamilifu — kila sheet, columns
    zake na kila row kama JSON. Haipotei, inaonekana kwenye dashboard, na
    moduli yake ikijengwa itasomwa kutoka hapa bila kupakia upya. Upakiaji
    mpya wa msimbo uleule unachukua nafasi ya ule wa zamani.
  - record(): baada ya kuhifadhi, kila workbook (yenye moduli au la)
    inaandikwa kwenye historia pamoja na uchambuzi wake wa wakati huo.

Bot HAITUMII data ya maktaba kujibu wakulima — data bila kanuni zake
ingemfanya AI abuni. Inatumika tu baada ya moduli yake kujengwa.
"""
import os
import re

from .models import DatasetRow, DatasetSheet, DatasetUpload

ENGINES = {
    'MHD-001': 'Maeneo na kanda', 'MHD-003A': 'Mbegu', 'MHD-004': 'Udongo',
    'MHD-006': 'Wakati wa kupanda + mzunguko', 'MHD-007': 'Uchunguzi wa matatizo',
}
BATCH = 1000


def family_of(name):
    """'MHD-005_Fertilizer_Tanzania_CMS_v1_2_FULL.xlsx' → 'mhd-005_fertilizer_tanzania_cms'."""
    base = os.path.basename(str(name)).lower()
    base = re.sub(r'\.xlsx$', '', base)
    base = re.sub(r'(_test_sample|_sample|_full|_final)+', '', base)
    return re.sub(r'[_ ]v\d[\d_.]*.*$', '', base)


def engine_for(code):
    return ENGINES.get(code) or ENGINES.get((code or '')[:7], '')


def _code(path):
    from .analysis import _workbook_code
    return _workbook_code(path)


def store(path, report=None, user=''):
    """Hifadhi workbook nzima kwenye maktaba. Rudisha DatasetUpload."""
    import openpyxl
    from diagnosis.importer import _read_sheet
    from .analysis import META_SHEET, _id_col
    from .schema import norm_sheet
    name, code = os.path.basename(str(path)), _code(path)
    family = family_of(name)
    DatasetSheet.objects.filter(upload__family=family).delete()
    upload = DatasetUpload.objects.create(file_name=name, code=code, family=family, status='stored',
                                          uploaded_by=user or '')
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    total = 0
    for ws in wb.worksheets:
        rows = _read_sheet(ws)
        if not rows:
            continue
        header = list(rows[0].keys())
        id_col = _id_col(header) or ''
        sheet = DatasetSheet.objects.create(
            upload=upload, code=code, name=ws.title, columns=header, id_col=id_col, row_count=len(rows),
            kind='meta' if META_SHEET.search(norm_sheet(ws.title)) else 'data')
        objs = [DatasetRow(sheet=sheet, row_id=str(r.get(id_col) or '')[:120],
                           data={k: v for k, v in r.items() if v is not None}) for r in rows]
        for i in range(0, len(objs), BATCH):
            DatasetRow.objects.bulk_create(objs[i:i + BATCH])
        total += len(rows)
        if report is not None:
            report.count('Sheets (maktaba)', True)
            for _ in rows:
                report.count('Rows (maktaba)', True)
    upload.data_rows = total
    upload.save(update_fields=['data_rows'])
    if report is not None:
        report.workbooks.append(code or name)
        report.sheets_used |= {(code, ws.title) for ws in wb.worksheets}
    return upload


def record(analysis, stored=None, user=''):
    """Andika historia ya upakiaji (baada ya kuhifadhi) kutoka ripoti ya uchambuzi."""
    stored = stored or {}
    out = []
    for b in analysis.get('books', []):
        fields = {'data_rows': b['data_rows'], 'crops': b['crops'], 'issues': b['issues'],
                  'sheets': b['sheets'], 'high': b['counts'].get('high', 0), 'medium': b['counts'].get('medium', 0)}
        up = stored.get(b['file'])
        if up:
            for k, v in fields.items():
                setattr(up, k, v)
            up.save()
        else:
            up = DatasetUpload.objects.create(file_name=b['file'], code=b['code'], family=family_of(b['file']),
                                              status='engine',
                                              engine=engine_for(b['code']), uploaded_by=user or '', **fields)
        out.append(up)
    return out


def latest_by_code():
    """Upakiaji wa mwisho kwa kila msimbo/faili (kwa ukurasa wa maktaba)."""
    seen, out = set(), []
    for up in DatasetUpload.objects.all():
        key = up.family or up.file_name
        if key not in seen:
            seen.add(key)
            out.append(up)
    return sorted(out, key=lambda u: (u.status != 'stored', u.code or 'ZZZ', u.file_name))
