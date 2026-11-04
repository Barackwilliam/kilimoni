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
from bot import diagnostic as dg
from diagnosis import engine as rx
from advisory import location as adv_location
from advisory import seed as adv_seed
from advisory import planting as adv_planting
from advisory import soil as adv_soil
from advisory import rotation as adv_rotation
from advisory import profile as adv_profile
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
            variation = (syn['variation'] or '').lower().strip()
            main_word = (syn['main_word'] or '').strip()
            if not variation or not main_word:
                continue
            pattern = r'\b' + re.escape(variation) + r'\b'
            # re.escape kwenye replacement pia — vinginevyo main_word yenye
            # '\' au '\1' ingevunja re.sub (bad escape / group reference)
            text = re.sub(pattern, main_word.replace('\\', r'\\'), text, flags=re.IGNORECASE)
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

    MUHIMU: tunatumia word-boundary (neno kamili), si substring.
    Bila hii, 'rice' (Mpunga) ingepatikana ndani ya 'price',
    na mkulima aliyeuliza kuhusu mahindi angepewa jibu la mpunga.
    """
    try:
        crops = Crop.objects.filter(active_status='active').order_by('priority_level')
        for crop in crops:
            names = [crop.crop_name_sw.lower(), crop.crop_name_en.lower()]
            for name in names:
                if name and _word_match(name, text):
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


GREETINGS = [
    'habari', 'hujambo', 'mambo', 'salamu', 'hello', 'hi',
    'salam', 'shikamoo', 'karibu', 'niaje', 'sasa', 'peace', 'hey',
]


def is_greeting(text: str) -> bool:
    """
    Angalia kama ujumbe ni salamu.

    MUHIMU: hatutumii substring ('hi' in text). Bila hii, mkulima
    aliyeandika 'Shinyanga' au 'Buhigwe' angehesabiwa kama anasalimia,
    kwa sababu 'hi' ipo ndani ya majina hayo.
    """
    t = (text or '').strip()
    if not t:
        return False
    return any(t == g or t.startswith(g + ' ') for g in GREETINGS)


def _word_match(name: str, text: str) -> bool:
    """Neno kamili tu (word boundary) — 'mara' isipatikane ndani ya 'mara nyingi' kwa bahati mbaya tu kama substring ya neno lingine."""
    if not name:
        return False
    return re.search(r'\b' + re.escape(name.lower()) + r'\b', text) is not None


# Maneno ambayo ni majina ya maeneo LAKINI pia ni maneno ya kawaida ya Kiswahili
# Haya yanatambuliwa TU yakiwa na muktadha wa eneo (mkoa wa X, niko X, n.k.)
AMBIGUOUS_LOCATIONS = {'mara', 'hai', 'pwani', 'tanga', 'sasa'}


def resolve_farm_location(text: str):
    """Eneo kutoka MHD-001 (kata/wilaya/mkoa + AEZ), au None."""
    try:
        return adv_location.resolve(text)
    except Exception as e:
        logger.error(f"MHD-001 location error: {e}")
        return None


def remember_farm_location(user, text: str):
    """
    Hifadhi eneo la shamba kwenye profile ya mkulima (kata, wilaya, mkoa, AEZ)
    ili ushauri unaotegemea kanda usimuulize eneo kila mara.
    """
    res = resolve_farm_location(text)
    if not res or res['level'] == 'ambiguous':
        return None
    fields = {'region': res['region'][:100]}
    if res['district']:
        fields['district'] = res['district'][:100]
    if res['level'] == 'ward':
        fields['ward'] = res['ward'][:100]
    elif res['district'] and res['district'] != user.district:
        fields['ward'] = ''
    if res.get('aez_id'):
        fields['aez_code'] = res['aez_id']
    elif res['level'] != 'ward':
        fields['aez_code'] = ''
    changed = [k for k, v in fields.items() if getattr(user, k) != v]
    if changed:
        for k in changed:
            setattr(user, k, fields[k])
        user.save(update_fields=changed)
    return res


def detect_location(text: str) -> str:
    """
    Tafuta eneo lililotajwa — mkoa, wilaya au kata.
    1. Muktadha wa wazi kwanza: "mkoa wa X", "wilaya ya X", "niko X"
    2. Database (word-boundary matching)
    3. Fallback lists (word-boundary matching)
    """
    # 0. Dataset ya maeneo ya mteja (MHD-001): kata → wilaya → mkoa
    adv = resolve_farm_location(text)
    if adv and adv['level'] != 'ambiguous':
        return adv_location.display_name(adv)

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

        # Kata kutoka MHD-001 ("Changaa, Kondoa") → AEZ yake au wilaya yake
        if ',' in location:
            zone = adv_location.zone_for(resolve_farm_location(location))
            if zone:
                return zone

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

    # Single keyword fallback — word boundary, si substring
    # ('bei' isipatikane ndani ya neno lingine, 'dap' ndani ya neno lingine n.k.)
    for keyword, intent_name in SINGLE_KEYWORD_INTENTS.items():
        if _word_match(keyword, text):
            try:
                intent = Intent.objects.get(intent_name=intent_name)
                # Upgrade if location present
                if intent_name == 'seed_selection' and location:
                    return Intent.objects.get(intent_name='variety_by_location')
                return intent
            except Intent.DoesNotExist:
                pass

    # Last resort: check 'mbegu' with location
    if _word_match('mbegu', text) and location:
        try:
            return Intent.objects.get(intent_name='variety_by_location')
        except Intent.DoesNotExist:
            pass
    elif _word_match('mbegu', text):
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

    # Baadhi ya intents zinamaanisha kitu kimoja kwenye maudhui.
    # Mfano: mkulima akiandika "mbegu" tunapata 'seed_selection',
    # lakini templates zote za mbegu zimehifadhiwa chini ya
    # 'variety_by_location'. Bila ramani hii, kila swali la mbegu
    # linaishia kwenye fallback licha ya jibu kuwepo.
    INTENT_ALIASES = {
        'seed_selection': ['variety_by_location'],
        'variety_by_location': ['seed_selection'],
        'symptom_analysis': ['disease_identification', 'pest_identification'],
        'fertilizer_amount': ['fertilizer_planting', 'fertilizer_top_dressing'],
    }

    intents_to_try = [intent] if intent else []
    if intent:
        for alias_name in INTENT_ALIASES.get(intent.intent_name, []):
            alt = Intent.objects.filter(intent_name=alias_name).first()
            if alt:
                intents_to_try.append(alt)

    # 0. Jaribu intent halisi, kisha zinazofanana nayo
    for candidate in intents_to_try:
        if crop and zone:
            answer = AnswerTemplate.objects.filter(
                crop=crop, intent=candidate, zone=zone, active_status='active'
            ).first()
        if not answer and crop:
            answer = AnswerTemplate.objects.filter(
                crop=crop, intent=candidate, active_status='active'
            ).first()
        if answer:
            break

    # 1. Most specific: crop + intent + zone
    if not answer and crop and intent and zone:
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


# ═══════════════════════════════════════════════════════
# MAZUNGUMZO — builders ziko bot/messages.py
# ═══════════════════════════════════════════════════════
from bot.messages import (            # noqa: E402
    build_greeting,
    build_crop_prompt,
    build_location_prompt,
    build_location_retry,
    build_symptom_followup,
    build_acknowledgement,
    build_fallback_message,
    build_technical_issue,
    build_help_message,
    format_response,
    topic_of,
    detect_offtopic_kind,
    build_identity_message,
    build_capability_message,
    build_offtopic_message,
)


# Maneno ya kukubali / kushukuru — hayahitaji jibu la kilimo
ACK_WORDS = {
    'sawa', 'asante', 'ahsante', 'nashukuru', 'poa', 'safi', 'nzuri',
    'ok', 'okay', 'haya', 'vizuri', 'shukrani', 'karibu', 'ndio',
    'ndiyo', 'naam', 'sawasawa', 'noted', 'thanks',
}


def is_acknowledgement(text: str) -> bool:
    """Angalia kama ujumbe ni kukubali tu, si swali jipya."""
    t = (text or '').strip().lower().rstrip('.!')
    if not t or len(t.split()) > 3:
        return False
    words = set(t.split())
    return bool(words) and words.issubset(ACK_WORDS)


# ═══════════════════════════════════════════════════════
# MAIN: process_message — Mtiririko Kamili
# ═══════════════════════════════════════════════════════
def process_message(phone_number: str, raw_message: str, whatsapp_type: str = 'text',
                    message_id: str = '') -> str:
    """
    Shughulikia ujumbe wote unaoingia kwa kufuata architecture kamili:
    Receive → Detect → Normalize → Synonyms → Crop → Location →
    Zone → Intent → Retrieve → Template → Follow-up → Format → Log

    message_id: ID ya ujumbe kutoka WhatsApp (kwa kuzuia majibu ya marudio).
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
        _log_all(user, raw_message, '', None, None, '', None, response, False, start_time,
                 message_id=message_id)
        return response

    # ── MODULE 3: Normalize text ─────────────────────
    normalized = normalize_text(raw_message)

    # ── Handle menu shortcuts ────────────────────────
    if normalized.strip() == '0':
        response = build_help_message()
        _log_all(user, raw_message, normalized, None, None, '', None, response, True, start_time,
                 message_id=message_id)
        return response

    # ── Handle greetings ─────────────────────────────
    if is_greeting(normalized) and len(normalized.split()) <= 4:
        # Mkulima anayerudi hapewi utangulizi mrefu tena —
        # tunamkumbuka na kuendelea pale tulipoishia.
        last_crop_name = ''
        if user.last_crop_id:
            _c = Crop.objects.filter(id=user.last_crop_id).first()
            last_crop_name = _c.crop_name_sw if _c else ''
        response = build_greeting(
            is_returning=user.message_count > 1,
            last_crop=last_crop_name,
        )
        _log_all(user, raw_message, normalized, None, None, '', None, response, True,
                 start_time, message_id=message_id)
        return response

    # ── MODULE 4: Apply synonyms ─────────────────────
    normalized = apply_synonyms(normalized)

    # ── Uchunguzi unaoendelea au swali la lengo ───────
    # Hushughulikiwa KWANZA, ili majibu ya mkulima (mfano "wiki 3",
    # "nusu ya shamba") yasichukuliwe kama maswali mapya.
    _sess = user.session_state or {}
    if _sess.get('goal_pending') or rx.get_state(_sess):
        handled = _handle_diagnostic_turn(user, raw_message, normalized,
                                          start_time, message_id)
        if handled is not None:
            return handled

    # ── Ushauri wa kanuni unaosubiri jibu (zao/eneo kwa ajili ya mbegu) ──
    if (user.session_state or {}).get('adv'):
        handled = _handle_advisory_pending(user, raw_message, normalized, start_time, message_id)
        if handled is not None:
            return handled

    # ── Kukubali / shukrani ("sawa", "asante") ───────
    # Bila hii, "sawa" hupelekwa kwenye injini ya maswali na
    # mkulima anapata fallback isiyo na maana.
    if is_acknowledgement(normalized) and not (user.session_state or {}).get('awaiting_location'):
        _c = Crop.objects.filter(id=user.last_crop_id).first() if user.last_crop_id else None
        response = build_acknowledgement(_c.crop_name_sw if _c else '')
        _log_all(user, raw_message, normalized, _c, None, '', None, response, True,
                 start_time, message_id=message_id)
        return response

    # ── Check session state — pending location reply ─
    session = user.session_state or {}
    if session.get('awaiting_location') and not is_greeting(normalized):
        # User is replying with their location
        location = detect_location(normalized)
        if location:
            remember_farm_location(user, normalized)
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

            # Ondoa hali ya kusubiri, LAKINI hifadhi eneo kwa mazungumzo yanayofuata
            user.session_state = {
                'last_location': location,
                'last_location_at': time.time(),
            }
            user.save(update_fields=['session_state'])

            # Now get answer with location
            answer_data = get_answer_from_db(crop, intent, zone)
            response = format_response(answer_data, crop, intent, location)
            found = bool(response)
            if not response:
                response, _ = _get_ai_or_fallback(raw_message, crop, intent, location, zone, user)
                _log_unresolved(user, raw_message, normalized, crop, intent, response)
            _log_all(user, raw_message, normalized, crop, intent, location, zone, response,
                     found, start_time, answer_data.get('answer_reference', ''),
                     message_id=message_id)
            return response

        # Hakuna eneo lililotambulika. Je, mkulima ameuliza swali JIPYA badala yake?
        # Bila ukaguzi huu, mtumiaji angeweza kunaswa kwenye "niambie eneo" milele.
        maybe_crop = detect_crop(normalized)
        maybe_intent = detect_intent(normalized, maybe_crop, '')
        attempts = int(session.get('location_attempts', 0)) + 1

        if maybe_crop or maybe_intent or attempts >= 2:
            # Achana na swali la eneo — shughulikia ujumbe huu kama swali jipya
            new_session = dict(session)
            new_session.pop('awaiting_location', None)
            new_session.pop('saved_intent', None)
            new_session.pop('location_attempts', None)
            user.session_state = new_session
            user.save(update_fields=['session_state'])
            session = new_session
            # (hakuna return — mtiririko unaendelea chini kama kawaida)
        else:
            new_session = dict(session)
            new_session['location_attempts'] = attempts
            user.session_state = new_session
            user.save(update_fields=['session_state'])
            response = build_location_retry()
            _log_all(user, raw_message, normalized, None, None, '', None, response, False,
                     start_time, message_id=message_id)
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
    if location:
        remember_farm_location(user, normalized)

    # Restore last location from session — TU ndani ya dakika 30
    # (mazungumzo yanayoendelea), isije ikagandamana milele
    if not location:
        saved_loc = session.get('last_location')
        saved_at = session.get('last_location_at', 0)
        if saved_loc and (time.time() - float(saved_at)) < 1800:
            location = saved_loc

    # ── MODULE 7: Zone Mapping ────────────────────────
    zone = map_location_to_zone(location)

    # ── Maswali yasiyo ya kilimo ──────────────────────
    # Tunaangalia HAPA (si mwanzo) ili majibu mafupi ya mkulima
    # kama "Singida" au "mahindi" yasihesabiwe kama yasiyo ya kilimo.
    _pending = (user.session_state or {})
    if not _pending.get('awaiting_location') and not _pending.get('awaiting_crop'):
        _kind = detect_offtopic_kind(normalized)
        # Tunatumia kilichotajwa KWENYE UJUMBE HUU, si kilichokumbukwa.
        # Vinginevyo mkulima aliyewahi kutaja Singida hataweza kamwe
        # kuuliza swali la nje ya kilimo.
        _fresh_crop = detect_crop(normalized)
        _fresh_loc = detect_location(normalized)
        if _kind and not _fresh_crop and not _fresh_loc and not adv_seed.wants_seed(normalized):
            if _kind == 'identity':
                response = build_identity_message()
            elif _kind == 'capability':
                response = build_capability_message()
            else:
                response = build_offtopic_message()
            _log_all(user, raw_message, normalized, None, None, '', None, response,
                     True, start_time, message_id=message_id)
            return response

    # ── MODULE 8: Intent Detection ────────────────────
    intent = detect_intent(normalized, crop, location)

    # Mkulima alichagua lengo kwa namba ("2" = mbegu, n.k.)
    _forced = (user.session_state or {}).get('forced_intent')
    if _forced:
        if not intent:
            intent = Intent.objects.filter(intent_name=_forced).first()
        _fs = dict(user.session_state or {})
        _fs.pop('forced_intent', None)
        user.session_state = _fs
        user.save(update_fields=['session_state'])

    # Mkulima alikuwa akiulizwa zao — sasa ametaja. Rudisha swali lake
    # la awali badala ya kumpeleka kwenye fallback.
    _sess = user.session_state or {}
    if crop and not intent and _sess.get('awaiting_crop'):
        saved_name = _sess.get('saved_intent', '')
        if saved_name:
            try:
                intent = Intent.objects.get(intent_name=saved_name)
            except Intent.DoesNotExist:
                intent = None
        _cleared = dict(_sess)
        _cleared.pop('awaiting_crop', None)
        _cleared.pop('saved_intent', None)
        user.session_state = _cleared
        user.save(update_fields=['session_state'])

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

    # ── Mzunguko wa mazao kwa kanuni (MHD-006 R4) ──
    if adv_rotation.wants_rotation(normalized):
        handled = _rotation_turn(user, raw_message, normalized, start_time, message_id)
        if handled is not None:
            return handled

    # ── Swali la udongo lililo wazi ("udongo wangu…") — kabla ya mbegu/kupanda,
    #    kwa sababu intent ya zamani inaweza kudhani ni swali la mbegu ──
    if 'udongo' in normalized.split() and not dg.is_problem_message(normalized, None):
        handled = _soil_turn(user, raw_message, normalized, detect_crop(normalized), start_time, message_id)
        if handled is not None:
            return handled

    # ── Mkulima ametaja eneo tu ("niko Changaa") → likumbuke na umkaribishe ──
    _only_loc = resolve_farm_location(normalized)
    if (_only_loc and _only_loc['level'] in ('ward', 'district') and len(normalized.split()) <= 4
            and not detect_crop(normalized) and not adv_seed.wants_seed(normalized)
            and not adv_planting.wants_planting(normalized) and not dg.is_problem_message(normalized, None)):
        response = _profile_ack(user, _only_loc)
        _log_all(user, raw_message, normalized, None, None, adv_location.display_name(_only_loc),
                 adv_location.zone_for(_only_loc), response, True, start_time, message_id=message_id,
                 trace={'mode': 'profile', 'decision': 'location_saved', 'aez': _only_loc.get('aez_id')})
        return response

    # ── Wakati wa kupanda kwa kanuni (MHD-006 + eneo + mbegu) ──
    if adv_planting.wants_planting(normalized, intent) and not adv_seed.mentioned_variety(normalized):
        handled = _planting_turn(user, raw_message, normalized, crop, start_time, message_id)
        if handled is not None:
            return handled

    # ── Ushauri wa mbegu kwa kanuni (MHD-003A + eneo la MHD-001) ──
    if adv_seed.wants_seed(normalized, intent):
        handled = _seed_turn(user, raw_message, normalized, crop, start_time, message_id)
        if handled is not None:
            return handled

    # ── Ushauri wa udongo kwa kanuni (MHD-004) ──
    if adv_soil.wants_soil(normalized) and not dg.is_problem_message(normalized, None):
        handled = _soil_turn(user, raw_message, normalized, detect_crop(normalized), start_time, message_id)
        if handled is not None:
            return handled

    # ── AI router: ujumbe bila neno la moduli → AI inachagua moduli (orodha funge) ──
    if intent is None and len(normalized.split()) >= 4 and not dg.is_problem_message(normalized, None):
        _rs = {}
        module = adv_profile.route(raw_message, _rs)
        handled = None
        if module == 'diagnosis':
            handled = _start_diagnostic(user, raw_message, normalized, detect_crop(normalized), start_time, message_id)
        elif module == 'seed':
            handled = _seed_turn(user, raw_message, normalized, crop, start_time, message_id, state=_rs)
        elif module == 'planting':
            handled = _planting_turn(user, raw_message, normalized, crop, start_time, message_id, state=_rs)
        elif module == 'soil':
            handled = _soil_turn(user, raw_message, normalized, detect_crop(normalized), start_time, message_id,
                                 state=_rs)
        elif module == 'rotation':
            handled = _rotation_turn(user, raw_message, normalized, start_time, message_id, state=_rs)
        if handled is not None:
            return handled

    # ── Ombi pana: uliza lengo kwanza, usitoe ushauri ──
    _fresh_c = detect_crop(normalized)
    _fresh_l = detect_location(normalized)
    if dg.is_broad_request(normalized, _fresh_c, intent, _fresh_l):
        _gs = dict(user.session_state or {})
        _gs['goal_pending'] = True
        user.session_state = _gs
        user.save(update_fields=['session_state'])
        response = dg.build_goal_question()
        _log_all(user, raw_message, normalized, None, None, '', None, response, True,
                 start_time, message_id=message_id,
                 trace={'mode': 'goal_question', 'reason': 'broad_request'})
        return response

    # ── Tatizo la zao: anza mtiririko wa uchunguzi ────
    # Hata kama template ipo, tatizo la mmea halijibiwi mara moja:
    # taarifa muhimu zikusanywe kwanza (kanuni ya usalama).
    if dg.is_problem_message(normalized, intent):
        return _start_diagnostic(user, raw_message, normalized, _fresh_c,
                                 start_time, message_id)

    # ── Prompt for crop if missing ────────────────────
    if needs_crop_prompt(crop, intent):
        # Hifadhi swali ili mkulima akitaja zao tuendelee palepale,
        # badala ya kuanza upya na kumuuliza tena.
        new_session = dict(user.session_state or {})
        new_session['awaiting_crop'] = True
        new_session['saved_intent'] = intent.intent_name if intent else ''
        user.session_state = new_session
        user.save(update_fields=['session_state'])
        response = build_crop_prompt(intent)
        _log_all(user, raw_message, normalized, None, intent, location, zone, response, False,
                 start_time, message_id=message_id)
        return response

    # ── Prompt for location if intent inahitaji eneo ──
    # Tunauliza KABLA ya kutafuta jibu — hivyo hatupotezi muda wa Groq
    # kwa jibu ambalo tungelitupa hata hivyo.
    if needs_location_prompt(intent, location):
        new_session = dict(user.session_state or {})
        new_session['awaiting_location'] = True
        new_session['saved_intent'] = intent.intent_name if intent else ''
        new_session['location_attempts'] = 0
        user.session_state = new_session
        user.save(update_fields=['session_state'])
        response = build_location_prompt(crop, intent)
        _log_all(user, raw_message, normalized, crop, intent, '', None, response, False,
                 start_time, message_id=message_id)
        return response

    # ── Special: symptom_analysis needs follow-up ────
    if intent and intent.intent_name == 'symptom_analysis' and crop:
        if not any(w in normalized for w in ['njano', 'kahawia', 'madoa', 'meupe', 'mashimo', 'kufa', 'kukauka']):
            response = build_symptom_followup(crop.crop_name_sw)
            _log_all(user, raw_message, normalized, crop, intent, location, zone, response, False,
                     start_time, message_id=message_id)
            return response

    # ── MODULE 9 & 10: Knowledge Retrieval ───────────
    answer_data = get_answer_from_db(crop, intent, zone)

    # ── MODULE 11: Answer Template Engine ────────────
    response = format_response(answer_data, crop, intent, location)

    # ── If no template found → Groq AI, kisha fallback ─
    from_template = bool(response)
    used_fallback = False
    if not response and not crop and not intent:
        # Hakuna zao wala lengo linalojulikana — AI ingebuni jibu la
        # jumla. Badala yake tunauliza mkulima anahitaji nini.
        _gs = dict(user.session_state or {})
        _gs['goal_pending'] = True
        user.session_state = _gs
        user.save(update_fields=['session_state'])
        response = dg.build_goal_question()
        from_template = True
    elif not response:
        response, used_fallback = _get_ai_or_fallback(
            raw_message, crop, intent, location, zone, user
        )
        if crop:
            response, _vr = dg.validate_output(response, crop.crop_name_sw, allow_chemical=False)

    # Bei za soko: onyo la lazima
    if intent and intent.intent_name == 'market_question' and 'thibitisha' not in response.lower():
        response += (
            "\n\n⚠️ _Bei hubadilika kila siku kulingana na msimu na soko. "
            "Taarifa hii si bei ya leo — thibitisha kwenye soko la karibu "
            "au kwa wafanyabiashara kabla ya kuuza au kununua._"
        )
    # success = tumeweza kumpa mkulima jibu la maana (template au AI),
    # SI tu kwamba tulirudisha maandishi fulani.
    success = from_template or not used_fallback

    # ── Log unresolved if needed ──────────────────────
    # Kila swali lisilopata jibu la template linarekodiwa ili msimamizi
    # aweze kuongeza template. Fallback kamili ni MUHIMU zaidi kurekodiwa.
    if not from_template:
        _log_unresolved(user, raw_message, normalized, crop, intent, response)

    # ── Log conversation + analytics ─────────────────
    _log_all(
        user, raw_message, normalized, crop, intent, location, zone,
        response, success, start_time,
        answer_data.get('answer_reference', '') if answer_data else '',
        message_id=message_id,
    )

    return response


