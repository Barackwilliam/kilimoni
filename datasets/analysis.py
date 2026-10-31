"""
Uchambuzi wa dataset (kila upakiaji)
====================================

Kazi niliyofanya kwa mkono kwenye sample sasa inafanyika yenyewe kwa kila
workbook inayopakiwa — kabla ya kuhifadhi, ndani ya hakiki:

  1. Sheets: rows, columns, ID column, ipi ni data na ipi ni maelezo
     (README, Vyanzo, CMS_Field_Map…), na sheet zenye data ambazo hakuna
     injini iliyozisoma (mf. sheet imebadilishwa jina).
  2. Ramani ya fields ya workbook yenyewe (CMS_Field_Map / Ramani_CMS /
     CMS_Mapping): column inayohitajika ikikosekana, au seli zake tupu.
  3. Validation_Lists za workbook: thamani zisizo kwenye orodha inayoruhusiwa.
  4. Viungo: ID zinazotajwa (Linked_*, *_ID, Target_ID…) lakini hazipo kwenye
     dataset yoyote iliyopakiwa wala kwenye database.
  5. ID zinazojirudia ndani ya sheet moja.
  6. Maandishi ya mkulima yaliyo kwa Kiingereza, au yenye maelekezo ya mfumo
     (yataondolewa kabla ya kumfikia mkulima, lakini yanahitaji kutafsiriwa).
  7. Rows ambazo ni draft/inactive (hazitatumika).
  8. Mazao yaliyomo kwenye kila workbook, na baada ya import: kila zao lina
     data ya moduli zipi (uchunguzi, mbegu, kupanda, udongo, mzunguko).

Inasoma tu — haibadilishi chochote. Viungo vinakaguliwa dhidi ya database
ikiwa ndani ya transaction ya hakiki, hivyo data mpya ya upakiaji huu
inahesabika.
"""
import os
import re
from collections import Counter, OrderedDict

from diagnosis import plain

META_SHEET = re.compile(
    r'readme|metadata|^sources?$|vyanzo|field_?map|ramani|mapping|qa_|_qa|^qa|ukaguzi|dataset_index|faharasa'
    r'|validation_lists?|data_dictionary|adss|integration_index|api_field|release_readiness|import_spec',
    re.I)
FIELD_MAP_SHEET = re.compile(r'field_?map|ramani_cms|cms_mapping', re.I)
VALIDATION_SHEET = re.compile(r'validation_lists?', re.I)

SHEET_COLS = ('jina_la_tab', 'sheet_name', 'source_sheet', 'sheet', 'tab')
FIELD_COLS = ('field_ya_excel', 'field_name', 'workbook_field', 'source_field', 'field')
REQUIRED_COLS = ('inahitajika', 'required')
YES = {'ndiyo', 'yes', 'y', 'true', '1', 'required', 'lazima'}

ID_TOKEN = re.compile(r'\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\d{2,}[A-Z]?\b')
CROP_COLS = ('jina_la_zao', 'crop', 'primary_crop', 'crop_name')
STATUS_COLS = ('cms_status', 'hadhi_ya_cms', 'status', 'record_status')
INACTIVE = ('inactive', 'retired', 'rejected', 'draft')
FARMER_TEXT = re.compile(r'kiswahili|_sw$|^ujumbe|ujumbe_|farmer_message|farmer_response|template_ya_jibu'
                         r'|message_kiswahili|sifa_kwa_lugha|jibu_fupi|maelezo_kwa_mkulima', re.I)
ENGLISH_COL = re.compile(r'english|_en$|^en_|scientific|developer|_note$|notes?$', re.I)
REF_EXCLUDE = re.compile(r'source|chanzo|crop_id|aez_id|url|kiungo', re.I)

LEVELS = OrderedDict([('high', 'Muhimu'), ('medium', 'Rekebisha'), ('info', 'Taarifa')])


def _norm_sheet(title):
    return re.sub(r'^\d+_', '', str(title or '')).strip().lower()


def _rows(ws):
    from diagnosis.importer import _read_sheet
    return _read_sheet(ws)


def _header(ws):
    for r in ws.iter_rows(values_only=True):
        if any(c not in (None, '') for c in r):
            return [str(h).strip() for h in r if h not in (None, '')]
    return []


def _pick(header_lower, options):
    for o in options:
        if o in header_lower:
            return header_lower[o]
    return None


