"""
Msaada wa mtiririko wa uchunguzi
================================

Utambuzi wa ujumbe wa tatizo / ombi pana, swali la lengo, na ukaguzi wa
jibu (output validation). Uchunguzi wenyewe (maswali, confidence, uamuzi)
unafanywa na rules engine: diagnosis/engine.py.

KANUNI ZA USALAMA:
  - Hakuna utambuzi, dawa, kiwango (dosage) wala mara za matumizi
    (frequency) mpaka taarifa muhimu zote zikusanywe.
  - Majibu yanatoka kwenye records za zao MOJA pekee.
  - AI inaelewa lugha na kuandika jibu; haibuni maarifa. Inapewa
    records za dataset pekee, na jibu lake linakaguliwa kabla ya
    kutumwa (output validation).
"""
import re
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# MISAMIATI
# ═══════════════════════════════════════════════════════

# Maneno yanayoonyesha mkulima ana TATIZO shambani
PROBLEM_STEMS = (
    'umwa', 'ugonjwa', 'magonjwa', 'wadudu', 'mdudu', 'viwavi', 'kiwavi',
    'funza', 'dalili', 'tatizo', 'shida', 'nyauka', 'kauka', 'njano',
    'madoa', 'doa', 'mashimo', 'shimo', 'kuoza', 'oza', 'kufa', 'yanakufa',
    'yamekufa', 'haikui', 'hayakui', 'dhaifu', 'harib', 'kutu', 'ukungu',
    'kahawia', 'mabaka', 'kujikunja', 'jikunja', 'kudumaa', 'dumaa',
    # Maneno ya kawaida ya wakulima yasiyotaja "ugonjwa/wadudu" moja kwa moja
    'kinakula', 'vinakula', 'wanakula', 'anakula', 'imeliwa', 'yameliwa', 'zimeliwa',
    'meliwa', 'kuliwa', 'tobo', 'tobolewa', 'nyauk', 'pukutika', 'ungua', 'kunjamana',
    'mistari', 'michirizi', 'kinyesi', 'chafu', 'haistawi', 'hayastawi',
)

# Maneno ya ombi pana lisilo na maelezo
BROAD_STEMS = (
    'msaada', 'nisaidie', 'saidia', 'ushauri', 'kilimo', 'naomba',
    'nahitaji', 'swali', 'maelekezo', 'elimu',
)

PROBLEM_INTENTS = ('pest_identification', 'disease_identification', 'symptom_analysis')

# Mazao yanayoweza kuchanganywa kwenye jibu (kwa output validation)
KNOWN_CROPS = (
    'mahindi', 'maharage', 'mpunga', 'mtama', 'alizeti', 'muhogo',
    'viazi', 'ufuta', 'karanga', 'pamba', 'kahawa', 'chai', 'korosho',
    'ndizi', 'nyanya', 'mbaazi', 'choroko', 'ulezi', 'ngano', 'shayiri',
    'miwa', 'tumbaku', 'vitunguu', 'kabichi', 'maize', 'beans', 'rice',
    'sorghum', 'sunflower', 'cassava',
)

# Majina mbadala ya zao moja (Kiswahili/Kiingereza) — yasichukuliwe
# kama "zao jingine" na validator. Mfano "Maize Streak Virus" ni
# ugonjwa wa mahindi, si zao tofauti.
CROP_ALIASES = {
    'mahindi': ('maize', 'corn'),
    'maharage': ('beans', 'bean'),
    'mpunga': ('rice', 'mchele'),
    'mtama': ('sorghum',),
    'alizeti': ('sunflower',),
    'muhogo': ('cassava',),
}

# ═══════════════════════════════════════════════════════
# UTAMBUZI WA LENGO
# ═══════════════════════════════════════════════════════

def _has_stem(text: str, stems) -> bool:
    words = re.findall(r"[a-z%']+", (text or '').lower())
    return any(w.startswith(s) or s in w for w in words for s in stems)


def is_problem_message(text: str, intent=None) -> bool:
    """Mkulima anaeleza tatizo la zao (ugonjwa, wadudu, dalili)."""
    if intent is not None and getattr(intent, 'intent_name', '') in PROBLEM_INTENTS:
        return True
    return _has_stem(text, PROBLEM_STEMS)


def is_broad_request(text: str, crop, intent, location) -> bool:
    """
    Ombi pana lisilo na maelezo ya kutosha, mfano:
    "Naomba msaada kuhusu kilimo". Hapa HATUTOI ushauri wowote;
    tunauliza lengo kwanza.
    """
    if crop or intent or location:
        return False
    return _has_stem(text, BROAD_STEMS)


