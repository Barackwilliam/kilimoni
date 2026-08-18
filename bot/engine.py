"""
Kilimoni AI — Core Query Engine (Full Architecture v2)
Inafuata System Architecture document kamili:
WhatsApp → Receive → Detect Type → Normalize → Synonyms →
Crop Detection → Location Detection → Intent Detection →
Knowledge Retrieval → Answer Template → Follow-up Logic →
Response → Log → Analytics
"""
import re
import time
import logging
from django.utils import timezone
from crops.models import (
    Crop, Zone, LocationMapping, CropProfile,
    SeedVariety, Intent, FarmerQuestion, Synonym, AnswerTemplate
)
from bot.models import User, Conversation, UnresolvedQuery
from analytics.models import AnalyticsLog

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# MODULE 1: TEXT/VOICE DETECTION
# ═══════════════════════════════════════════════════════
def detect_message_type(raw_message: str, whatsapp_type: str = 'text') -> str:
    """
    Tambua aina ya ujumbe: text, voice, menu_selection
    Kwa MVP, text ndio kipaumbele. Voice = phase 2.
    """
    if whatsapp_type in ['audio', 'voice']:
        return 'voice'
    if whatsapp_type in ['interactive', 'button']:
        return 'menu_selection'
    return 'text'


# ═══════════════════════════════════════════════════════
# MODULE 2: SPEECH-TO-TEXT (Phase 2 placeholder)
# ═══════════════════════════════════════════════════════
def speech_to_text(audio_url: str) -> str:
    """
    Phase 2: Badilisha voice note kuwa maandishi.
    Kwa sasa, rudisha ujumbe wa kuomba maandishi.
    """
    return ''  # Phase 2


# ═══════════════════════════════════════════════════════
# MODULE 3: TEXT PROCESSING — Normalize
# ═══════════════════════════════════════════════════════
def normalize_text(text: str) -> str:
    """
    Safisha na andaa ujumbe:
    - lowercase
    - ondoa alama zisizo muhimu
    - ondoa nafasi za ziada
    """
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ═══════════════════════════════════════════════════════
# MODULE 4: SYNONYMS AND NORMALIZATION LAYER
# ═══════════════════════════════════════════════════════
def apply_synonyms(text: str) -> str:
    """
    Badilisha maneno ya kawaida/makosa na maneno rasmi.
    Mfano: mahind→mahindi, mbole→mbolea, pest→wadudu
    """
    try:
        synonyms = Synonym.objects.all().values('variation', 'main_word')
        for syn in synonyms:
            pattern = r'\b' + re.escape(syn['variation'].lower()) + r'\b'
            text = re.sub(pattern, syn['main_word'], text, flags=re.IGNORECASE)
    except Exception as e:
        logger.error(f"Synonym error: {e}")
    return text


# ═══════════════════════════════════════════════════════
# MODULE 5: CROP DETECTION
# ═══════════════════════════════════════════════════════
def detect_crop(text: str):
    """
    Tambua zao lililotajwa kwenye ujumbe.
    Angalia Kiswahili na English.
    """
    try:
        crops = Crop.objects.filter(active_status='active').order_by('priority_level')
        for crop in crops:
            names = [crop.crop_name_sw.lower(), crop.crop_name_en.lower()]
            for name in names:
                if name and name in text:
                    return crop
    except Exception as e:
        logger.error(f"Crop detection error: {e}")
    return None


# ═══════════════════════════════════════════════════════
# MODULE 6: LOCATION DETECTION
# ═══════════════════════════════════════════════════════
TANZANIA_REGIONS = [
    'dar es salaam', 'dodoma', 'arusha', 'mwanza', 'tanga', 'morogoro',
    'pwani', 'lindi', 'mara', 'mbeya', 'ruvuma', 'iringa', 'kagera',
    'kigoma', 'kilimanjaro', 'manyara', 'njombe', 'rukwa', 'shinyanga',
    'simiyu', 'singida', 'songwe', 'tabora', 'geita', 'katavi',
    'zanzibar', 'mtwara', 'pemba',
]

