"""
Mtiririko wa Uchunguzi (Diagnostic Conversation Flow)
======================================================

Inashughulikia matatizo ya mazao kwa mpangilio huu:

    tambua lengo -> kusanya taarifa -> chagua record ya dataset
    -> pima uhakika -> hatua salama za awali -> pendekezo mahsusi
    (pale tu inapowezekana)

KANUNI ZA USALAMA:
  - Hakuna utambuzi, dawa, kiwango (dosage) wala mara za matumizi
    (frequency) mpaka taarifa muhimu zote zikusanywe.
  - Majibu yanatoka kwenye records za zao MOJA pekee.
  - AI inaelewa lugha na kuandika jibu; haibuni maarifa. Inapewa
    records za dataset pekee, na jibu lake linakaguliwa kabla ya
    kutumwa (output validation).
"""
import re
import time
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

# Mpangilio wa taarifa za kukusanya
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

SLOT_ORDER = ('crop', 'symptoms', 'location', 'stage', 'onset', 'extent')

SLOT_QUESTIONS = {
    'crop': (
        "Pole kwa tatizo hilo. Nikusaidie kuchunguza hatua kwa hatua. 🔍\n\n"
        "Kwanza, ni *zao gani* lenye tatizo?\n"
        "_Mfano: mahindi, maharage, mpunga_"
    ),
    'symptoms': (
        "Sawa. Sasa nieleze *dalili unazoziona* kwenye {crop}.\n\n"
        "Sehemu gani imeathirika (majani, shina, mizizi, gunzi) na "
        "inaonekanaje (rangi, madoa, mashimo, kunyauka)?\n"
        "_Mfano: majani yana madoa ya kahawia na mashimo_"
    ),
    'location': (
        "Asante. Shamba lako liko *wapi*? 📍\n"
        "Taja mkoa, wilaya au kata.\n"
        "_Mfano: Kondoa, au niko Bereko_"
    ),
    'stage': (
        "{crop} yako iko katika *hatua gani ya ukuaji*? 🌱\n\n"
        "_Mfano: wiki 3 baada ya kuota, inatoa ndevu, au inakomaa_"
    ),
    'onset': (
        "Tatizo hili *lilianza lini*? ⏱️\n"
        "_Mfano: jana, wiki moja iliyopita, mwezi mmoja_"
    ),
    'extent': (
        "Swali la mwisho: ni *kiasi gani cha shamba* kimeathirika?\n"
        "_Mfano: mimea michache, nusu ya shamba, shamba lote_\n\n"
        "📷 Ukiweza, tuma pia picha ya mmea ulioathirika."
    ),
}

UNKNOWN_WORDS = ('sijui', 'sijajua', 'sina uhakika', 'sikumbuki', 'haijulikani')
CANCEL_WORDS = ('acha', 'ghairi', 'basi', 'sitaki', 'stop', 'swali jingine', 'swali lingine')

STAGE_KEYWORDS = (
    'kuota', 'kuchipua', 'chipukizi', 'miche', 'majani', 'kukua', 'ukuaji',
    'maua', 'ndevu', 'kubeba', 'gunzi', 'kujaza', 'punje', 'kukomaa',
    'komaa', 'kuvuna', 'wiki', 'siku', 'mwezi', 'miezi',
)
ONSET_KEYWORDS = ('jana', 'leo', 'juzi', 'siku', 'wiki', 'mwezi', 'miezi', 'karibuni', 'muda')
EXTENT_KEYWORDS = (
    'shamba', 'nusu', 'robo', 'sehemu', 'mimea', 'michache', 'mingi',
    'yote', 'kidogo', 'asilimia', '%', 'baadhi', 'eneo',
)

DIAG_TIMEOUT_SECONDS = 1800   # dakika 30 bila jibu -> uchunguzi unaisha