def _is_ref_col(col, id_col):
    c = col.lower()
    if col == id_col or REF_EXCLUDE.search(c):
        return False
    return (c.endswith('_id') or c.endswith('_ids') or c.startswith('linked_') or c.startswith('kitambulisho')
            or c in ('target_id', 'yes_routes_to', 'no_routes_to', 'linked_rules', 'depends_on')
            or c.endswith('_id_inayolingana') or c.endswith('_release1'))


def _id_col(header):
    for h in header[:3]:
        hl = h.lower()
        if hl.endswith('id') or hl.startswith('kitambulisho'):
            return h
    return None


def _prefix(token):
    return re.sub(r'\d+[A-Z]?$', '', token)


def _issue(level, text, sheet='', examples=None):
    return {'level': level, 'level_sw': LEVELS[level], 'text': text, 'sheet': sheet,
            'examples': [str(e)[:140] for e in (examples or [])][:3]}


def _known_db_ids():
    """source_id za records zote za dataset zilizopo kwenye database."""
    from django.apps import apps
    ids = set()
    for model in apps.get_models():
        if model._meta.app_label in ('diagnosis', 'advisory') and any(f.name == 'source_id' for f in model._meta.fields):
            ids.update(model.objects.values_list('source_id', flat=True))
    return ids


def _workbook_code(name):
    base = os.path.basename(str(name)).upper()
    m = re.search(r'MHD-\d{3}[A-Z]?', base)
    return m.group(0) if m else ''


def _field_map(wb):
    """{sheet_norm: [(field, required)]} kutoka sheet ya ramani ya workbook."""
    out = {}
    for ws in wb.worksheets:
        if not FIELD_MAP_SHEET.search(ws.title):
            continue
        rows = _rows(ws)
        if not rows:
            continue
        hl = {k.lower(): k for k in rows[0].keys()}
        sc, fc, rc = _pick(hl, SHEET_COLS), _pick(hl, FIELD_COLS), _pick(hl, REQUIRED_COLS)
        if not (sc and fc):
            continue                      # ramani isiyotaja sheet — haiwezi kukaguliwa kwa sheet
        for r in rows:
            sheet, field = r.get(sc), r.get(fc)
            if sheet and field:
                req = str(r.get(rc) or '').strip().lower() in YES if rc else False
                out.setdefault(_norm_sheet(sheet), []).append((str(field).strip(), req))
    return out


def _validation_lists(wb):
    """{list_name_lower: {allowed_lower}}."""
    lists = {}
    for ws in wb.worksheets:
        if not VALIDATION_SHEET.search(ws.title):
            continue
        rows = _rows(ws)
        if not rows:
            continue
        hl = {k.lower(): k for k in rows[0].keys()}
        if 'list_name' in hl and 'allowed_value' in hl:
            for r in rows:
                n, v = r.get(hl['list_name']), r.get(hl['allowed_value'])
                if n and v is not None:
                    lists.setdefault(str(n).strip().lower(), set()).add(str(v).strip().lower())
        else:                               # kila column ni orodha
            for r in rows:
                for k, v in r.items():
                    if v is not None:
                        lists.setdefault(k.strip().lower(), set()).add(str(v).strip().lower())
    return lists


