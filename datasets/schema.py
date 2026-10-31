"""
Muundo unaobadilika (sheet/column zilizobadilishwa jina)
========================================================

Injini zinasoma sheets na columns kwa majina ya sample za MHD (zile zilizo
kwenye repo: advisory/fixtures, diagnosis/fixtures/mhd007). Hizo ndizo
"muundo unaotarajiwa" — hakuna orodha ya pili ya kutunza kwa mkono.

Dataset kamili ya mteja ikibadilisha jina (mf. 'Soil_Master_Registry' →
'Soil_Master_Registry_v2', au 'jina_la_kiswahili' → 'jina_kiswahili'):

  1. propose(): kila sheet ya data isiyolingana na sheet inayotarajiwa
     inalinganishwa na sheets zinazokosekana (ukaribu wa jina + columns
     zinazofanana). Ndani ya kila sheet, columns zinazokosekana
     zinalinganishwa na columns mpya kwa ukaribu wa jina; zisizoeleweka
     zinapewa AI (orodha funge ya columns zilizopo — haiwezi kubuni).
  2. Hakiki inaonyesha mapendekezo; yenye uhakika yanatumika kwenye hakiki.
  3. Mteja akithibitisha, yanahifadhiwa kama SchemaAlias na kutumika kila
     upakiaji unaofuata (dashboard na management commands).

Utumiaji: diagnosis.importer._find_sheet / _read_sheet zinauliza current()
kwa jina halisi la sheet na columns.
"""
import difflib
import glob
import os
import re
import threading
from contextlib import contextmanager

BASE = os.path.join(os.path.dirname(__file__), '..')
FIXTURE_DIRS = [os.path.join(BASE, 'advisory', 'fixtures'), os.path.join(BASE, 'diagnosis', 'fixtures', 'mhd007')]
SHEET_MIN, COLUMN_MIN, AUTO_APPLY = 0.45, 0.6, 0.7

_expected = None


def norm_sheet(title):
    return re.sub(r'^\d+_', '', str(title or '')).strip().lower()


def _norm_col(name):
    return re.sub(r'[^a-z0-9]', '', str(name or '').lower())


def _tokens(name):
    return {t for t in re.split(r'[^a-z0-9]+', str(name or '').lower()) if t and t not in ('ya', 'la', 'wa', 'za', 'the', 'of')}


def similarity(a, b):
    """Ukaribu wa majina 0–1: herufi (difflib) au maneno yanayofanana, ipi kubwa."""
    ratio = difflib.SequenceMatcher(None, _norm_col(a), _norm_col(b)).ratio()
    ta, tb = _tokens(a), _tokens(b)
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0
    return max(ratio, jac)


def _code(name):
    m = re.search(r'MHD-\d{3}[A-Z]?', os.path.basename(str(name)).upper())
    return m.group(0) if m else ''


def _header_and_samples(ws, n=3):
    rows = [r for r in ws.iter_rows(values_only=True) if any(c not in (None, '') for c in r)]
    if not rows:
        return [], {}, 0
    header = [str(h).strip() if h is not None else '' for h in rows[0]]
    samples = {}
    for i, h in enumerate(header):
        if h:
            vals = [str(r[i])[:40] for r in rows[1:n + 1] if i < len(r) and r[i] not in (None, '')]
            samples[h] = vals
    return [h for h in header if h], samples, len(rows) - 1


def expected():
    """{code: {sheet_norm: {'title', 'columns': [...], 'samples': {col: [..]}}}} kutoka sample za repo."""
    global _expected
    if _expected is None:
        import openpyxl
        out = {}
        for d in FIXTURE_DIRS:
            for path in sorted(glob.glob(os.path.join(d, '*.xlsx'))):
                code = _code(path)
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                for ws in wb.worksheets:
                    header, samples, _ = _header_and_samples(ws)
                    if header:
                        out.setdefault(code, {}).setdefault(norm_sheet(ws.title), []).append(
                            {'title': re.sub(r'^\d+_', '', ws.title), 'columns': header, 'samples': samples})
        _expected = out
    return _expected


# ─────────────────────────── Ramani inayotumika wakati wa import ───────────────────────────

class SchemaMap:
    def __init__(self):
        self.sheets = {}      # sheet_norm inayotarajiwa → jina halisi la sheet
        self.sheet_titles = {}  # sheet_norm inayotarajiwa → jina la injini (herufi kama zilivyo)
        self.columns = {}     # sheet_norm inayotarajiwa → {column halisi: column inayotarajiwa}

    def add(self, kind, sheet, expected_name, actual):
        if kind == 'sheet':
            self.sheets[norm_sheet(expected_name)] = actual
            self.sheet_titles[norm_sheet(expected_name)] = expected_name
        else:
            self.columns.setdefault(norm_sheet(sheet), {})[actual] = expected_name

    def sheet_for(self, expected_name):
        return self.sheets.get(norm_sheet(expected_name))

    def expected_sheet(self, actual_title):
        """Jina la sheet halisi → jina linalotarajiwa (kama ramani ipo)."""
        for exp, act in self.sheets.items():
            if act == actual_title:
                return exp
        return norm_sheet(actual_title)

    def columns_for(self, ws_or_title):
        title = getattr(ws_or_title, 'title', ws_or_title)
        exp = getattr(ws_or_title, '_kilimoni_expected', None) or self.expected_sheet(title)
        return self.columns.get(norm_sheet(exp), {})

    @classmethod
    def from_db(cls):
        m = cls()
        try:
            from .models import SchemaAlias
            for a in SchemaAlias.objects.all():
                m.add(a.kind, a.sheet, a.expected, a.actual)
        except Exception:        # DB bila migration (mf. wakati wa migrate yenyewe)
            pass
        return m