TANZANIA_DISTRICTS = [
    'kondoa', 'mpwapwa', 'kongwa', 'chamwino', 'bahi',
    'iramba', 'manyoni', 'ikungi', 'mkalama',
    'musoma', 'rorya', 'bunda', 'serengeti',
    'bukoba', 'muleba', 'biharamulo', 'karagwe', 'kyerwa',
    'chato', 'mbogwe', 'geita', 'nyang\'hwale',
    'njombe', 'ludewa', 'makambako', 'makete', 'wanging\'wa',
    'mbarali', 'mbeya', 'rungwe', 'kyela', 'busokelo',
    'iringa', 'kilolo', 'mufindi', 'mwanga',
    'moshi', 'hai', 'siha', 'rombo', 'same',
    'babati', 'hanang', 'kiteto', 'mbulu', 'simanjiro',
    'morogoro', 'kilosa', 'kilombero', 'ulanga', 'mvomero',
    'tabora', 'uyui', 'nzega', 'igunga', 'kaliua', 'sikonge',
    'kigoma', 'kasulu', 'kibondo', 'kakonko', 'buhigwe',
    'shinyanga', 'kahama', 'msalala', 'ushetu',
    'singida', 'mwanzi', 'itigi',
]


def _word_match(name: str, text: str) -> bool:
    """Neno kamili tu (word boundary) — 'mara' isipatikane ndani ya 'mara nyingi' kwa bahati mbaya tu kama substring ya neno lingine."""
    if not name:
        return False
    return re.search(r'\b' + re.escape(name.lower()) + r'\b', text) is not None


# Maneno ambayo ni majina ya maeneo LAKINI pia ni maneno ya kawaida ya Kiswahili
# Haya yanatambuliwa TU yakiwa na muktadha wa eneo (mkoa wa X, niko X, n.k.)
AMBIGUOUS_LOCATIONS = {'mara', 'hai', 'pwani', 'tanga', 'sasa'}


def detect_location(text: str) -> str:
    """
    Tafuta eneo lililotajwa — mkoa, wilaya au kata.
    1. Muktadha wa wazi kwanza: "mkoa wa X", "wilaya ya X", "niko X"
    2. Database (word-boundary matching)
    3. Fallback lists (word-boundary matching)
    """
    # 1. Muktadha wa wazi — hushinda vyote, na huruhusu hata maneno ambiguous
    ctx = re.search(
        r"(?:mkoa wa|wilaya ya|niko|nipo|natoka|kutoka)\s+([a-z\']+(?:\s+[a-z\']+)?)",
        text
    )
    if ctx:
        candidate = ctx.group(1).strip()
        for word_count in (2, 1):  # jaribu maneno 2 kwanza (dar es salaam n.k.)
            cand = ' '.join(candidate.split()[:word_count])
            if cand in TANZANIA_DISTRICTS or cand in TANZANIA_REGIONS:
                return cand.title()

    try:
        locations = LocationMapping.objects.all().values('region_name', 'district_name')
        # District first (more specific)
        for loc in locations:
            name = (loc['district_name'] or '').lower()
            if name and name not in AMBIGUOUS_LOCATIONS and _word_match(name, text):
                return loc['district_name'].title()
        # Then region
        for loc in locations:
            name = (loc['region_name'] or '').lower()
            if name and name not in AMBIGUOUS_LOCATIONS and _word_match(name, text):
                return loc['region_name'].title()
    except Exception as e:
        logger.error(f"Location DB error: {e}")

    # Fallback to hardcoded lists
    for district in TANZANIA_DISTRICTS:
        if district not in AMBIGUOUS_LOCATIONS and _word_match(district, text):
            return district.title()
    for region in TANZANIA_REGIONS:
        if region not in AMBIGUOUS_LOCATIONS and _word_match(region, text):
            return region.title()
    return ''


# ═══════════════════════════════════════════════════════
# MODULE 7: LOCATION → ZONE MAPPING
# ═══════════════════════════════════════════════════════
def map_location_to_zone(location: str):
    """
    Unganisha eneo na agro-ecological zone.
    Singida → Central Zone, Mbeya → Southern Highlands n.k.
    """
    if not location:
        return None
    try:
        mapping = LocationMapping.objects.filter(
            district_name__iexact=location
        ).select_related('zone').first()
        if mapping:
            return mapping.zone

        mapping = LocationMapping.objects.filter(
            region_name__iexact=location
        ).select_related('zone').first()
        if mapping:
            return mapping.zone
    except Exception as e:
        logger.error(f"Zone mapping error: {e}")
    return None