# Maneno ya kawaida yasiyobeba maana ya dalili (kwa kupima uhakika)
STOPWORDS = {
    'yangu', 'wangu', 'yako', 'yake', 'yana', 'ina', 'kwa', 'na', 'ya', 'wa',
    'la', 'za', 'kwenye', 'katika', 'sana', 'kidogo', 'hii', 'hiyo', 'huu',
    'mahindi', 'maharage', 'mpunga', 'zao', 'mazao', 'shamba', 'nifanye',
    'nini', 'naomba', 'msaada', 'tafadhali', 'pia', 'lakini', 'kama', 'ni',
    'yameanza', 'imeanza', 'sasa', 'tu', 'hapa', 'mimea', 'mmea',
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
# HALI YA UCHUNGUZI (session)
# ═══════════════════════════════════════════════════════

def get_diag(session: dict):
    diag = (session or {}).get('diag')
    if not diag or not diag.get('active'):
        return None
    if time.time() - float(diag.get('updated', 0)) > DIAG_TIMEOUT_SECONDS:
        return None
    return diag


def new_diag() -> dict:
    return {
        'active': True,
        'slots': {s: None for s in SLOT_ORDER},
        'asked': None,
        'unknown_count': 0,
        'started': time.time(),
        'updated': time.time(),
    }


def next_missing_slot(diag: dict):
    for slot in SLOT_ORDER:
        if diag['slots'].get(slot) is None:
            return slot
    return None


def _is_unknown(text: str) -> bool:
    t = (text or '').lower()
    return any(w in t for w in UNKNOWN_WORDS)


def is_cancel(text: str) -> bool:
    t = (text or '').strip().lower()
    return any(t == w or t.startswith(w + ' ') for w in CANCEL_WORDS)


def fill_slots(diag: dict, text: str, detect_crop, detect_location, fresh_crop=None):
    """
    Jaza taarifa zozote zilizopo kwenye ujumbe huu. Mkulima anaweza
    kutaja mambo kadhaa kwa pamoja: "mahindi yangu Bereko yana madoa
    ya njano wiki mbili sasa" — tunakusanya vyote mara moja badala
    ya kumuuliza tena kitu alichokisema.
    """
    slots = diag['slots']
    asked = diag.get('asked')
    t = (text or '').strip()
    low = t.lower()

    # Mkulima hajui jibu la swali tuliloliuliza
    if asked and _is_unknown(low):
        slots[asked] = 'haijulikani'
        diag['unknown_count'] = diag.get('unknown_count', 0) + 1
        return

    crop = fresh_crop or detect_crop(low)
    if crop and slots['crop'] is None:
        slots['crop'] = crop.id
    elif slots['crop'] is None and asked == 'crop':
        # Zao limetajwa lakini halipo kwenye database (mfano mtama).
        # Bila hii, bot ingeuliza "zao gani?" milele.
        words = set(re.findall(r"[a-z]+", low))
        unsupported = [c for c in KNOWN_CROPS if c in words]
        if unsupported:
            diag['unsupported_crop'] = unsupported[0]
        else:
            diag['crop_attempts'] = diag.get('crop_attempts', 0) + 1

    loc = detect_location(low)
    if loc and slots['location'] is None:
        slots['location'] = loc

    if slots['symptoms'] is None and _has_stem(low, PROBLEM_STEMS):
        # Ujumbe una maelezo ya dalili (si tu "mazao yanaumwa")
        meaningful = [w for w in re.findall(r"[a-z']+", low)
                      if len(w) >= 3 and w not in STOPWORDS]
        if asked == 'symptoms' or len(meaningful) >= 3:
            slots['symptoms'] = t

    if slots['stage'] is None and asked == 'stage':
        slots['stage'] = t
    elif slots['stage'] is None and _has_stem(low, ('ndevu', 'maua', 'gunzi', 'kukomaa', 'kuota')):
        slots['stage'] = t

    if slots['onset'] is None and asked == 'onset':
        slots['onset'] = t

    if slots['extent'] is None and asked == 'extent':
        slots['extent'] = t
    elif slots['extent'] is None and _has_stem(low, ('shamba lote', 'nusu', 'asilimia')):
        slots['extent'] = t

    # Jibu la swali tuliloliuliza (kwa slots za maandishi huru)
    if asked == 'symptoms' and slots['symptoms'] is None and len(t.split()) >= 2:
        slots['symptoms'] = t


def question_for(slot: str, crop_name: str = '') -> str:
    return SLOT_QUESTIONS[slot].format(crop=crop_name or 'zao lako')


# ═══════════════════════════════════════════════════════
# UCHAGUZI WA RECORDS NA KUPIMA UHAKIKA
# ═══════════════════════════════════════════════════════

def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z']+", (text or '').lower())
            if len(w) >= 4 and w not in STOPWORDS}


ITEM_HEADING = re.compile(r'^\s*\S{0,3}\s*\*\s*\d+\s*[\.\)]')


def split_items(text: str):
    """
    Gawanya template ya orodha kuwa vipengele. Mstari unaoanza na
    namba ("🐛 *1. Fall Armyworm*") unaanzisha kipengele kipya.
    Template isiyo orodha inarudishwa nzima.
    """
    lines = (text or '').split('\n')
    items, current = [], []
    for line in lines:
        if ITEM_HEADING.match(line):
            if current:
                items.append('\n'.join(current).strip())
            current = [line]
        elif current:
            current.append(line)
    if current:
        items.append('\n'.join(current).strip())
    return items or ([text.strip()] if text and text.strip() else [])