def is_duplicate_message(message_id: str) -> bool:
    """
    Angalia kama ujumbe huu tumeushughulikia tayari.

    WhatsApp (Meta na GreenAPI) hurudia kutuma webhook ile ile kama
    haikupata 200 haraka. Bila ukaguzi huu, mkulima mmoja angepokea
    jibu lile lile mara 2-3.
    """
    if not message_id:
        return False
    try:
        return Conversation.objects.filter(
            whatsapp_message_id=message_id,
            message_direction='inbound',
        ).exists()
    except Exception as e:
        logger.error(f"Duplicate check error: {e}")
        return False


def _is_fallback_message(response: str) -> bool:
    """
    Ukaguzi wa dharura pale hatuna bendera ya moja kwa moja.
    Ujumbe wa fallback sasa hubadilika, kwa hiyo tunaangalia
    misemo yote inayowezekana badala ya mmoja.
    """
    if not response:
        return False
    head = response[:80]
    return any(m in head for m in (
        'Nimeelewa swali lako',
        'Asante kwa swali lako',
        'Nimekusikia',
    ))


def _log_unresolved(user, raw_message, normalized, crop, intent, response):
    """Rekodi swali lisilojibiwa ili msimamizi aliangalie kwenye dashboard."""
    try:
        if _is_fallback_message(response):
            reason = 'no_answer' if (crop or intent) else 'no_intent'
        else:
            # Groq AI ilijibu, lakini hakuna template — bado ni pengo la maudhui
            reason = 'no_answer'
        UnresolvedQuery.objects.create(
            user=user,
            raw_message=raw_message,
            normalized_text=normalized,
            detected_crop=crop,
            detected_intent=intent,
            reason=reason,
        )
    except Exception as e:
        logger.error(f"UnresolvedQuery error: {e}")