# ═══════════════════════════════════════════════════════
# MODULE 8: INTENT DETECTION ENGINE
# ═══════════════════════════════════════════════════════
INTENT_KEYWORD_MAP = {
    'variety_by_location': [
        ['mbegu', 'nipande'], ['mbegu', 'eneo'], ['mbegu', 'singida'],
        ['mbegu', 'dodoma'], ['mbegu', 'mbeya'], ['mbegu', 'arusha'],
        ['mbegu', 'mwanza'], ['mbegu', 'morogoro'], ['mbegu', 'tabora'],
        ['mbegu', 'zone'], ['variety', 'location'],
    ],
    'seed_selection': [
        ['mbegu', 'gani'], ['mbegu', 'bora'], ['aina', 'mbegu'],
        ['seed', 'selection'], ['variety', 'gani'],
    ],
    'planting_time': [
        ['lini', 'kupanda'], ['wakati', 'kupanda'], ['msimu', 'kupanda'],
        ['mwezi', 'kupanda'], ['ratiba', 'kupanda'], ['when', 'plant'],
        ['nipande', 'lini'], ['naweza', 'kupanda'],
    ],
    'spacing': [
        ['nafasi', 'kupanda'], ['umbali', 'kupanda'], ['spacing'],
        ['cm', 'safu'], ['mstari', 'umbali'], ['shimo', 'shimo'],
        ['nafasi', 'mstari'],
    ],
    'fertilizer_planting': [
        ['mbolea', 'kupandia'], ['mbolea', 'kupanda'], ['basal', 'fertilizer'],
        ['dap', 'kupanda'], ['can', 'kupanda'], ['mbolea', 'awali'],
        ['mbolea', 'shimo'],
    ],
    'fertilizer_top_dressing': [
        ['mbolea', 'juu'], ['top', 'dressing'], ['urea', 'lini'],
        ['can', 'juu'], ['mbolea', 'baada'], ['topdress'],
        ['mbolea', 'wiki'], ['urea', 'wakati'],
    ],
    'fertilizer_amount': [
        ['mbolea', 'ngapi'], ['kiasi', 'mbolea'], ['gramu', 'mbolea'],
        ['kilo', 'mbolea'], ['debe', 'mbolea'], ['mbolea', 'kiwango'],
    ],
    'pest_identification': [
        ['wadudu'], ['pest'], ['viwavi'], ['nondo'], ['inzi'],
        ['aphid'], ['chawa'], ['mdudu'], ['fall armyworm'],
        ['stalk borer'], ['thrips'],
    ],
    'disease_identification': [
        ['ugonjwa'], ['disease'], ['maradhi'], ['gray leaf'],
        ['leaf blight'], ['streak virus'], ['smut'], ['rust'],
        ['kuoza'], ['ukungu'],
    ],
    'symptom_analysis': [
        ['dalili'], ['majani', 'njano'], ['majani', 'kukauka'],
        ['majani', 'madoa'], ['mmea', 'kufa'], ['shina', 'mashimo'],
        ['rangi', 'majani'], ['majani', 'meupe'], ['majani', 'kahawia'],
        ['yellow', 'leaves'], ['brown', 'leaves'],
    ],
    'harvest_time': [
        ['lini', 'kuvuna'], ['wakati', 'kuvuna'], ['tayari', 'kuvuna'],
        ['kuvuna', 'lini'], ['harvest', 'time'], ['mavuno', 'lini'],
        ['ukomavu'], ['kukomaa'],
    ],
    'storage_advice': [
        ['kuhifadhi'], ['storage'], ['ghala'], ['panya'],
        ['unyevu', 'mahindi'], ['pics', 'gunia'], ['actellic'],
        ['hifadhi', 'mahindi'], ['baada', 'kuvuna'],
    ],
    'market_question': [
        ['bei'], ['soko'], ['market'], ['price'], ['kuuza'],
        ['faida'], ['nfra'], ['wanunuzi'], ['uza', 'wapi'],
    ],
    'weather_planting_decision': [
        ['mvua', 'lini'], ['hali', 'hewa'], ['weather'], ['ukame'],
        ['mvua', 'yataanza'], ['mvua', 'kupanda'], ['masika', 'lini'],
        ['vuli', 'lini'],
    ],
}