def select_records(crop, zone, symptoms: str):
    """
    Chagua records za dataset za ZAO HILI PEKEE, zinazohusu tatizo,
    na uzipange kwa jinsi zinavyolingana na dalili za mkulima.
    Hakuna record ya zao lingine inayoingia — hivyo jibu haliwezi
    kuchanganya mahindi na mtama au alizeti.
    """
    from crops.models import AnswerTemplate, CropProfile

    records = []

    templates = AnswerTemplate.objects.filter(
        crop=crop, active_status='active',
        intent__intent_name__in=PROBLEM_INTENTS,
    ).select_related('intent', 'zone')
    for tpl in templates:
        # Templates nyingi ni orodha ("1. Fall Armyworm ... 2. Stalk Borer ...").
        # Tunazigawa kwa vipengele ili kuchagua KIPENGELE kinacholingana
        # na dalili, badala ya kumpa mkulima orodha nzima.
        items = split_items(tpl.answer_text_sw or '')
        for n, item in enumerate(items, start=1):
            records.append({
                'kind': 'template_item',
                'ref': f"{tpl.answer_reference}#{n}",
                'zone': tpl.zone.zone_name if tpl.zone else '',
                'zone_match': bool(zone and tpl.zone_id == zone.id),
                'text': item,
            })

    profiles = CropProfile.objects.filter(crop=crop).select_related('zone')
    for p in profiles:
        text = ' '.join(filter(None, [
            getattr(p, 'common_symptoms', ''), getattr(p, 'common_pests', ''),
            getattr(p, 'common_diseases', ''), getattr(p, 'caution_note', ''),
        ]))
        if text.strip():
            records.append({
                'kind': 'crop_profile',
                'ref': f"CropProfile:{p.id}",
                'zone': p.zone.zone_name if p.zone else '',
                'zone_match': bool(zone and p.zone_id == zone.id),
                'text': text,
            })

    farmer = _tokens(symptoms)
    for r in records:
        overlap = farmer & _tokens(r['text'])
        r['match_terms'] = sorted(overlap)
        r['score'] = len(overlap) + (1 if r['zone_match'] else 0)

    records.sort(key=lambda r: r['score'], reverse=True)
    return records


def assess_confidence(records, slots) -> str:
    """
    Kiwango cha uhakika kinachotokana na kanuni zilizo wazi:
      high   — maneno 3+ ya dalili yanalingana na record
      medium — maneno 2 yanalingana
      low    — chini ya hapo (hakuna utambuzi unaotolewa)
    """
    if not records or not slots.get('symptoms') or slots['symptoms'] == 'haijulikani':
        return 'low'
    best = len(records[0].get('match_terms', []))
    if best >= 3:
        return 'high'
    if best >= 2:
        return 'medium'
    return 'low'


def chemical_allowed(slots, confidence: str) -> bool:
    """
    Dawa, viwango na mara za matumizi zinaruhusiwa TU pale:
    uhakika si mdogo NA taarifa zote muhimu zimejulikana.
    """
    if confidence not in ('high', 'medium'):
        return False
    return all(slots.get(s) not in (None, 'haijulikani') for s in SLOT_ORDER)


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
    "⚠️ *Tahadhari:* Fuata maelekezo ya kwenye *label* ya bidhaa na "
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

    if CHEMICAL_PATTERN.search(cleaned) and 'label' not in cleaned.lower():
        cleaned += '\n\n' + LABEL_CAUTION
        report['added_caution'] = True

    return cleaned, report


# ═══════════════════════════════════════════════════════
# KUUNDA JIBU LA MWISHO
# ═══════════════════════════════════════════════════════

SAFE_FIRST_STEPS = (
    "*Hatua salama za awali:*\n"
    "• Kagua mimea mingine uone kama dalili zinaenea\n"
    "• Ondoa mimea iliyoathirika sana, ichome au izike mbali na shamba\n"
    "• Weka shamba safi — palilia na ondoa mabaki ya mazao\n"
    "• *Usitumie kemikali yoyote* kabla tatizo halijathibitishwa"
)

REFER_EXTENSION = (
    "📞 Tafadhali wasiliana na *afisa ugani* wa kata yako. Ukiweza, "
    "mpelekee picha au sampuli ya mmea ulioathirika."
)