def _get_ai_or_fallback(raw_message, crop, intent, location, zone, user=None) -> str:
    """Tumia Groq AI (dataset + historia ya mazungumzo) kama template haipatikani."""
    try:
        from bot.groq_ai import get_groq_response
        ai_response = get_groq_response(
            user_message=raw_message,
            crop=crop,
            intent=intent,
            location=location or '',
            zone=zone,
            user=user,
        )
        if ai_response:
            return ai_response, False
    except Exception as e:
        logger.error(f"Groq AI fallback error: {e}")

    # Groq imeshindwa — hii ni fallback ya kweli.
    return build_fallback_message(crop, intent, location), True


def _log_all(user, raw_message, normalized, crop, intent, location, zone,
             response, success, start_time, answer_ref='', message_id='', trace=None):
    """Hifadhi mazungumzo, analytics — Module 13 & 15"""
    try:
        response_ms = int((time.time() - start_time) * 1000)

        Conversation.objects.create(
            user=user, message_direction='inbound',
            raw_message=raw_message, normalized_text=normalized,
            detected_crop=crop, detected_intent=intent,
            detected_location=location or '', detected_zone=zone,
            response_reference=answer_ref,
            whatsapp_message_id=message_id or '',
        )
        Conversation.objects.create(
            user=user, message_direction='outbound',
            raw_message=response, normalized_text='',
            detected_crop=crop, detected_intent=intent,
            detected_location=location or '', detected_zone=zone,
            response_reference=answer_ref,
            trace=trace or {},
        )
        AnalyticsLog.objects.create(
            user_id=user.id, phone_number=user.phone_number,
            crop=crop, intent=intent, zone=zone,
            success_flag=success, response_time_ms=response_ms,
        )
    except Exception as e:
        logger.error(f"Logging error: {e}")