# Single keyword fallbacks (lower priority)
SINGLE_KEYWORD_INTENTS = {
    'wadudu': 'pest_identification', 'viwavi': 'pest_identification',
    'nondo': 'pest_identification', 'pest': 'pest_identification',
    'ugonjwa': 'disease_identification', 'disease': 'disease_identification',
    'maradhi': 'disease_identification',
    'dalili': 'symptom_analysis',
    'kuvuna': 'harvest_time', 'harvest': 'harvest_time',
    'kuhifadhi': 'storage_advice', 'ghala': 'storage_advice',
    'bei': 'market_question', 'soko': 'market_question',
    'nafasi': 'spacing', 'spacing': 'spacing',
    'urea': 'fertilizer_top_dressing',
    'dap': 'fertilizer_planting',
}


def detect_intent(text: str, crop=None, location: str = ''):
    """
    Tambua aina ya swali la mkulima kwa kutumia keyword matching.
    Multi-keyword patterns zinapewa kipaumbele juu ya single keywords.
    """
    # Try multi-keyword patterns first (highest accuracy)
    best_intent = None
    best_score = 0

    for intent_name, patterns in INTENT_KEYWORD_MAP.items():
        for pattern_keywords in patterns:
            if all(kw in text for kw in pattern_keywords):
                score = len(pattern_keywords)  # More keywords = higher confidence
                if score > best_score:
                    best_score = score
                    best_intent = intent_name

    # Upgrade seed_selection → variety_by_location if location present
    if best_intent == 'seed_selection' and location:
        best_intent = 'variety_by_location'

    if best_intent:
        try:
            return Intent.objects.get(intent_name=best_intent)
        except Intent.DoesNotExist:
            pass

    # Single keyword fallback
    for keyword, intent_name in SINGLE_KEYWORD_INTENTS.items():
        if keyword in text:
            try:
                intent = Intent.objects.get(intent_name=intent_name)
                # Upgrade if location present
                if intent_name == 'seed_selection' and location:
                    return Intent.objects.get(intent_name='variety_by_location')
                return intent
            except Intent.DoesNotExist:
                pass

    # Last resort: check 'mbegu' with location
    if 'mbegu' in text and location:
        try:
            return Intent.objects.get(intent_name='variety_by_location')
        except Intent.DoesNotExist:
            pass
    elif 'mbegu' in text:
        try:
            return Intent.objects.get(intent_name='seed_selection')
        except Intent.DoesNotExist:
            pass

    return None


# ═══════════════════════════════════════════════════════
# MODULE 9: KNOWLEDGE RETRIEVAL ENGINE
# ═══════════════════════════════════════════════════════
def get_answer_from_db(crop, intent, zone) -> dict:
    """
    Tafuta jibu sahihi kutoka database kwa utaratibu:
    1. crop + intent + zone (specific)
    2. crop + intent (general)
    3. intent only
    4. Crop profile fallback
    """
    answer = None

    # 1. Most specific: crop + intent + zone
    if crop and intent and zone:
        answer = AnswerTemplate.objects.filter(
            crop=crop, intent=intent, zone=zone, active_status='active'
        ).first()

    # 2. crop + intent (no zone)
    if not answer and crop and intent:
        answer = AnswerTemplate.objects.filter(
            crop=crop, intent=intent, active_status='active'
        ).first()

    # 3. intent only
    if not answer and intent:
        answer = AnswerTemplate.objects.filter(
            intent=intent, active_status='active'
        ).first()

    if answer:
        # Append seed varieties if relevant
        extra = ''
        if intent and intent.intent_name in ['seed_selection', 'variety_by_location'] and crop:
            varieties = SeedVariety.objects.filter(
                crop=crop, verification_status='verified'
            )
            if zone:
                zone_varieties = varieties.filter(recommended_zone=zone)
                if zone_varieties.exists():
                    varieties = zone_varieties
            if varieties.exists():
                names = ', '.join([v.variety_name for v in varieties[:5]])
                extra = f"\n\n🌱 *Mbegu zilizothibitishwa:*\n{names}"

        return {
            'found': True,
            'source': 'template',
            'answer_text': answer.answer_text_sw + extra,
            'follow_up': answer.follow_up_question,
            'caution': answer.caution_note,
            'answer_reference': answer.answer_reference,
        }

    # 4. Crop profile fallback
    if crop:
        profile = None
        if zone:
            profile = CropProfile.objects.filter(crop=crop, zone=zone).first()
        if not profile:
            profile = CropProfile.objects.filter(crop=crop).first()

        if profile and intent:
            field_map = {
                'planting_time': profile.planting_window_simple,
                'spacing': profile.spacing,
                'fertilizer_planting': profile.fertilizer_planting,
                'fertilizer_top_dressing': profile.fertilizer_top_dressing,
                'fertilizer_amount': profile.fertilizer_planting,
                'pest_identification': profile.common_pests,
                'disease_identification': profile.common_diseases,
                'symptom_analysis': profile.common_symptoms,
                'harvest_time': profile.harvest_window,
                'storage_advice': profile.storage_notes,
                'market_question': profile.market_notes,
            }
            field_value = field_map.get(intent.intent_name, '')
            if field_value:
                return {
                    'found': True,
                    'source': 'profile',
                    'answer_text': field_value,
                    'follow_up': '',
                    'caution': profile.caution_note or '',
                    'answer_reference': f'profile_{crop.id}_{intent.intent_name}',
                }

    return {'found': False, 'source': None}


