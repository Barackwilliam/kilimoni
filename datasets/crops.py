"""
Mazao mapya kwenye dataset
==========================

Dataset ya zao jipya (mf. maharage) ikipakiwa na zao hilo halipo kwenye
Mazao, importer ilikuwa inaacha `crop` tupu — data inaingia lakini injini
(zinazochuja kwa zao) haziitumii kamwe.

Sasa importers zote mbili (MHD-007 na MHD-001…006) zinapitia CropIntake:

  - Hakiki (dry run): zao lisilopo linaundwa ndani ya transaction ambayo
    itarudishwa nyuma, ili hesabu za hakiki ziwe za kweli, na linaorodheshwa
    kwenye ukurasa wa hakiki pamoja na kundi lake linalokisiwa.
  - Kuhifadhi: zao linaundwa TU kama mteja amelithibitisha kwenye hakiki
    (anaweza kubadilisha jina la Kiswahili/Kiingereza na kundi).
  - Nje ya dashboard (management commands) tabia ni ileile ya zamani:
    hakuna zao linaloundwa bila --create-crops.

Majina: "Mahindi", "Maize", "Mahindi (Maize)" yote yanalingana na zao moja.
KNOWN ni kamusi ya majina tu (Kiingereza ↔ Kiswahili ↔ kundi), si ushauri.
"""
import re
import threading
from contextlib import contextmanager

# en → (sw, kundi)
KNOWN = {
    'maize': ('Mahindi', 'cereals'), 'rice': ('Mpunga', 'cereals'), 'paddy': ('Mpunga', 'cereals'),
    'sorghum': ('Mtama', 'cereals'), 'pearl millet': ('Uwele', 'cereals'), 'millet': ('Uwele', 'cereals'),
    'finger millet': ('Ulezi', 'cereals'), 'wheat': ('Ngano', 'cereals'), 'barley': ('Shayiri', 'cereals'),
    'beans': ('Maharage', 'legumes'), 'common bean': ('Maharage', 'legumes'), 'common beans': ('Maharage', 'legumes'),
    'bean': ('Maharage', 'legumes'), 'groundnut': ('Karanga', 'legumes'), 'groundnuts': ('Karanga', 'legumes'),
    'peanut': ('Karanga', 'legumes'), 'cowpea': ('Kunde', 'legumes'), 'cowpeas': ('Kunde', 'legumes'),
    'pigeon pea': ('Mbaazi', 'legumes'), 'pigeonpea': ('Mbaazi', 'legumes'), 'green gram': ('Choroko', 'legumes'),
    'chickpea': ('Dengu', 'legumes'), 'soybean': ('Soya', 'legumes'), 'soya bean': ('Soya', 'legumes'),
    'peas': ('Njegere', 'legumes'), 'garden pea': ('Njegere', 'legumes'),
    'cassava': ('Muhogo', 'roots'), 'sweet potato': ('Viazi vitamu', 'roots'),
    'irish potato': ('Viazi mviringo', 'roots'), 'potato': ('Viazi mviringo', 'roots'), 'yam': ('Viazi vikuu', 'roots'),
    'tomato': ('Nyanya', 'vegetables'), 'onion': ('Vitunguu', 'vegetables'), 'cabbage': ('Kabichi', 'vegetables'),
    'sweet pepper': ('Hoho', 'vegetables'), 'pepper': ('Pilipili', 'vegetables'), 'chilli': ('Pilipili', 'vegetables'),
    'amaranth': ('Mchicha', 'vegetables'), 'eggplant': ('Biringanya', 'vegetables'), 'okra': ('Bamia', 'vegetables'),
    'watermelon': ('Tikiti maji', 'fruits'), 'carrot': ('Karoti', 'vegetables'), 'spinach': ('Spinachi', 'vegetables'),
    'banana': ('Ndizi', 'fruits'), 'mango': ('Embe', 'fruits'), 'avocado': ('Parachichi', 'fruits'),
    'orange': ('Machungwa', 'fruits'), 'pineapple': ('Nanasi', 'fruits'), 'papaya': ('Papai', 'fruits'),
    'coffee': ('Kahawa', 'cash_crops'), 'tea': ('Chai', 'cash_crops'), 'cotton': ('Pamba', 'cash_crops'),
    'cashew': ('Korosho', 'cash_crops'), 'cashew nut': ('Korosho', 'cash_crops'), 'tobacco': ('Tumbaku', 'cash_crops'),
    'sunflower': ('Alizeti', 'cash_crops'), 'sesame': ('Ufuta', 'cash_crops'), 'simsim': ('Ufuta', 'cash_crops'),
    'sugarcane': ('Miwa', 'cash_crops'), 'sisal': ('Mkonge', 'cash_crops'), 'cocoa': ('Kakao', 'cash_crops'),
    'coconut': ('Nazi', 'cash_crops'), 'cloves': ('Karafuu', 'cash_crops'),
}
SW = {sw.lower(): (en, group) for en, (sw, group) in KNOWN.items()}
# Kiingereza kinachopendelewa kwa jina la Kiswahili (si 'paddy' kwa Mpunga)
PREFERRED_EN = {}
for _en, (_sw, _g) in KNOWN.items():
    PREFERRED_EN.setdefault(_sw.lower(), _en)