# ═══════════════════════════════════════════════════════
# MTIRIRIKO WA UCHUNGUZI — helpers
# ═══════════════════════════════════════════════════════

def _save_rx(user, state):
    sess = dict(user.session_state or {})
    sess.pop('diag', None)          # hali ya mfumo wa zamani, kama ipo
    if state is None:
        sess.pop(rx.STATE_KEY, None)
    else:
        sess[rx.STATE_KEY] = state
    user.session_state = sess
    user.save(update_fields=['session_state'])


def _profile_ack(user, loc):
    place = adv_location.display_name(loc)
    zone = f" ({loc['aez_name']})" if loc.get('aez_name') else ''
    soil = adv_profile.profile_soil(user)
    lines = [f"📍 Nimekumbuka eneo la shamba lako: *{place}*{zone}."]
    if soil:
        lines.append(f"🟤 Udongo: {soil.name_sw}.")
    lines += ['', 'Sasa unaweza kuniuliza, kwa mfano:',
              '• _Mbegu gani ya mahindi nipande?_', '• _Nipande lini?_',
              '• _Udongo wangu unafaa mahindi?_', '• _Baada ya mahindi nipande nini?_',
              '• _Mahindi yangu yana mashimo kwenye majani_']
    return '\n'.join(lines)


def _farm_soil(user, normalized):
    """Udongo uliotajwa sasa (unakumbukwa) au wa profile ya mkulima."""
    named = adv_profile.soil_in_text(normalized)
    if named:
        adv_profile.remember_soil(user, named)
        return named
    return adv_profile.profile_soil(user)


