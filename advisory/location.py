"""
Kutambua eneo la mkulima (MHD-001)
==================================

LOC-RULE-001 "Tambua kata kwanza": maneno ya mkulima yanalinganishwa na
visawe vya dataset (Production_Location_Synonyms), majina ya kata, wilaya
na mkoa — kwa mpangilio huo (kilicho mahsusi zaidi kwanza).

Matokeo ni dict:
    {'level': 'ward'|'district'|'region', 'matched': 'changaa',
     'location_id': 'LOC-WARD-00001' (kata tu), 'ward': 'Changaa',
     'district': 'Kondoa', 'region': 'Dodoma',
     'aez_id': 'AEZ-003', 'aez_name': 'Kanda ya Kati …',
     'planting_window': 'Novemba-Januari', 'harvest_window': 'Aprili-Juni',
     'candidates': [...]}   # kata zenye jina hilo kwenye wilaya tofauti

Kata yenye jina linalojirudia (wilaya tofauti) inatenganishwa kwa wilaya au
mkoa uliotajwa kwenye ujumbe huohuo; isipotenganishwa, matokeo yanabaki
ngazi ya juu inayoshirikiwa (wilaya/mkoa) na `candidates` zinaorodheshwa.

Kanda (AEZ) ya wilaya au mkoa inatolewa tu kama kata zake zote ziko kanda
moja — vinginevyo aez_id = None (ushauri unaotegemea kanda utauliza kata).
"""
import re
import threading

# Maneno ya kawaida ya Kiswahili ambayo pia ni majina ya maeneo. Yanatambuliwa
# tu yakiwa na muktadha ("kata ya Kati", "niko Mji Mpya").
COMMON_WORDS = {
    'kati', 'mji', 'mjini', 'juu', 'chini', 'kaskazini', 'kusini', 'mashariki',
    'magharibi', 'sasa', 'mara', 'hai', 'pwani', 'tanga', 'bado', 'mpya', 'kubwa',
    'ndogo', 'mbali', 'karibu', 'shamba', 'soko', 'kisima', 'mto', 'ziwa', 'bahari',
    'mlima', 'bonde', 'mahindi', 'mtama', 'maharage', 'mpunga', 'nyanya', 'majani',
}
CONTEXT = r"(?:kata ya|kijiji cha|wilaya ya|mkoa wa|halmashauri ya|niko|nipo|natoka|kutoka|huku)\s+"

_lock = threading.Lock()
_cache = {'version': None, 'index': None}


def clear_cache():
    with _lock:
        _cache['version'] = None
        _cache['index'] = None


def _version():
    from django.db.models import Count, Max

    from .models import LocationSynonym, WardLocation
    w = WardLocation.objects.filter(is_active=True).aggregate(n=Count('id'), t=Max('updated_at'))
    s = LocationSynonym.objects.filter(is_active=True).aggregate(n=Count('id'), t=Max('updated_at'))
    return (w['n'], str(w['t']), s['n'], str(s['t']))


def _norm(text):
    return ' '.join(re.findall(r"[a-z0-9']+", (text or '').lower()))


def _index():
    """term → list ya (kipaumbele, aina, payload). Inajengwa mara moja kwa kila toleo la data."""
    from .models import LocationSynonym, WardLocation
    version = _version()
    with _lock:
        if _cache['version'] == version and _cache['index'] is not None:
            return _cache['index']
    idx = {}

    def add(term, prio, kind, payload):
        term = _norm(term)
        if len(term) >= 3:
            idx.setdefault(term, []).append((prio, kind, payload))

    wards = list(WardLocation.objects.filter(is_active=True).select_related('aez'))
    by_id = {w.pk: w for w in wards}
    for s in LocationSynonym.objects.filter(is_active=True).values('term', 'location_id'):
        if s['location_id'] in by_id:
            add(s['term'], 1, 'ward', s['location_id'])
    for w in wards:
        add(w.ward_name, 2, 'ward', w.pk)
        add(f"{w.ward_name} {w.district_name}", 1, 'ward', w.pk)
        add(w.district_name, 3, 'district', (w.region_name, w.district_name))
        add(w.region_name, 4, 'region', w.region_name)
    index = {'terms': idx, 'wards': by_id, 'max_len': max((len(t.split()) for t in idx), default=1)}
    with _lock:
        _cache['version'], _cache['index'] = version, index
    return index


def _ngrams(words, max_len):
    for n in range(min(max_len, len(words)), 0, -1):
        for i in range(len(words) - n + 1):
            yield ' '.join(words[i:i + n])