# ═══════════════════════════════════════════════════════
# MODULE 10: FOLLOW-UP QUESTION LOGIC
# ═══════════════════════════════════════════════════════
def needs_location_prompt(intent, location: str) -> bool:
    """Angalia kama intent inahitaji eneo lakini haijatajwa"""
    location_required_intents = [
        'variety_by_location', 'planting_time', 'market_question',
        'weather_planting_decision', 'seed_selection',
    ]
    if not intent:
        return False
    return intent.intent_name in location_required_intents and not location


def needs_crop_prompt(crop, intent) -> bool:
    """Angalia kama intent inahitaji zao lakini haijatajwa"""
    if not intent:
        return False
    crop_required = [
        'seed_selection', 'variety_by_location', 'planting_time',
        'spacing', 'fertilizer_planting', 'fertilizer_top_dressing',
        'fertilizer_amount', 'pest_identification', 'disease_identification',
        'symptom_analysis', 'harvest_time', 'storage_advice',
    ]
    return intent.intent_name in crop_required and not crop


def build_location_prompt(crop, intent) -> str:
    """Jenga swali la kuomba eneo"""
    crop_name = crop.crop_name_sw if crop else 'zao lako'
    return (
        "📍 *Naomba eneo lako*\n\n"
        f"Ili nikupe ushauri sahihi wa *{crop_name}*, "
        "niambie uko mkoa au wilaya gani.\n\n"
        "_Mfano: Singida, Dodoma, Mbeya, Mwanza_"
    )


def build_crop_prompt() -> str:
    """Jenga swali la kuomba zao"""
    return (
        "🌱 *Naomba jina la zao*\n\n"
        "Tafadhali niambie ni zao gani unalouliza. Kwa sasa ninasaidia:\n\n"
        "•  *Mahindi* (Maize)\n"
        "•  *Maharage* (Beans)\n"
        "•  *Mpunga* (Rice)\n\n"
        "_Mfano: Mahindi yana wadudu, nifanye nini?_"
    )


def build_symptom_followup(crop_name: str) -> str:
    """Follow-up kwa symptom analysis — inahitaji taarifa zaidi"""
    return (
        f"🔍 *{crop_name.title()} — Uchunguzi wa Dalili*\n\n"
        "Ili nikupe utambuzi sahihi, nisaidie kwa taarifa hizi tatu:\n\n"
        "*1.* Sehemu iliyoathirika — majani, shina au tunda?\n"
        "*2.* Rangi au dalili — njano, kahawia, madoa?\n"
        "*3.* Umri wa mmea — wiki au miezi mingapi?\n\n"
        "_Mfano: Majani ya chini yana madoa ya kahawia, mmea una miezi 2_"
    )