def analyse_workbook(path, used_sheets=frozenset(), supported=True):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    code = _workbook_code(path)
    fmap, vlists = _field_map(wb), _validation_lists(wb)
    sheets, issues, crops, ids, refs = [], [], Counter(), set(), []
    for ws in wb.worksheets:
        header = _header(ws)
        rows = _rows(ws)
        meta = bool(META_SHEET.search(_norm_sheet(ws.title))) and not re.search(r'explain|rules?$|engine', ws.title, re.I)
        id_col = None if meta else _id_col(header)
        used = (code, ws.title) in used_sheets
        info = {'name': ws.title, 'rows': len(rows), 'columns': len(header), 'id_col': id_col or '',
                'kind': 'meta' if meta else 'data', 'used': used}
        sheets.append(info)
        if meta or not rows:
            continue
        if supported and not used:
            issues.append(_issue('medium', f"Sheet '{ws.title}' ina rows {len(rows)} lakini hakuna injini inayoisoma — "
                                           "data yake imehifadhiwa kwenye workbook tu. Kama ni sheet ya zamani "
                                           "iliyobadilishwa jina, irudishe jina lake la awali.", ws.title))

        # 2. ramani ya fields ya workbook
        expected = fmap.get(_norm_sheet(ws.title), [])
        have = {h.lower() for h in header}
        missing = [f for f, req in expected if req and f.lower() not in have]
        if missing:
            issues.append(_issue('high', f"Columns zinazohitajika (kwa ramani ya workbook) hazipo: {', '.join(missing[:6])}"
                                         f"{'…' if len(missing) > 6 else ''}", ws.title))
        for f, req in expected:
            if req and f.lower() in have:
                col = next(h for h in header if h.lower() == f.lower())
                empty = [r.get(id_col) or '?' for r in rows if r.get(col) in (None, '')]
                if empty:
                    issues.append(_issue('medium', f"'{col}' (inahitajika) iko tupu kwenye rows {len(empty)}", ws.title, empty))

        # 3. orodha za thamani zinazoruhusiwa
        for col in header:
            allowed = vlists.get(col.lower())
            if not allowed:
                continue
            bad = Counter()
            for r in rows:
                v = r.get(col)
                if v is None:
                    continue
                for part in re.split(r'\s*[;|]\s*', str(v)):
                    if part and part.lower() not in allowed:
                        bad[part] += 1
            if bad:
                issues.append(_issue('info', f"'{col}': thamani {sum(bad.values())} si za orodha ya Validation_Lists",
                                     ws.title, [f"{k} (×{n})" for k, n in bad.most_common(3)]))

        # 5. ID zinazojirudia
        if id_col:
            counts = Counter(str(r.get(id_col)).strip() for r in rows if r.get(id_col))
            dup = [k for k, n in counts.items() if n > 1]
            if dup:
                issues.append(_issue('high', f"ID {len(dup)} zinajirudia ndani ya sheet — row ya mwisho ndiyo itabaki",
                                     ws.title, dup))
            ids.update(counts)

        # 4. viungo (vinakaguliwa baada ya kusoma workbooks zote)
        for col in header:
            if _is_ref_col(col, id_col):
                for r in rows:
                    for tok in ID_TOKEN.findall(str(r.get(col) or '')):
                        if not tok.startswith('MHD'):
                            refs.append((ws.title, col, tok, r.get(id_col) or ''))

        # 6. maandishi ya mkulima
        english, system = [], []
        for col in header:
            if not FARMER_TEXT.search(col) or ENGLISH_COL.search(col):
                continue
            for r in rows:
                v = r.get(col)
                if not isinstance(v, str) or len(v.split()) < 3:
                    continue
                for sentence in re.split(r'(?<=[.;])\s+', v):
                    if plain.SYSTEM_NOTE.search(sentence) or plain.AI_START.search(sentence) and not plain.AI_BECAUSE.search(sentence):
                        system.append(f"{r.get(id_col) or '?'}: {sentence}")
                    elif plain._is_english(plain._apply_terms(sentence, plain._terms())):
                        english.append(f"{r.get(id_col) or '?'}: {sentence}")
        if english:
            issues.append(_issue('medium', f"Sentensi {len(english)} za mkulima bado ziko kwa Kiingereza — "
                                           "zitaondolewa kwenye jibu hadi zitafsiriwe (au ziongezwe kwenye kamusi)",
                                 ws.title, english))
        if system:
            issues.append(_issue('info', f"Sentensi {len(system)} kwenye maandishi ya mkulima ni maelekezo ya mfumo — "
                                         "hazitaonyeshwa kwa mkulima", ws.title, system))

        # 7. draft / inactive
        st = next((h for h in header if h.lower() in STATUS_COLS), None)
        if st:
            off = [r.get(id_col) or '?' for r in rows if any(w in str(r.get(st) or '').lower() for w in INACTIVE)]
            if off:
                issues.append(_issue('info', f"Rows {len(off)} zimewekwa '{st}' = draft/inactive — hazitatumika", ws.title, off))

        # 8. mazao
        cc = next((h for h in header if h.lower() in CROP_COLS), None)
        if cc:
            for r in rows:
                if r.get(cc):
                    crops[str(r.get(cc)).strip()] += 1

    data_rows = sum(s['rows'] for s in sheets if s['kind'] == 'data')
    return {'file': os.path.basename(str(path)), 'code': code, 'supported': supported, 'sheets': sheets,
            'issues': issues, 'crops': dict(crops.most_common()), 'ids': ids, 'refs': refs,
            'data_rows': data_rows, 'field_map': bool(fmap), 'validation_lists': bool(vlists)}