def _case_summary(slots, crop_name: str) -> str:
    rows = [
        ('Zao', crop_name),
        ('Dalili', slots.get('symptoms')),
        ('Eneo', slots.get('location')),
        ('Hatua ya ukuaji', slots.get('stage')),
        ('Lilianza', slots.get('onset')),
        ('Kiasi kilichoathirika', slots.get('extent')),
    ]
    return '\n'.join(f"- {k}: {v}" for k, v in rows if v)


def build_final_answer(slots, crop, zone, user=None):
    """
    Inarudisha (jibu, trace). trace inaeleza records zilizotumika,
    uhakika, na hatua za ukaguzi — kwa ajili ya ufuatiliaji.
    """
    crop_name = crop.crop_name_sw if crop else 'zao lako'
    records = select_records(crop, zone, slots.get('symptoms') or '')
    confidence = assess_confidence(records, slots)
    allow_chem = chemical_allowed(slots, confidence)
    best = records[0]['score'] if records else 0
    # Uwezekano 1-2 tu: kipengele kinachoongoza, na cha pili kama
    # kinakaribiana nacho. Hivyo jibu halimwagi orodha nzima.
    top = [r for r in records if r['score'] > 0 and r['score'] >= max(2, best - 1)][:2]

    trace = {
        'mode': 'diagnostic',
        'slots': slots,
        'confidence': confidence,
        'chemical_allowed': allow_chem,
        'records_used': [
            {'ref': r['ref'], 'kind': r['kind'], 'zone': r['zone'],
             'score': r['score'], 'match_terms': r['match_terms']}
            for r in top
        ],
        'source': None,
        'validation': None,
    }

    header = f"🌾 *{crop_name}*" + (f" — {slots['location']}" if slots.get('location') not in (None, 'haijulikani') else '')

    unknown = sum(1 for v in slots.values() if v == 'haijulikani')
    trace['unknown_slots'] = unknown

    # ── Taarifa hazitoshi au uhakika mdogo: hakuna utambuzi ──
    if unknown >= 2 or confidence == 'low' or not top:
        trace['source'] = 'safety_insufficient_info' if unknown >= 2 else 'safety_low_confidence'
        reason = ("Taarifa muhimu kadhaa hazijulikani bado" if unknown >= 2
                  else f"Dalili ulizotaja *hazilingani vya kutosha* na taarifa tulizonazo kuhusu {crop_name}")
        body = (
            f"{header}\n\n"
            f"Asante kwa maelezo yako. {reason}, kwa hiyo siwezi kukupa utambuzi "
            "wa uhakika. Sitakupa jina la ugonjwa wala tiba ya kemikali ili kuepuka "
            "ushauri usio sahihi.\n\n"
            f"{SAFE_FIRST_STEPS}\n\n{REFER_EXTENSION}"
        )
        return body, trace

    # ── Uhakika wa kutosha: AI inaandika kutoka records PEKEE ──
    ai_text = ''
    try:
        from bot.groq_ai import get_grounded_response
        ai_text = get_grounded_response(
            case_summary=_case_summary(slots, crop_name),
            crop_name=crop_name,
            records=top,
            confidence=confidence,
            allow_chemical=allow_chem,
        )
    except Exception as e:
        logger.error(f"Grounded response error: {e}")

    if ai_text:
        trace['source'] = 'ai_grounded'
        draft = ai_text
    else:
        # AI haipatikani — jibu linajengwa moja kwa moja kutoka dataset
        trace['source'] = 'dataset_direct'
        draft = (
            "*Tathmini:* Dalili ulizotaja zinalingana na taarifa zifuatazo "
            f"kwenye dataset ya {crop_name}:\n\n{top[0]['text']}"
        )

    draft, vreport = validate_output(draft, crop_name, allow_chem)
    trace['validation'] = vreport

    level = {'high': 'juu', 'medium': 'wastani'}.get(confidence, 'mdogo')
    parts = [header, '', draft, '', f"_Kiwango cha uhakika: {level}_"]

    if not allow_chem:
        parts += ['', SAFE_FIRST_STEPS,
                  '', "ℹ️ Mapendekezo ya tiba ya kemikali yatatolewa baada ya "
                      "taarifa zote muhimu kuthibitishwa, au na afisa ugani."]

    parts += ['', REFER_EXTENSION]
    refs = ', '.join(r['ref'] for r in top)
    parts += ['', f"📚 _Chanzo: dataset ya Kilimoni ({refs})_"]

    return '\n'.join(parts).strip(), trace