def split_name(name):
    """'Mahindi (Maize)' → ('Mahindi', 'Maize'); 'Maize' → ('Mahindi', 'Maize'); 'Ufuta' → ('Ufuta', 'Sesame')."""
    text = re.sub(r'\s+', ' ', str(name or '')).strip()
    if not text:
        return '', ''
    m = re.match(r'^(.*?)\s*[(/]\s*(.*?)\s*\)?$', text)
    a, b = (m.group(1), m.group(2)) if m and m.group(2) else (text, '')
    for first, second in ((a, b), (b, a)):
        if first.lower() in KNOWN and not (second and second.lower() in SW):
            return (second or KNOWN[first.lower()][0]), first
    if a.lower() in SW:
        return a, b or PREFERRED_EN[a.lower()].title()
    if b and b.lower() in SW:
        return b, a
    return a, b


def guess_group(sw, en):
    for key, table in ((en.lower(), KNOWN), (sw.lower(), SW)):
        if key in table:
            return table[key][1]
    return ''


def key_of(name):
    sw, en = split_name(name)
    return (sw or en).lower()


def find(sw, en):
    from django.db.models import Q
    from crops.models import Crop
    names = [n for n in (sw, en) if n]
    if not names:
        return None
    q = Q()
    for n in names:
        q |= Q(crop_name_sw__iexact=n) | Q(crop_name_en__iexact=n)
    return Crop.objects.filter(q).order_by('id').first()


class CropIntake:
    """
    create:   ruhusu kuunda mazao yasiyopo.
    approved: None = yote yanaruhusiwa; dict key → {'name_sw','name_en','group'}
              = yale tu yaliyothibitishwa na mteja (kwa majina aliyoyaweka).
    """

    def __init__(self, create=False, approved=None):
        self.create = create
        self.approved = approved
        self.new = {}        # key → info ya zao lisilopo
        self._cache = {}

    def resolve(self, name, source=''):
        if not name or not str(name).strip():
            return None
        key = key_of(name)
        if key in self._cache:
            if key in self.new:
                self._note(key, source)
            return self._cache[key]
        sw, en = split_name(name)
        override = (self.approved or {}).get(key) if isinstance(self.approved, dict) else None
        crop = find(sw, en) or (find(override['name_sw'], override['name_en']) if override else None)
        if crop is None:
            info = self.new.setdefault(key, {
                'key': key, 'raw': str(name).strip(), 'name_sw': sw, 'name_en': en or sw,
                'group': guess_group(sw, en), 'count': 0, 'sources': [], 'created': False})
            self._note(key, source)
            if self.create and (self.approved is None or override):
                crop = self._make(override or info)
                info['created'] = True
        self._cache[key] = crop
        return crop

    def _note(self, key, source):
        info = self.new[key]
        info['count'] += 1
        src = source.split('/')[0] if source else ''
        if src and src not in info['sources']:
            info['sources'].append(src)

    @staticmethod
    def _make(info):
        from crops.models import Crop
        group = info.get('group') or 'cash_crops'
        return Crop.objects.create(crop_name_sw=info['name_sw'][:100], crop_name_en=(info['name_en'] or info['name_sw'])[:100],
                                   crop_group=group, priority_level=3, active_status='active')

    @property
    def missing(self):
        return sorted(self.new.values(), key=lambda i: (-i['count'], i['key']))


_local = threading.local()


def current():
    intake = getattr(_local, 'intake', None)
    if intake is None:
        intake = CropIntake()          # tabia ya zamani: usiunde, rudisha None
    return intake


@contextmanager
def use(intake):
    previous = getattr(_local, 'intake', None)
    _local.intake = intake
    try:
        yield intake
    finally:
        _local.intake = previous


def resolve(name, source=''):
    return current().resolve(name, source)


def check_crop_conflict(model, sid, crop):
    """
    Dataset za mazao tofauti zikitumia ID ileile (mf. PEST-001 ya mahindi na
    PEST-001 ya maharage), upsert ingeandika juu ya data ya zao la kwanza.
    Row hiyo inakataliwa badala yake (inaingia kwenye makosa ya hakiki).
    """
    if crop is None or not hasattr(model, 'crop'):
        return
    other = (model.objects.filter(source_id=sid).exclude(crop=None).exclude(crop=crop)
             .values_list('crop__crop_name_sw', flat=True).first())
    if other:
        raise ValueError(f"ID '{sid}' tayari inatumika kwa {other} — data ya {crop.crop_name_sw} haiwezi "
                         "kuiandika juu. Tumia ID tofauti kwa zao hili (mf. kiambishi cha zao).")