def _set_adv(user, value):
    sess = dict(user.session_state or {})
    if value:
        sess['adv'] = value
    else:
        sess.pop('adv', None)
    user.session_state = sess
    user.save(update_fields=['session_state'])


def _place_without_data(user, normalized):
    """
    Eneo ambalo mkulima ametaja (au alitaja awali) na tunalitambua kwa jina,
    lakini halimo kwenye data ya maeneo (MHD-001) — hakuna AEZ.

    Bila hii, mkulima aliyesema "niko Kongwa" aliulizwa "taja wilaya yako"
    tena na tena: hakujua kwamba tatizo ni data, si jibu lake.
    """
    if resolve_farm_location(normalized):
        return ''
    try:
        named = detect_location(normalized)
    except Exception:
        named = ''
    sess = dict(user.session_state or {})
    if named:
        sess['place_no_data'] = named
        user.session_state = sess
        user.save(update_fields=['session_state'])
        return named
    return sess.get('place_no_data', '')


def _no_data_place_message(place, purpose):
    return (f"📍 Nimeona uko *{place}*, lakini bado sina taarifa za kanda ya kilimo (AEZ) ya eneo hilo "
            f"kwenye data yangu, kwa hiyo siwezi {purpose} kwa uhakika — na sitabuni.\n\n"
            "Kama shamba lako liko kwenye kata au wilaya nyingine jirani, nitajie. Vinginevyo, "
            "📞 afisa ugani wa eneo lako atakusaidia.")