def _aez_payload(wards):
    aezs = {w.aez_id for w in wards}
    if len(aezs) == 1 and None not in aezs:
        a = wards[0].aez
        return {'aez_id': a.source_id, 'aez_name': a.name_sw,
                'planting_window': a.planting_window_sw or wards[0].planting_window_sw,
                'harvest_window': a.harvest_window_sw or wards[0].harvest_window_sw}
    return {'aez_id': None, 'aez_name': '', 'planting_window': '', 'harvest_window': ''}


def _ward_result(w, matched, candidates=()):
    out = {'level': 'ward', 'matched': matched, 'location_id': w.source_id,
           'ward': w.ward_name, 'district': w.district_name, 'region': w.region_name,
           'latitude': w.latitude, 'longitude': w.longitude, 'candidates': list(candidates)}
    out.update(_aez_payload([w]))
    if not out['planting_window']:
        out['planting_window'], out['harvest_window'] = w.planting_window_sw, w.harvest_window_sw
    return out


def _area_result(level, matched, wards, region, district=''):
    out = {'level': level, 'matched': matched, 'location_id': None, 'ward': '',
           'district': district, 'region': region, 'latitude': None, 'longitude': None,
           'candidates': []}
    out.update(_aez_payload(wards))
    return out


def resolve(text):
    """Tambua eneo kwenye maandishi. Rudisha dict (tazama juu) au None."""
    try:
        index = _index()
    except Exception:
        return None
    terms, wards = index['terms'], index['wards']
    if not terms:
        return None
    norm = _norm(text)
    words = norm.split()

    found = []        # (kipaumbele, urefu, term, entries)
    for gram in _ngrams(words, index['max_len']):
        if gram not in terms:
            continue
        if gram in COMMON_WORDS and not re.search(CONTEXT + re.escape(gram) + r'\b', norm):
            continue
        found.append((min(p for p, _, _ in terms[gram]), -len(gram), gram, terms[gram]))
    if not found:
        return None
    found.sort()

    mentioned_districts = {p[1].lower() for _, _, _, es in found for _, k, p in es if k == 'district'}
    mentioned_regions = {p.lower() for _, _, _, es in found for _, k, p in es if k == 'region'}

    ambiguous = None
    for _, _, gram, entries in found:
        ward_ids = list(dict.fromkeys(p for _, k, p in entries if k == 'ward'))
        if ward_ids:
            ws = [wards[i] for i in ward_ids]
            if len(ws) > 1:
                narrowed = [w for w in ws if w.district_name.lower() in mentioned_districts] or \
                           [w for w in ws if w.region_name.lower() in mentioned_regions]
                ws = narrowed or ws
            if len(ws) == 1:
                return _ward_result(ws[0], gram)
            districts = {(w.region_name, w.district_name) for w in ws}
            cands = [f"{w.ward_name} ({w.district_name}, {w.region_name})" for w in ws]
            if len(districts) == 1:
                region, district = districts.pop()
                res = _area_result('district', gram, ws, region, district)
            else:
                regions = {w.region_name for w in ws}
                if len(regions) != 1:
                    # Jina la kata liko mikoa tofauti — angalia maneno mengine kwanza
                    ambiguous = ambiguous or {
                        'level': 'ambiguous', 'matched': gram, 'location_id': None, 'ward': '',
                        'district': '', 'region': '', 'latitude': None, 'longitude': None,
                        'aez_id': None, 'aez_name': '', 'planting_window': '', 'harvest_window': '',
                        'candidates': cands}
                    continue
                res = _area_result('region', gram, ws, regions.pop())
            res['candidates'] = cands
            return res
        for _, kind, payload in entries:
            if kind == 'district':
                region, district = payload
                ws = [w for w in wards.values() if w.district_name == district and w.region_name == region]
                return _area_result('district', gram, ws, region, district)
            if kind == 'region':
                ws = [w for w in wards.values() if w.region_name == payload]
                return _area_result('region', gram, ws, payload)
    return ambiguous


def display_name(res):
    if not res or res['level'] == 'ambiguous':
        return ''
    if res['level'] == 'ward':
        return f"{res['ward']}, {res['district']}"
    if res['level'] == 'district':
        return res['district']
    return res['region']


def zone_for(res):
    """crops.Zone ya matokeo (kwa templates za zamani za bot), au None."""
    if not res or res['level'] == 'ambiguous':
        return None
    from crops.models import LocationMapping

    from .models import Aez
    if res.get('aez_id'):
        aez = Aez.objects.filter(source_id=res['aez_id']).select_related('zone').first()
        if aez and aez.zone:
            return aez.zone
    for district, region in ((res.get('district'), res.get('region')), ('', res.get('region'))):
        q = LocationMapping.objects.select_related('zone')
        m = (q.filter(district_name__iexact=district).first() if district
             else q.filter(region_name__iexact=region).first())
        if m:
            return m.zone
    return None
