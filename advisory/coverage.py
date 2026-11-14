"""
Bot inajua nini? — kutoka kwenye data, si kwa kubuni
=====================================================

Mkulima akiuliza "uko na taarifa za mikoa gani?" au "unajua mazao gani?",
bot inajibu kutoka database: maeneo ya MHD-001 (mkoa → wilaya) na mazao
yenye data ya kila moduli. Orodha inabadilika yenyewe mteja akipakia
dataset kamili — hakuna code ya kubadilisha.

Pia: mfano wa ujumbe wa kukaribisha unatumia eneo LILILOMO kwenye data
(zamani ulisema "Singida", ambako data ya sample haikuwa nayo — mkulima
alifuata mfano wa bot na kuambiwa "sina taarifa").
"""
import re
from collections import OrderedDict

META_WORDS = r'(taarifa|data|unajua|mnajua|unafahamu|mnafahamu|unahudumia|mnahudumia|unazo|mnazo|unayo|mnayo|unapatikana|mnapatikana)'
SCOPE = r'(mikoa|mkoa|maeneo|eneo|wilaya|kata|sehemu|mazao|zao)'
WHICH = r'(gani|ipi|zipi|yapi|lipi|mingapi|mangapi|ngapi)'


def wants_coverage(text):
    """'uko na taarifa za mikoa gani', 'unajua mazao gani', 'unahudumia wilaya zipi'."""
    low = ' '.join(re.findall(r"[a-z']+", (text or '').lower()))
    if not re.search(rf'\b{SCOPE}\b', low):
        return False
    return bool(re.search(rf'\b{META_WORDS}\b', low) and re.search(rf'\b{WHICH}\b', low))


def places():
    """OrderedDict mkoa → [wilaya] kutoka MHD-001 (zenye kanda/AEZ tu)."""
    from .models import WardLocation
    out = OrderedDict()
    rows = (WardLocation.objects.filter(is_active=True).exclude(aez=None)
            .values_list('region_name', 'district_name').distinct().order_by('region_name', 'district_name'))
    for region, district in rows:
        out.setdefault(region.strip().title(), [])
        d = district.strip().title()
        if d and d not in out[region.strip().title()]:
            out[region.strip().title()].append(d)
    return out


def places_line(limit=8):
    p = places()
    if not p:
        return ''
    items = [f"{r} ({', '.join(ds[:4])}{'…' if len(ds) > 4 else ''})" if ds else r
             for r, ds in list(p.items())[:limit]]
    more = f" na mingine {len(p) - limit}" if len(p) > limit else ''
    return ', '.join(items) + more


def example_place():
    """Wilaya ya kwanza yenye data — kwa mifano ya bot. Hakuna data → ''."""
    p = places()
    for region, districts in p.items():
        return districts[0] if districts else region
    return ''


def crops_with_data():
    """[(zao, [moduli zenye data])] — kwa kutumia jedwali la uchambuzi wa dataset."""
    from datasets.analysis import coverage
    cov = coverage()
    labels = {'Uchunguzi': 'wadudu na magonjwa', 'Mbegu': 'mbegu', 'Kupanda': 'wakati wa kupanda',
              'Udongo': 'udongo', 'Mzunguko': 'mzunguko wa mazao'}
    return [(row['crop'], [labels[m] for m, n in zip(cov['modules'], row['counts']) if n])
            for row in cov['rows']]


def coverage_message():
    lines = ['📚 *Taarifa nilizonazo kwa sasa*']
    pl = places_line(limit=12)
    if pl:
        lines += ['', f"📍 *Maeneo:* {pl}."]
    else:
        lines += ['', '📍 Bado sina data ya maeneo (kanda za kilimo).']
    crops = crops_with_data()
    if crops:
        lines += ['', '🌾 *Mazao:*'] + [f"• *{c}* — {', '.join(m)}" for c, m in crops]
    lines += ['', '_Taarifa zinaongezwa kadiri data mpya inavyoingia. Kwa eneo ambalo halipo, '
                  'afisa ugani wa eneo lako atakusaidia._']
    ex = example_place()
    if ex:
        lines += ['', f"Mfano wa swali: _Ni mbegu gani ya mahindi nipande {ex}?_"]
    return '\n'.join(lines)


# ── "Mahindi hustawi wapi Tanzania?" ──
GROWS = re.compile(r'\b(\w*stawi|stawi|hustawi|linastawi|linalostawi|yanastawi|yanayostawi|inastawi|inayostawi|hulimwa'
                   r'|linalimwa|yanalimwa|inalimwa|linafaa|yanafaa|inafaa)\b')
WHERE = re.compile(r'\b(wapi|maeneo|mikoa|mkoa gani|sehemu gani|sehemu zipi)\b')
LIST_PLACES = re.compile(r'\b(taja|orodhesha|nitajie|nipe)\b.*\b(maeneo|mikoa|sehemu)\b')


def wants_where_grows(text, has_crop_context=False):
    low = (text or '').lower()
    if GROWS.search(low) and WHERE.search(low):
        return True
    return bool(has_crop_context and LIST_PLACES.search(low) and not wants_coverage(low))


def where_grows_message(crop, repeat=False):
    """Jibu kutoka data tu: hakuna orodha ya mikoa iliyobuniwa."""
    from .models import Aez, CropCalendar, SoilSuitability
    name = crop.crop_name_sw if crop else 'zao hili'
    if repeat:
        zones = ', '.join(Aez.objects.filter(is_active=True).order_by('source_id').values_list('name_sw', flat=True))
        return (f"Samahani, siwezi kukutajia mikoa maalum ambako {name} hustawi zaidi — data yangu bado haina "
                "ulinganisho huo, na sitaki kukupa majina ya kubahatisha. 🙏\n\n"
                + (f"Kanda za kilimo zilizo kwenye data yangu ni: {zones}.\n\n" if zones else '')
                + "Nitajie wilaya au kata yako, nikuambie kwa uhakika kuhusu eneo lako.")
    lines = [f"Swali zuri. 🌱 Kwa uaminifu: bado sina data inayolinganisha mikoa yote ya Tanzania kuonyesha wapi "
             f"*{name}* hustawi zaidi, kwa hiyo sitataja mikoa kwa kubahatisha.", '',
             "Ninachoweza kukuambia kutoka taarifa zangu:"]
    if crop:
        zones = list(CropCalendar.objects.filter(crop=crop, is_active=True).exclude(aez=None)
                     .values_list('aez__name_sw', flat=True).distinct())
        if zones:
            lines.append(f"• Kanda za kilimo zenye kalenda ya {name}: {', '.join(zones)}")
        good = [s.soil.name_sw for s in SoilSuitability.objects.filter(crop=crop, is_active=True)
                .select_related('soil').order_by('-score') if (s.score or 0) >= 75 and s.soil][:4]
        if good:
            lines.append(f"• Udongo unaofaa zaidi {name}: {', '.join(good)}")
    known = places_line(limit=6)
    if known:
        lines.append(f"• Maeneo niliyo na taarifa kamili za kanda: {known}")
    if len(lines) == 3:
        lines.pop()
    lines += ['', f"Ukinitajia *wilaya au kata* yako, nitakuambia kama {name} inafaa huko, mbegu bora na wakati "
                  "wa kupanda."]
    return '\n'.join(lines)