# ═══════════════════════════════════════════════════════
# MODULE 11: ANSWER TEMPLATE ENGINE — Format Response
# ═══════════════════════════════════════════════════════
def format_response(answer_data: dict, crop, intent, location: str) -> str:
    """
    Panga jibu la mwisho kwa WhatsApp format.
    - Kiswahili rahisi
    - Fupi na la moja kwa moja
    - Follow-up question kama inahitajika
    - Footer ya Kilimoni AI
    """
    if not answer_data.get('found'):
        return None  # Tutumie Claude AI badala yake

    parts = []

    # Header ya kifahari — zao + eneo, na mstari mwembamba chini yake
    if crop and location:
        parts.append(f"🌾 *{crop.crop_name_sw.upper()}*  •  {location}")
        parts.append("━━━━━━━━━━━━━━━\n")
    elif crop:
        parts.append(f"🌾 *{crop.crop_name_sw.upper()}*")
        parts.append("━━━━━━━━━━━━━━━\n")

    # Main answer body
    parts.append(answer_data['answer_text'])

    # Caution note
    if answer_data.get('caution'):
        parts.append(f"\n⚠️ *Tahadhari:* {answer_data['caution']}")

    # Follow-up question
    if answer_data.get('follow_up'):
        parts.append(f"\n💬 _{answer_data['follow_up']}_")

    return '\n'.join(parts)


def build_fallback_message() -> str:
    """Fallback ya mwisho kabisa — inatumika tu kama AI nayo imeshindwa.
    Haionyeshi udhaifu wa mfumo — inaomba maelezo zaidi kwa staha."""
    return (
        "🌿 *Asante kwa swali lako!*\n\n"
        "Ili nikupe ushauri sahihi kabisa, naomba unieleze kidogo zaidi — "
        "hasa *zao* unalolima na *eneo* lako.\n\n"
        "_Mfano: Mahindi yangu yana majani ya njano, niko Singida_"
    )


def build_greeting() -> str:
    return (
        "🌿 *Karibu KILIMONI AI!*\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Mimi ni msaidizi wako wa kilimo, popote ulipo Tanzania.\n\n"
        "*Ninachoweza kukusaidia:*\n\n"
        "🌱  *Mbegu* — uchaguzi na aina bora\n"
        "📅  *Kupanda* — wakati na nafasi sahihi\n"
        "🧪  *Mbolea* — aina na vipimo\n"
        "🐛  *Wadudu & Magonjwa* — utambuzi na tiba\n"
        "🌾  *Kuvuna & Kuhifadhi* — njia bora\n"
        "💰  *Masoko* — bei na mwelekeo\n\n"
        "Uliza swali lako moja kwa moja 👇\n"
        "_Mfano: Ni mbegu gani ya mahindi nipande Singida?_\n\n"
        "Andika *0* kupata mwongozo wakati wowote."
    )


def build_help_message() -> str:
    return (
        "📋 *MWONGOZO WA KILIMONI AI*\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Uliza swali kwa lugha yako ya kawaida. Mifano:\n\n"
        "*1.* _Ni mbegu gani ya mahindi nipande Singida?_\n"
        "*2.* _Mahindi yapandwe lini Dodoma?_\n"
        "*3.* _Mbolea ya kupandia mahindi ni ipi?_\n"
        "*4.* _Mahindi yana viwavi, nifanye nini?_\n"
        "*5.* _Mahindi yana madoa, ni ugonjwa gani?_\n"
        "*6.* _Mahindi yanakuwa tayari kuvuna lini?_\n"
        "*7.* _Jinsi ya kuhifadhi mahindi baada ya kuvuna?_\n"
        "*8.* _Bei ya mahindi sokoni Mbeya ikoje?_\n\n"
        "💡 *Dokezo:* Taja *zao* na *eneo* lako kwenye swali ili upate ushauri sahihi zaidi."
    )