def coverage():
    """Kila zao lina data ya moduli zipi (inaitwa ndani ya transaction ya hakiki → inajumuisha upakiaji huu)."""
    from advisory.models import CropCalendar, CropFamily, SoilSuitability, VarietyAgronomy
    from crops.models import Crop
    from diagnosis.models import DiagnosisRule, Pest, Disease
    modules = [('Uchunguzi', lambda c: DiagnosisRule.objects.filter(crop=c, is_active=True).count()
                + Pest.objects.filter(crop=c, is_active=True).count() + Disease.objects.filter(crop=c, is_active=True).count()),
               ('Mbegu', lambda c: VarietyAgronomy.objects.filter(crop=c, is_active=True).count()),
               ('Kupanda', lambda c: CropCalendar.objects.filter(crop=c, is_active=True).count()),
               ('Udongo', lambda c: SoilSuitability.objects.filter(crop=c, is_active=True).count()),
               ('Mzunguko', lambda c: CropFamily.objects.filter(crop=c, is_active=True).count())]
    rows = []
    for crop in Crop.objects.filter(active_status='active').order_by('priority_level', 'crop_name_sw'):
        counts = [fn(crop) for _, fn in modules]
        if any(counts):
            rows.append({'crop': crop.crop_name_sw, 'counts': counts, 'ready': sum(1 for n in counts if n)})
    return {'modules': [m for m, _ in modules], 'rows': rows}


def analyse(paths, reports=(), supported_codes=None):
    """
    paths: faili zilizopakiwa. reports: ImportReport za hakiki (kwa sheets_used).
    Inaitwa ndani ya transaction ya hakiki baada ya import.
    """
    used = set()
    for r in reports:
        used |= getattr(r, 'sheets_used', set())
    books = []
    for p in paths:
        code = _workbook_code(p)
        supported = bool(code) and (supported_codes is None or code in supported_codes or code.startswith('MHD-007'))
        try:
            books.append(analyse_workbook(p, used, supported))
        except Exception as exc:                # faili lililoharibika: ripoti, usikwame
            books.append({'file': os.path.basename(str(p)), 'code': code, 'supported': supported, 'sheets': [],
                          'issues': [_issue('high', f"Faili halikusomeka: {exc}")], 'crops': {}, 'ids': set(),
                          'refs': [], 'data_rows': 0, 'field_map': False, 'validation_lists': False})

    known = set().union(*(b['ids'] for b in books)) | _known_db_ids() if books else set()
    families = {_prefix(i) for i in known if ID_TOKEN.fullmatch(str(i))}
    for b in books:
        broken = OrderedDict()
        for sheet, col, tok, rid in b['refs']:
            if tok not in known and _prefix(tok) in families:
                broken.setdefault((sheet, col), []).append(f"{rid} → {tok}" if rid else tok)
        for (sheet, col), items in broken.items():
            b['issues'].append(_issue('high', f"'{col}': viungo {len(items)} vinaelekeza kwenye ID ambazo hazipo "
                                              "kwenye dataset yoyote", sheet, items))
        b['issues'].sort(key=lambda i: list(LEVELS).index(i['level']))
        b['counts'] = Counter(i['level'] for i in b['issues'])
        b['status'] = ('Haina moduli ya kanuni bado' if not b['supported'] else
                       'Ina mapungufu muhimu' if b['counts'].get('high') else
                       'Iko tayari (rekebisha madogo)' if b['counts'].get('medium') else 'Iko tayari')
        del b['ids'], b['refs']
    summary = {'books': len(books), 'rows': sum(b['data_rows'] for b in books),
               'ready': sum(1 for b in books if b['supported'] and not b['counts'].get('high')),
               'problems': sum(1 for b in books if b['supported'] and b['counts'].get('high')),
               'unsupported': sum(1 for b in books if not b['supported']),
               'high': sum(b['counts'].get('high', 0) for b in books),
               'medium': sum(b['counts'].get('medium', 0) for b in books)}
    return {'books': books, 'coverage': coverage(), 'summary': summary,
            'with_issues': [b for b in books if b['issues'] or not b['supported']],
            'clean': [b for b in books if not b['issues'] and b['supported']]}