def build_goal_question() -> str:
    return (
        "Karibu, nitafurahi kukusaidia. 🌿\n\n"
        "Ili nikupe ushauri sahihi, niambie unahitaji msaada gani:\n\n"
        "*1.* Tatizo shambani (ugonjwa, wadudu, dalili)\n"
        "*2.* Mbegu bora\n"
        "*3.* Wakati wa kupanda\n"
        "*4.* Mbolea\n"
        "*5.* Kuvuna na kuhifadhi\n"
        "*6.* Bei ya soko\n\n"
        "Jibu kwa namba, na ukiweza taja *zao* na *eneo* lako.\n"
        "_Mfano: 1, mahindi, Kondoa_"
    )


GOAL_ROUTES = {
    '1': 'diagnosis',
    '2': 'seed_selection',
    '3': 'planting_time',
    '4': 'fertilizer_planting',
    '5': 'harvest_time',
    '6': 'market_question',
}


def parse_goal_reply(text: str):
    """
    Rudisha 'diagnosis', jina la intent, au None.
    Inakubali namba ("1") au maneno ("tatizo", "mbegu").
    """
    t = (text or '').strip().lower()
    m = re.match(r'^\s*([1-6])\b', t)
    if m:
        return GOAL_ROUTES[m.group(1)]
    if _has_stem(t, PROBLEM_STEMS):
        return 'diagnosis'
    word_routes = (
        ('mbegu', 'seed_selection'), ('kupanda', 'planting_time'),
        ('panda', 'planting_time'), ('mbolea', 'fertilizer_planting'),
        ('vuna', 'harvest_time'), ('hifadhi', 'harvest_time'),
        ('bei', 'market_question'), ('soko', 'market_question'),
    )
    for word, route in word_routes:
        if word in t:
            return route
    return None


# ═══════════════════════════════════════════════════════
# OUTPUT VALIDATION
# ═══════════════════════════════════════════════════════

CHEMICAL_PATTERN = re.compile(
    r"(\d+[\.,]?\d*\s*(ml|mls|mililita|g|gm|gramu|kg|kilo|lita|l)\b"
    r"|kwa\s+lita|kwa\s+ekari|kwa\s+hekta|kwa\s+bomba"
    r"|mara\s+\w+\s+kwa\s+(wiki|siku|mwezi)|kila\s+siku\s+\d+"
    r"|nyunyizia|piga\s+dawa|kiuatilifu|viuatilifu|kiuakuvu"
    r"|pesticide|fungicide|insecticide|herbicide"
    r"|emamectin|lambda|cypermethrin|mancozeb|chlorpyrifos|imidacloprid"
    r"|dimethoate|profenofos|carbendazim|metalaxyl|abamectin|spinetoram"
    r"|chlorantraniliprole|deltamethrin|thiamethoxam|diazinon"
    r"|propiconazole|tebuconazole|azoxystrobin|spinosad|benzoate|bifenthrin"
    r"|malathion|carbofuran|glyphosate|atrazine|acetamiprid|flubendiamide"
    r"|\bdawa\b|\budhibiti\b)",
    re.IGNORECASE,
)

LABEL_CAUTION = (
    "⚠️ *Tahadhari:* Fuata maelekezo ya kwenye *kibandiko (label)* cha bidhaa na "
    "ushauri wa afisa ugani. Tumia vifaa vya kujikinga, na zingatia "
    "muda wa kusubiri kabla ya kuvuna."
)


def _sentences(text: str):
    # Gawanya kwa mistari na vituo, bila kupoteza muundo wa WhatsApp
    parts = []
    for line in text.split('\n'):
        chunks = re.split(r'(?<=[\.\!\?])\s+', line)
        parts.append(chunks)
    return parts


def validate_output(text: str, crop_name: str, allow_chemical: bool):
    """
    Kagua jibu kabla ya kutumwa. Inarudisha (jibu_safi, ripoti).

    1. Ondoa sentensi zinazotaja zao jingine (zao moja tu kwa jibu).
    2. Kama dawa haziruhusiwi, ondoa sentensi zenye dawa/viwango/mara.
    3. Kama jibu lina maudhui ya dawa, ongeza tahadhari ya label.
    """
    report = {'removed_other_crop': 0, 'removed_chemical': 0, 'added_caution': False}
    target = (crop_name or '').lower()
    own = {target, *CROP_ALIASES.get(target, ())}
    others = [c for c in KNOWN_CROPS if c not in own and c not in target]

    out_lines = []
    for chunks in _sentences(text or ''):
        kept = []
        for s in chunks:
            low = s.lower()
            if any(re.search(r'\b' + re.escape(c) + r'\b', low) for c in others):
                report['removed_other_crop'] += 1
                continue
            if not allow_chemical and CHEMICAL_PATTERN.search(s):
                report['removed_chemical'] += 1
                continue
            kept.append(s)
        out_lines.append(' '.join(kept).rstrip())

    cleaned = '\n'.join(out_lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

    if CHEMICAL_PATTERN.search(cleaned) and not re.search(r'label|kibandiko', cleaned.lower()):
        cleaned += '\n\n' + LABEL_CAUTION
        report['added_caution'] = True

    return cleaned, report