# ═══════════════════════════════════════════════════════
# MAIN: process_message — Mtiririko Kamili
# ═══════════════════════════════════════════════════════
def process_message(phone_number: str, raw_message: str, whatsapp_type: str = 'text') -> str:
    """
    Shughulikia ujumbe wote unaoingia kwa kufuata architecture kamili:
    Receive → Detect → Normalize → Synonyms → Crop → Location →
    Zone → Intent → Retrieve → Template → Follow-up → Format → Log
    """
    start_time = time.time()

    # ── Get or create user ──────────────────────────
    user, _ = User.objects.get_or_create(
        phone_number=phone_number,
        defaults={'active_status': 'active', 'session_state': {}}
    )
    user.message_count += 1
    user.save(update_fields=['message_count', 'last_seen_at'])

    if user.active_status == 'blocked':
        return "Samahani, nambari yako imezuiwa. Wasiliana na msimamizi."

    # ── MODULE 1: Detect message type ───────────────
    msg_type = detect_message_type(raw_message, whatsapp_type)

    # ── Voice handling (Phase 2 placeholder) ────────
    if msg_type == 'voice':
        response = (
            "Asante! Kwa sasa ninaweza kushughulikia *maandishi tu* 📝\n"
            "Tafadhali andika swali lako kwa maneno.\n\n"
            "Mfano: _Mahindi yana wadudu Singida, nifanye nini?_"
        )
        _log_all(user, raw_message, '', None, None, '', None, response, False, start_time)
        return response

    # ── MODULE 3: Normalize text ─────────────────────
    normalized = normalize_text(raw_message)

    # ── Handle menu shortcuts ────────────────────────
    if normalized.strip() == '0':
        response = build_help_message()
        _log_all(user, raw_message, normalized, None, None, '', None, response, True, start_time)
        return response

    # ── Handle greetings ─────────────────────────────
    GREETINGS = ['habari', 'hujambo', 'mambo', 'salamu', 'hello', 'hi',
                 'salam', 'shikamoo', 'karibu', 'niaje', 'sasa', 'peace', 'hey']
    if any(g == normalized.strip() or normalized.strip().startswith(g + ' ') for g in GREETINGS):
        if len(normalized.split()) <= 4:
            response = build_greeting()
            _log_all(user, raw_message, normalized, None, None, '', None, response, True, start_time)
            return response

    # ── MODULE 4: Apply synonyms ─────────────────────
    normalized = apply_synonyms(normalized)

    # ── Check session state — pending location reply ─
    session = user.session_state or {}
    if session.get('awaiting_location') and not any(g in normalized for g in GREETINGS):
        # User is replying with their location
        location = detect_location(normalized)
        if location:
            # Retrieve saved context and continue
            saved_intent_name = session.get('saved_intent', '')
            saved_crop_id = user.last_crop_id
            crop = None
            intent = None
            if saved_crop_id:
                try:
                    crop = Crop.objects.get(id=saved_crop_id)
                except Crop.DoesNotExist:
                    pass
            if saved_intent_name:
                try:
                    intent = Intent.objects.get(intent_name=saved_intent_name)
                except Intent.DoesNotExist:
                    pass
            zone = map_location_to_zone(location)

            # Clear session
            user.session_state = {}
            user.save(update_fields=['session_state'])

            # Now get answer with location
            answer_data = get_answer_from_db(crop, intent, zone)
            response = format_response(answer_data, crop, intent, location)
            if not response:
                response = _get_ai_or_fallback(raw_message, crop, intent, location, zone)
            _log_all(user, raw_message, normalized, crop, intent, location, zone, response, True, start_time, answer_data.get('answer_reference', ''))
            return response
        else:
            # Still no location recognized
            response = (
                "Sijatambua eneo ulilotaja. 📍\n"
                "Tafadhali andika jina la *mkoa au wilaya* yako.\n\n"
                "Mfano: _Singida_, _Dodoma_, _Mbeya_, _Mwanza_"
            )
            _log_all(user, raw_message, normalized, None, None, '', None, response, False, start_time)
            return response

    # ── MODULE 5: Crop Detection ──────────────────────
    crop = detect_crop(normalized)

    # Restore last crop from session if not detected
    if not crop and user.last_crop_id:
        try:
            crop = Crop.objects.get(id=user.last_crop_id)
        except Crop.DoesNotExist:
            pass

    # ── MODULE 6: Location Detection ─────────────────
    location = detect_location(normalized)

    # Restore last location from session — TU ndani ya dakika 30
    # (mazungumzo yanayoendelea), isije ikagandamana milele
    if not location:
        saved_loc = session.get('last_location')
        saved_at = session.get('last_location_at', 0)
        if saved_loc and (time.time() - float(saved_at)) < 1800:
            location = saved_loc

    # ── MODULE 7: Zone Mapping ────────────────────────
    zone = map_location_to_zone(location)

    # ── MODULE 8: Intent Detection ────────────────────
    intent = detect_intent(normalized, crop, location)

    # ── Update user session ───────────────────────────
    updates = {}
    if crop:
        user.last_crop_id = crop.id
        updates['last_crop_id'] = crop.id
    if intent:
        user.last_intent = intent.intent_name
        updates['last_intent'] = intent.intent_name
    if location:
        new_session = dict(session)
        new_session['last_location'] = location
        new_session['last_location_at'] = time.time()
        user.session_state = new_session
        updates['session_state'] = new_session
    if updates:
        user.save(update_fields=list(updates.keys()) + ['last_seen_at'])

    # ── Prompt for crop if missing ────────────────────
    if needs_crop_prompt(crop, intent):
        response = build_crop_prompt()
        _log_all(user, raw_message, normalized, None, intent, location, zone, response, False, start_time)
        return response

    # ── Special: symptom_analysis needs follow-up ────
    if intent and intent.intent_name == 'symptom_analysis' and crop:
        if not any(w in normalized for w in ['njano', 'kahawia', 'madoa', 'meupe', 'mashimo', 'kufa', 'kukauka']):
            response = build_symptom_followup(crop.crop_name_sw)
            _log_all(user, raw_message, normalized, crop, intent, location, zone, response, False, start_time)
            return response

    # ── MODULE 9 & 10: Knowledge Retrieval ───────────
    answer_data = get_answer_from_db(crop, intent, zone)

    # ── MODULE 11: Answer Template Engine ────────────
    response = format_response(answer_data, crop, intent, location)

    # ── If no template found → Claude AI ─────────────
    if not response:
        response = _get_ai_or_fallback(
            raw_message, crop, intent, location, zone
        )
        success = bool(response and 'Samahani' not in response[:20])
    else:
        success = True

    # ── Prompt for location if needed but not provided ─
    if success and intent and needs_location_prompt(intent, location) and not location:
        # Save state and ask for location
        new_session = dict(user.session_state or {})
        new_session['awaiting_location'] = True
        new_session['saved_intent'] = intent.intent_name if intent else ''
        user.session_state = new_session
        user.save(update_fields=['session_state'])
        response = build_location_prompt(crop, intent)
        _log_all(user, raw_message, normalized, crop, intent, '', None, response, False, start_time)
        return response

    # ── Log unresolved if needed ──────────────────────
    if not success or (not answer_data.get('found') and 'Asante kwa swali lako' not in response[:30]):
        try:
            UnresolvedQuery.objects.create(
                user=user,
                raw_message=raw_message,
                normalized_text=normalized,
                detected_crop=crop,
                detected_intent=intent,
                reason='no_answer' if (crop or intent) else 'no_intent',
            )
        except Exception as e:
            logger.error(f"UnresolvedQuery error: {e}")

    # ── Log conversation + analytics ─────────────────
    _log_all(
        user, raw_message, normalized, crop, intent, location, zone,
        response, success, start_time,
        answer_data.get('answer_reference', '') if answer_data else ''
    )

    return response