def _seed_location(user, normalized):
    """Eneo la ujumbe huu (likihifadhiwa kwenye profile), au la profile ya mkulima."""
    loc = remember_farm_location(user, normalized)
    if loc and (user.session_state or {}).get('place_no_data'):
        sess = dict(user.session_state)
        sess.pop('place_no_data', None)           # sasa tunajua eneo lenye data
        user.session_state = sess
        user.save(update_fields=['session_state'])
    if loc and loc.get('aez_id'):
        return loc
    prof = adv_seed.location_from_user(user)
    if loc and loc['level'] == 'region' and prof and prof.get('region') != loc['region']:
        return loc                      # mkoa mpya wenye kanda nyingi → uliza wilaya/kata
    return prof or loc


def _seed_turn(user, raw_message, normalized, crop, start_time, message_id, text=None, attempts=0, state=None):
    """Ushauri wa mbegu. Inarudisha jibu, au None kama zao halina data ya mbegu."""
    if crop is None:
        named = adv_seed.mentioned_variety(normalized)
        crop = named.crop if named else None        # "SC 403" → mahindi
    if crop is None:
        _set_adv(user, {'module': 'seed', 'stage': 'crop', 'text': normalized, 'attempts': 0})
        response = ("Sawa, nitakusaidia kuchagua mbegu. 🌱\n\nNi mbegu ya *zao gani*?\n"
                    "_Mfano: mahindi_")
        _log_all(user, raw_message, normalized, None, None, '', None, response, True, start_time,
                 message_id=message_id, trace={'mode': 'seed_advisor', 'decision': 'need_crop'})
        return response
    if not adv_seed.has_data(crop):
        return None                     # mtiririko wa zamani (templates) unaendelea
    loc = _seed_location(user, normalized)
    state = state if state is not None else {}
    response, trace = adv_seed.advise(crop, loc, text or normalized, state, soil=_farm_soil(user, normalized))
    place = _place_without_data(user, normalized) if trace.get('decision') == 'need_location' and not loc else ''
    if place:
        response = _no_data_place_message(place, 'kukuchagulia mbegu')
        trace.update({'decision': 'location_not_in_data', 'place': place})
        # tunasubiri kata/wilaya jirani; ujumbe usio wa eneo unafuta hali hii (attempts=1)
        _set_adv(user, {'module': 'seed', 'stage': 'location', 'crop_id': crop.id,
                        'text': text or normalized, 'attempts': max(attempts, 1)})
    elif trace.get('decision') == 'need_location':
        _set_adv(user, {'module': 'seed', 'stage': 'location', 'crop_id': crop.id,
                        'text': text or normalized, 'attempts': attempts})
    else:
        _set_adv(user, None)
    zone = adv_location.zone_for(loc) if loc and loc.get('level') != 'ambiguous' else None
    _log_all(user, raw_message, normalized, crop, None, adv_location.display_name(loc) if loc else '',
             zone, response, trace.get('decision') not in ('need_location', 'no_suitable_variety', 'location_not_in_data'),
             start_time, answer_ref=','.join(r for r in trace.get('rules_used', []) if r),
             message_id=message_id, trace=trace)
    return response


def _planting_has_data(crop):
    from advisory.models import CropCalendar, SeasonProfile
    return SeasonProfile.objects.filter(is_active=True, aez__isnull=False).exists() or \
        CropCalendar.objects.filter(crop=crop, is_active=True).exists()


def _planting_turn(user, raw_message, normalized, crop, start_time, message_id, text=None, rain=None,
                   attempts=0, state=None):
    """Wakati wa kupanda. None = hakuna data ya MHD-006 (mtiririko wa zamani unaendelea)."""
    if not _planting_has_data(crop):
        return None
    loc = _seed_location(user, normalized)
    state = state if state is not None else {}
    response, trace = adv_planting.advise(crop, loc, text or normalized, state, rain=rain)
    dec = trace.get('decision')
    place = _place_without_data(user, normalized) if dec == 'need_location' and not loc else ''
    if place:
        response = _no_data_place_message(place, 'kukuambia wakati wa kupanda')
        trace.update({'decision': 'location_not_in_data', 'place': place})
        dec = 'location_not_in_data'
        _set_adv(user, {'module': 'planting', 'stage': 'location', 'crop_id': crop.id if crop else None,
                        'text': text or normalized, 'attempts': max(attempts, 1)})
    elif dec == 'need_location':
        _set_adv(user, {'module': 'planting', 'stage': 'location', 'crop_id': crop.id if crop else None,
                        'text': text or normalized, 'attempts': attempts})
    elif dec == 'need_crop':
        _set_adv(user, {'module': 'planting', 'stage': 'crop', 'text': text or normalized, 'attempts': 0})
    elif trace.get('ask_rain'):
        _set_adv(user, {'module': 'planting', 'stage': 'rain', 'crop_id': crop.id, 'text': text or normalized,
                        'attempts': 0})
    else:
        _set_adv(user, None)
    zone = adv_location.zone_for(loc) if loc and loc.get('level') != 'ambiguous' else None
    _log_all(user, raw_message, normalized, crop, None, adv_location.display_name(loc) if loc else '',
             zone, response, dec not in ('need_location', 'need_crop', 'INFO_ONLY', 'location_not_in_data'),
             start_time, answer_ref=','.join(r for r in trace.get('rules_used', []) if r),
             message_id=message_id, trace=trace)
    return response