_local = threading.local()


def current():
    m = getattr(_local, 'map', None)
    return m if m is not None else SchemaMap.from_db()


@contextmanager
def use(schema_map):
    previous = getattr(_local, 'map', None)
    _local.map = schema_map
    try:
        yield schema_map
    finally:
        _local.map = previous


def build_map(proposals=(), only_default=True):
    """Ramani = zilizohifadhiwa (DB) + mapendekezo (yote yaliyochaguliwa, au yenye uhakika tu)."""
    m = SchemaMap.from_db()
    for p in proposals:
        if not only_default or p['default']:
            m.add(p['kind'], p['sheet'], p['expected'], p['actual'])
    return m


# ─────────────────────────── Mapendekezo ───────────────────────────

def _is_meta(title):
    from .analysis import META_SHEET
    return bool(META_SHEET.search(norm_sheet(title))) and not re.search(r'explain|rules?$|engine', title, re.I)


def _best_variant(variants, header):
    have = {h.lower() for h in header}
    return max(variants, key=lambda v: len(have & {c.lower() for c in v['columns']}))


def _proposal(code, file, kind, sheet, expected_name, actual, score, method):
    return {'code': code, 'file': file, 'kind': kind, 'sheet': sheet, 'expected': expected_name, 'actual': actual,
            'score': round(score, 2), 'pct': int(round(score * 100)), 'method': method,
            'default': score >= AUTO_APPLY or method == 'ai'}


def _column_proposals(code, file, sheet_title, variant, header, samples, known):
    out = []
    have = {h.lower() for h in header}
    expected_cols = [c for c in variant['columns'] if c.lower() not in have]
    extras = [h for h in header if h.lower() not in {c.lower() for c in variant['columns']} and h not in known.values()]
    if not expected_cols or not extras:
        return out
    pairs = sorted(((similarity(e, x), e, x) for e in expected_cols for x in extras), reverse=True)
    used_e, used_x = set(), set()
    for score, e, x in pairs:
        if score < COLUMN_MIN or e in used_e or x in used_x:
            continue
        used_e.add(e)
        used_x.add(x)
        out.append(_proposal(code, file, 'column', variant['title'], e, x, score, 'jina'))
    # zilizobaki: AI kwa orodha funge ya columns mpya zilizobaki
    from diagnosis import ai_layer
    left = [x for x in extras if x not in used_x]
    if left and ai_layer.available():
        for e in [c for c in expected_cols if c not in used_e][:12]:
            options = {x: ', '.join(samples.get(x, [])) or '(tupu)' for x in left}
            pick = ai_layer.match_column(e, ', '.join(variant['samples'].get(e, [])), options)
            if pick:
                left.remove(pick)
                out.append(_proposal(code, file, 'column', variant['title'], e, pick, similarity(e, pick), 'ai'))
            if not left:
                break
    return out


def propose(paths):
    """Linganisha kila workbook na sample ya msimbo wake. Rudisha list ya mapendekezo."""
    import openpyxl
    exp_all = expected()
    db = SchemaMap.from_db()
    proposals = []
    for path in paths:
        code = _code(path)
        exp = exp_all.get(code)
        if not exp:
            continue
        file = os.path.basename(str(path))
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        actual = {}
        for ws in wb.worksheets:
            header, samples, n = _header_and_samples(ws)
            if header:
                actual[ws.title] = (header, samples, n)
        present = {norm_sheet(t) for t in actual}
        mapped = {db.expected_sheet(t) for t in actual}
        missing = {k: v for k, v in exp.items() if k not in present and k not in mapped}
        matched = []                                   # (title halisi, variant)
        for title, (header, samples, n) in actual.items():
            key = norm_sheet(title)
            if key in exp:
                matched.append((title, _best_variant(exp[key], header)))
                continue
            if db.sheet_for(db.expected_sheet(title)) == title and db.expected_sheet(title) in exp:
                matched.append((title, _best_variant(exp[db.expected_sheet(title)], header)))
                continue
            if _is_meta(title) or n == 0 or not missing:
                continue
            best = None
            for k, variants in missing.items():
                v = _best_variant(variants, header)
                cols = {c.lower() for c in v['columns']}
                overlap = len(cols & {h.lower() for h in header}) / len(cols | {h.lower() for h in header})
                score = 0.5 * similarity(title, v['title']) + 0.5 * overlap
                if best is None or score > best[0]:
                    best = (score, k, v)
            if best and best[0] >= SHEET_MIN:
                score, k, v = best
                proposals.append(_proposal(code, file, 'sheet', '', v['title'], title, score, 'jina'))
                missing.pop(k)
                matched.append((title, v))
        for title, variant in matched:
            header, samples, _ = actual[title]
            known = db.columns.get(norm_sheet(variant['title']), {})
            header = [known.get(h, h) for h in header]
            proposals += _column_proposals(code, file, title, variant, header, samples, known)
    return proposals


def save(proposals):
    from .models import SchemaAlias
    n = 0
    for p in proposals:
        SchemaAlias.objects.update_or_create(
            kind=p['kind'], sheet=p['sheet'] if p['kind'] == 'column' else '', actual=p['actual'],
            defaults={'expected': p['expected'], 'method': p.get('method', ''), 'code': p.get('code', '')})
        n += 1
    return n