def _get_ai_or_fallback(raw_message, crop, intent, location, zone) -> str:
    """Tumia Groq AI (pamoja na muktadha wa dataset) kama template haipatikani."""
    try:
        from bot.groq_ai import get_groq_response
        ai_response = get_groq_response(
            user_message=raw_message,
            crop=crop,
            intent=intent,
            location=location or '',
            zone=zone,
        )
        if ai_response:
            return ai_response
    except Exception as e:
        logger.error(f"Groq AI fallback error: {e}")

    return build_fallback_message()


def _log_all(user, raw_message, normalized, crop, intent, location, zone,
             response, success, start_time, answer_ref=''):
    """Hifadhi mazungumzo, analytics — Module 13 & 15"""
    try:
        response_ms = int((time.time() - start_time) * 1000)

        Conversation.objects.create(
            user=user, message_direction='inbound',
            raw_message=raw_message, normalized_text=normalized,
            detected_crop=crop, detected_intent=intent,
            detected_location=location or '', detected_zone=zone,
            response_reference=answer_ref,
        )
        Conversation.objects.create(
            user=user, message_direction='outbound',
            raw_message=response, normalized_text='',
            detected_crop=crop, detected_intent=intent,
            detected_location=location or '', detected_zone=zone,
            response_reference=answer_ref,
        )
        AnalyticsLog.objects.create(
            user_id=user.id, phone_number=user.phone_number,
            crop=crop, intent=intent, zone=zone,
            success_flag=success, response_time_ms=response_ms,
        )
    except Exception as e:
        logger.error(f"Logging error: {e}")