def _handle_planting_pending(user, raw_message, normalized, start_time, message_id, pend):
    crop = Crop.objects.filter(id=pend.get('crop_id')).first() if pend.get('crop_id') else None
    if pend.get('stage') == 'crop':
        crop = detect_crop(normalized)
        if not crop:
            _set_adv(user, None)
            return None
        return _planting_turn(user, raw_message, normalized, crop, start_time, message_id,
                              text=pend.get('text', '') + ' ' + normalized)
    if pend.get('stage') == 'rain':
        rain = adv_planting.rain_status(normalized, {})
        if rain is None:
            _set_adv(user, None)
            return None                      # si jibu la swali la mvua — shughulikia kawaida
        return _planting_turn(user, raw_message, normalized, crop, start_time, message_id,
                              text=pend.get('text', ''), rain=rain)
    if pend.get('stage') == 'location':
        res = resolve_farm_location(normalized)
        if res and res['level'] != 'ambiguous':
            return _planting_turn(user, raw_message, normalized, crop, start_time, message_id,
                                  text=pend.get('text', ''), attempts=pend.get('attempts', 0) + 1)
        attempts = pend.get('attempts', 0) + 1
        if attempts >= 2 or detect_intent(normalized, detect_crop(normalized), '') or dg.is_problem_message(normalized, None):
            _set_adv(user, None)
            return None
        pend['attempts'] = attempts
        _set_adv(user, pend)
        response = ("Sijaweza kutambua eneo hilo. 🙏\n\nTafadhali taja *wilaya au kata* yako kwa jina, "
                    "_mfano: Kondoa, au kata ya Changaa_.")
        _log_all(user, raw_message, normalized, crop, None, '', None, response, False, start_time,
                 message_id=message_id, trace={'mode': 'planting_advisor', 'decision': 'location_not_found'})
        return response
    _set_adv(user, None)
    return None


def _rotation_turn(user, raw_message, normalized, start_time, message_id, text=None, state=None):
    """Mzunguko wa mazao. None = hakuna data ya MHD-006 R4."""
    from advisory.models import CropFamily, RotationCompatibility
    if not (CropFamily.objects.exists() or RotationCompatibility.objects.exists()):
        return None
    loc = _seed_location(user, normalized)
    state = state if state is not None else {}
    response, trace = adv_rotation.advise(text or normalized, loc, state, soil=_farm_soil(user, normalized))
    if trace.get('decision') == 'need_crop':
        _set_adv(user, {'module': 'rotation', 'stage': 'crop', 'text': text or normalized})
    else:
        _set_adv(user, None)
    _log_all(user, raw_message, normalized, None, None, adv_location.display_name(loc) if loc else '', None,
             response, trace.get('decision') not in ('need_crop', 'no_assessment'), start_time,
             answer_ref=','.join(trace.get('rules_used', [])), message_id=message_id, trace=trace)
    return response


def _soil_turn(user, raw_message, normalized, crop, start_time, message_id, text=None, state=None):
    """Ushauri wa udongo. None = hakuna data ya MHD-004."""
    from advisory.models import SoilType
    if not SoilType.objects.filter(is_active=True).exists():
        return None
    state = state if state is not None else {}
    named = adv_soil.identify(text or normalized, state)
    soil = named or adv_profile.profile_soil(user)
    if named:
        adv_profile.remember_soil(user, named)
    crop = crop or (Crop.objects.filter(id=user.last_crop_id).first() if soil and not named and user.last_crop_id else None)
    response, trace = adv_soil.advise(crop, text or normalized, state, soil=soil)
    if soil and not named:
        trace['soil_from_profile'] = True
        head, _, rest = response.partition('\n')
        response = (f"{head}\n_(Nimetumia udongo uliouniambia awali. Kama ni tofauti, niambie aina yake.)_"
                    f"\n{rest}")
    if trace.get('decision') == 'need_soil':
        _set_adv(user, {'module': 'soil', 'stage': 'soil', 'crop_id': crop.id if crop else None,
                        'text': text or normalized})
    else:
        _set_adv(user, None)
    _log_all(user, raw_message, normalized, crop, None, '', None, response, trace.get('decision') != 'need_soil',
             start_time, answer_ref=','.join(trace.get('rules_used', [])), message_id=message_id, trace=trace)
    return response


def _handle_advisory_pending(user, raw_message, normalized, start_time, message_id):
    """Jibu la mkulima kwa swali la zao/eneo la ushauri wa mbegu. None = shughulikia kawaida."""
    pend = dict((user.session_state or {}).get('adv') or {})
    if rx.is_cancel(normalized) or is_greeting(normalized):
        _set_adv(user, None)
        return None
    if pend.get('module') == 'planting':
        return _handle_planting_pending(user, raw_message, normalized, start_time, message_id, pend)
    if pend.get('module') == 'rotation':
        crops = adv_rotation.mentioned(normalized)
        if not crops:
            _set_adv(user, None)
            return None
        return _rotation_turn(user, raw_message, normalized, start_time, message_id,
                              text=f"nipande {crops[1] if len(crops) > 1 else 'nini'} baada ya {crops[0]}")
    if pend.get('module') == 'soil':
        crop = Crop.objects.filter(id=pend.get('crop_id')).first() if pend.get('crop_id') else detect_crop(normalized)
        if adv_soil.identify(normalized, {}) is None:
            _set_adv(user, None)
            return None
        return _soil_turn(user, raw_message, normalized, crop, start_time, message_id, text=normalized)
    if pend.get('stage') == 'crop':
        crop = detect_crop(normalized)
        if not crop:
            _set_adv(user, None)
            return None
        if not adv_seed.has_data(crop):
            _set_adv(user, None)
            response = (f"Samahani, kwa sasa sina taarifa za kutosha za mbegu za *{crop.crop_name_sw}* "
                        "kwenye mfumo, kwa hiyo sitabahatisha jina la mbegu. 🌱\n\n"
                        "📞 Afisa ugani wa kata yako atakusaidia kuchagua mbegu ya eneo lako.")
            _log_all(user, raw_message, normalized, crop, None, '', None, response, False, start_time,
                     message_id=message_id, trace={'mode': 'seed_advisor', 'decision': 'crop_without_seed_data'})
            return response
        return _seed_turn(user, raw_message, normalized, crop, start_time, message_id,
                          text=pend.get('text', '') + ' ' + normalized)
    if pend.get('stage') == 'location':
        crop = Crop.objects.filter(id=pend.get('crop_id')).first()
        res = resolve_farm_location(normalized)
        if crop and res and res['level'] != 'ambiguous':
            return _seed_turn(user, raw_message, normalized, crop, start_time, message_id,
                              text=pend.get('text', ''), attempts=pend.get('attempts', 0) + 1)
        attempts = pend.get('attempts', 0) + 1
        if attempts >= 2 or detect_intent(normalized, detect_crop(normalized), '') or dg.is_problem_message(normalized, None):
            _set_adv(user, None)
            return None
        pend['attempts'] = attempts
        _set_adv(user, pend)
        response = ("Sijaweza kutambua eneo hilo. 🙏\n\nTafadhali taja *wilaya au kata* yako kwa jina, "
                    "_mfano: Kondoa, au kata ya Changaa_.")
        _log_all(user, raw_message, normalized, crop, None, '', None, response, False, start_time,
                 message_id=message_id, trace={'mode': 'seed_advisor', 'decision': 'location_not_found'})
        return response
    _set_adv(user, None)
    return None


def _rx_reply(user, state, raw_message, normalized, response, trace, done,
              start_time, message_id):
    """Hifadhi hali ya uchunguzi, rekodi trace, rudisha jibu."""
    crop = Crop.objects.filter(id=state.get('crop_id')).first() if state.get('crop_id') else None
    _save_rx(user, None if done else state)
    if crop and user.last_crop_id != crop.id:
        user.last_crop_id = crop.id
        user.save(update_fields=['last_crop_id'])
    success = trace.get('decision') not in ('uncertain', 'no_rule_matched', 'no_crop')
    _log_all(user, raw_message, normalized, crop, None, '', None, response, success,
             start_time, answer_ref=','.join(trace.get('rules_used', [])),
             message_id=message_id, trace=trace)
    return response


def _rx_step(user, state, raw_message, normalized, start_time, message_id, fresh_crop=None):
    """Hatua moja ya rules engine (diagnosis/engine.py)."""
    if state['phase'] == 'crop':
        crop = fresh_crop or detect_crop(normalized)
        if not crop:
            words = set(re.findall(r"[a-z]+", normalized.lower()))
            unsupported = [c for c in dg.KNOWN_CROPS if c in words]
            if unsupported:
                # Zao halipo kwenye mfumo — sema ukweli, usizunguke
                names = ', '.join(rx.supported_crop_names()) or '—'
                response = (
                    f"Samahani, kwa sasa sina taarifa za *{unsupported[0].capitalize()}* "
                    "kwenye mfumo wangu, kwa hiyo siwezi kuchunguza tatizo lake kwa usahihi. 🌱\n\n"
                    f"Kwa sasa uchunguzi unapatikana kwa: *{names}*.\n\n" + rx.REFER_EXTENSION)
                return _rx_reply(user, state, raw_message, normalized, response,
                                 {'mode': 'rules_engine', 'decision': 'unsupported_crop',
                                  'crop_named': unsupported[0]}, True, start_time, message_id)
            if state.get('crop_asked'):
                state['crop_attempts'] = state.get('crop_attempts', 0) + 1
            if state.get('crop_attempts', 0) >= 2:
                response = ("Sawa. Bila kujua zao, siwezi kuchagua kanuni sahihi. 🌱\n\n"
                            + rx.REFER_EXTENSION)
                return _rx_reply(user, state, raw_message, normalized, response,
                                 {'mode': 'rules_engine', 'decision': 'no_crop'}, True,
                                 start_time, message_id)
            state['crop_asked'] = True
            return _rx_reply(user, state, raw_message, normalized, rx.ASK_CROP,
                             {'mode': 'rules_engine', 'asked': 'crop'}, False,
                             start_time, message_id)
        fresh_crop = crop
    response, trace, done = rx.step(state, normalized, fresh_crop)
    return _rx_reply(user, state, raw_message, normalized, response, trace, done,
                     start_time, message_id)


def _start_diagnostic(user, raw_message, normalized, fresh_crop, start_time, message_id):
    # Zao linachukuliwa tu kama limetajwa kwenye ujumbe huu —
    # si kutoka kumbukumbu ya zamani — ili tusichunguze zao lisilo sahihi.
    return _rx_step(user, rx.new_state(), raw_message, normalized, start_time,
                    message_id, fresh_crop=fresh_crop)


def _handle_diagnostic_turn(user, raw_message, normalized, start_time, message_id):
    """Inarudisha jibu, au None kama ujumbe ushughulikiwe na mtiririko wa kawaida."""
    sess = dict(user.session_state or {})

    # ── Jibu la swali la lengo ──
    if sess.get('goal_pending'):
        sess.pop('goal_pending', None)
        user.session_state = sess
        user.save(update_fields=['session_state'])
        route = dg.parse_goal_reply(normalized)
        if route == 'diagnosis':
            return _start_diagnostic(user, raw_message, normalized,
                                     detect_crop(normalized), start_time, message_id)
        if route:
            sess['forced_intent'] = route
            user.session_state = sess
            user.save(update_fields=['session_state'])
        return None

    # ── Uchunguzi unaoendelea ──
    state = rx.get_state(sess)
    if not state:
        return None

    if rx.is_cancel(normalized):
        _save_rx(user, None)
        response = "Sawa, nimesitisha uchunguzi. Uliza swali lingine lolote kuhusu kilimo. 🌿"
        _log_all(user, raw_message, normalized, None, None, '', None, response, True,
                 start_time, message_id=message_id,
                 trace={'mode': 'rules_engine', 'decision': 'cancelled'})
        return response

    return _rx_step(user, state, raw_message, normalized, start_time, message_id,
                    fresh_crop=detect_crop(normalized) if state['phase'] == 'crop' else None)
