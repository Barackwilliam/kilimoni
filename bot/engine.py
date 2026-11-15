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
from django.conf import settings
from crops.models import Crop, LocationMapping, Synonym
from bot.models import User, Conversation, UnresolvedQuery
from bot import diagnostic as dg
from bot import understand as understanding
from diagnosis import engine as rx
from advisory import coverage as adv_coverage
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


GREETING_TAILS = {'asubuhi', 'mchana', 'jioni', 'usiku', 'leo', 'kazi', 'nyumbani', 'siku', 'saa', 'shamba',
                  'wikendi', 'za', 'yako', 'zako', 'mzee', 'mkuu', 'familia', 'huko', 'kwenu'}


SASA_TAILS = {'vipi', 'mzee', 'mkuu', 'kaka', 'dada', 'bro', 'ndugu', 'habari', 'rafiki', 'boss', 'mambo'}


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
    # "habari za mpira jana" si salamu; "habari za asubuhi/shamba" ni salamu
    m = re.match(r'habari (?:za|ya) ([a-z]+)', t)
    if m and m.group(1) not in GREETING_TAILS:
        return False
    # "sasa" ni salamu peke yake ("sasa", "sasa vipi") — "sasa ni mpunga" si salamu
    words = t.split()
    if words[0] == 'sasa' and len(words) > 1 and words[1] not in SASA_TAILS:
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
        if adv['level'] == 'region':
            # "Kongwa, Dodoma": wilaya iliyotajwa (hata isiyo kwenye dataset) ni mahususi zaidi
            for district in TANZANIA_DISTRICTS:
                if district not in AMBIGUOUS_LOCATIONS and _word_match(district, text):
                    return district.title()
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
        locations = list(LocationMapping.objects.all().values('region_name', 'district_name'))
    except Exception as e:
        logger.error(f"Location DB error: {e}")
        locations = []
    # Wilaya kwanza (DB, kisha orodha), kisha mkoa — "Kongwa, Dodoma" ni Kongwa
    for loc in locations:
        name = (loc['district_name'] or '').lower()
        if name and name not in AMBIGUOUS_LOCATIONS and _word_match(name, text):
            return loc['district_name'].title()
    for district in TANZANIA_DISTRICTS:
        if district not in AMBIGUOUS_LOCATIONS and _word_match(district, text):
            return district.title()
    for loc in locations:
        name = (loc['region_name'] or '').lower()
        if name and name not in AMBIGUOUS_LOCATIONS and _word_match(name, text):
            return loc['region_name'].title()
    for region in TANZANIA_REGIONS:
        if region not in AMBIGUOUS_LOCATIONS and _word_match(region, text):
            return region.title()
    # Kosa moja la uchapaji ("Morogolo" → Morogoro), kwa majina ya herufi 7+ tu — majina mafupi
    # yanakaribiana na maneno ya kawaida ("mwanzo" ≈ Mwanza, "kusoma" ≈ Musoma, "kahawa" ≈ Kahama).
    from diagnosis.engine import _near
    for w in re.findall(r"[a-z']+", text.lower()):
        if len(w) >= 7:
            for name in TANZANIA_REGIONS + TANZANIA_DISTRICTS:
                if ' ' not in name and len(name) >= 7 and name not in AMBIGUOUS_LOCATIONS and _near(w, name):
                    return name.title()
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
def _strict():
    """Hali ya data pekee ni ya kudumu sasa (mfumo wa zamani umeondolewa)."""
    return True


# ═══════════════════════════════════════════════════════
# MAZUNGUMZO — builders ziko bot/messages.py
# ═══════════════════════════════════════════════════════
from bot.messages import (            # noqa: E402
    build_greeting,
    build_acknowledgement,
    build_help_message,
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
def _seed_example_text():
    from bot.messages import _seed_example
    return _seed_example()


def process_message(phone_number: str, raw_message: str, whatsapp_type: str = 'text',
                    message_id: str = '') -> str:
    """
    Kama _process_message; jibu la kwanza baada ya malalamiko ya mkulima
    ("nimeuliza hatua za kupanda…") linaanza kwa kuomba radhi.
    """
    user = User.objects.filter(phone_number=phone_number).first()
    previous = (Conversation.objects.filter(user=user, message_direction='outbound').order_by('-id')
                .values_list('raw_message', flat=True).first() if user else None)
    response = _process_message(phone_number, raw_message, whatsapp_type, message_id)
    user = User.objects.filter(phone_number=phone_number).first()          # session mpya baada ya jibu
    final = response
    # AI kama mwandishi: jibu la data → maelezo ya kawaida (ukweli wa rasimu tu; ukaguzi ukishindwa → rasimu)
    last = (Conversation.objects.filter(user=user, message_direction='outbound').order_by('-id').first()
            if user and response else None)
    if last is not None and last.raw_message == response:
        from bot import writer
        if writer.eligible(last.trace):
            final, info = writer.write(response, raw_message, last.trace)
            last.trace = {**(last.trace or {}), **info}
            last.save(update_fields=['trace'])
    prefix = _apology_prefix(user) if user and response else ''
    if prefix:
        final = prefix + final
    if previous and final == previous:
        final = _not_again(final)            # kigezo 1: mkulima asipate jibu lilelile mara mbili mfululizo
    if final != response and user:
        last = (Conversation.objects.filter(user=user, message_direction='outbound')
                .order_by('-id').first())
        if last:
            last.raw_message = final
            last.save(update_fields=['raw_message'])
    return final


def _not_again(text):
    """Jibu lilelile la pili mfululizo → toleo fupi linalokiri kwamba tumeshalisema."""
    first = (text or '').strip().split('\n\n')[0]
    first = re.sub(r'^[^\w*_]+', '', first)
    return ("Kama nilivyokueleza hapo juu 👆 — " + first[:1].lower() + first[1:] +
            "\n\nUkiwa na swali jingine, niulize tu. Au andika *0* kuona ninachoweza kukusaidia.")


def _process_message(phone_number: str, raw_message: str, whatsapp_type: str = 'text',
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
        if last_crop_name and user.message_count > 1:
            # Salamu imeuliza "tuendelee hapo, au una swali jipya?" — jibu lake lishughulikiwe;
            # maswali yaliyokuwa yakisubiriwa kabla ya salamu yanafutwa
            _clear_pending(user, keep_rx=True)
            _gs = dict(user.session_state or {})
            _gs['resume_offer'] = time.time()
            user.session_state = _gs
            user.save(update_fields=['session_state'])
        _log_all(user, raw_message, normalized, None, None, '', None, response, True,
                 start_time, message_id=message_id)
        return response

    # ── MODULE 4: Apply synonyms ─────────────────────
    normalized = apply_synonyms(normalized)

    # ── Jibu la salamu "tuendelee hapo, au una swali jipya?" / zao peke yake ──
    handled = _handle_resume_or_crop_only(user, raw_message, normalized, start_time, message_id)
    if handled is not None:
        return handled

    # ── WAKALA: AI inapokea na kuelewa, inachunguza dataset kwa zana, inajibu (bot/agent.py) ──
    handled = _agent_turn(user, raw_message, normalized, start_time, message_id)
    if handled is not None:
        return handled

    # ── AKIBA: fomu ya kuelewa (kanuni + AI) → kidhibiti kimoja kwa kila lengo ──
    frame = understanding.understand(raw_message, user, normalized=normalized,
                                     use_ai=understanding_enabled())
    # Malalamiko yenye swali jipya ("mbona hunijibu… nimeuliza bei") → jibu la swali lianze kwa radhi
    if _is_complaint(normalized) and frame['goal'] not in ('complaint', 'challenge'):
        _ap = dict(user.session_state or {})
        _ap['apologize'] = True
        user.session_state = _ap
        user.save(update_fields=['session_state'])
    return _dispatch(user, raw_message, normalized, frame, start_time, message_id)


# ═══════════════════════════════════════════════════════
# NJIA MOJA: fomu ya kuelewa → kidhibiti kimoja kwa kila lengo
# ═══════════════════════════════════════════════════════
# Mfumo wa zamani (majibu ya templates/demo, AI ya kutunga majibu, maswali ya "uko mkoa
# gani?" ya intent, "nahitaji kidogo zaidi") umeondolewa. Kila lengo lina kidhibiti kimoja
# kinachorudisha jibu la maana kila mara: kutoka kwenye data, au "sina data ya X" mahususi,
# au swali moja la kufafanua.

# Malengo ambayo ni majibu yanayowezekana kwa swali linalosubiriwa
ANSWERISH = {'answer', 'diagnosis', 'unclear', 'thanks', 'crop_only', 'location_only', 'greeting'}


def _agent_turn(user, raw_message, normalized, start_time, message_id):
    """
    Wakala wa AI unajibu ujumbe usio jibu la swali linalosubiriwa. None = AI haipo, imefika
    kikomo, au jibu lake halikupita ukaguzi → mfumo wa kanuni hapa chini unajibu.
    """
    from bot import agent
    sess = user.session_state or {}
    if rx.get_state(sess) or sess.get('goal_pending') or sess.get('adv') or not agent.enabled():
        return None                     # maswali ya uchunguzi/menyu yanajibiwa kwa kanuni
    if resolve_farm_location(normalized):
        remember_farm_location(user, normalized)
    out = agent.run(user, raw_message)
    if out is None:
        return None
    kind, payload, trace = out
    if kind == 'diagnosis':
        crop = payload or detect_crop(normalized)
        _clear_pending(user)
        return _start_diagnostic(user, raw_message, normalized, crop, start_time, message_id)
    crop = detect_crop(normalized)
    if crop and user.last_crop_id != crop.id:
        user.last_crop_id = crop.id
        user.save(update_fields=['last_crop_id'])
    _log_all(user, raw_message, normalized, crop, None, '', None, payload, True, start_time,
             message_id=message_id, trace=trace)
    return payload


def _dispatch(user, raw_message, normalized, frame, start_time, message_id):
    # Eneo lililotajwa kwenye ujumbe wowote (kata/wilaya ya MHD-001) linakumbukwa kwenye profile
    if resolve_farm_location(normalized):
        remember_farm_location(user, normalized)
    sess = user.session_state or {}
    goal = frame['goal']
    in_rx = bool(rx.get_state(sess))
    # 1. Bot inasubiri jibu (uchunguzi au menyu ya namba) na ujumbe ni jibu lake
    if (in_rx and goal in ANSWERISH | {'complaint'}) or (sess.get('goal_pending') and goal in ANSWERISH):
        handled = _handle_diagnostic_turn(user, raw_message, normalized, start_time, message_id)
        if handled is not None:
            return handled
    # 2. Moduli ya ushauri inasubiri zao/eneo/mvua/udongo
    if (user.session_state or {}).get('adv') and goal in ANSWERISH:
        handled = _handle_advisory_pending(user, raw_message, normalized, start_time, message_id)
        if handled is not None:
            return handled
    # 3. Kidhibiti cha lengo — hakirudishi None
    return _route_goal(user, raw_message, normalized, frame, start_time, message_id)


MODULE_NAMES = {'seed': 'mbegu', 'planting': 'wakati wa kupanda', 'soil': 'udongo', 'rotation': 'mzunguko wa mazao'}


def _module_no_data(user, raw_message, normalized, module, crop, start_time, message_id):
    """Moduli haina data ya ombi hili → sema ukweli mahususi (si 'nahitaji kidogo zaidi')."""
    what = MODULE_NAMES.get(module, module)
    subject = f"*{what}*" + (f" ya *{crop.crop_name_sw}*" if crop else '')
    response = (f"🌱 Samahani, bado sina taarifa zilizothibitishwa za {subject} kwenye data yangu — "
                "kwa hiyo sitabuni.\n\n📞 Afisa ugani wa eneo lako atakusaidia kwa hili.\n\n"
                "Kwa sasa naweza kukusaidia kuhusu: *matatizo ya mazao* (wadudu, magonjwa, dalili), "
                "*mbegu bora*, *wakati wa kupanda*, *udongo* na *mzunguko wa mazao*.")
    _log_all(user, raw_message, normalized, crop, None, '', None, response, False, start_time,
             message_id=message_id, trace={'mode': 'understand', 'decision': 'module_without_data',
                                           'module': module})
    _log_unresolved(user, raw_message, normalized, crop, None, response)
    return response


def _location_only(user, raw_message, normalized, crop, start_time, message_id):
    loc = resolve_farm_location(normalized)
    if loc and loc['level'] in ('ward', 'district'):
        response = _profile_ack(user, loc)
        _log_all(user, raw_message, normalized, None, None, adv_location.display_name(loc),
                 adv_location.zone_for(loc), response, True, start_time, message_id=message_id,
                 trace={'mode': 'profile', 'decision': 'location_saved', 'aez': loc.get('aez_id')})
        return response
    place = _place_without_data(user, normalized)
    if not place:
        return None
    known = adv_coverage.places_line(limit=6)
    response = (f"📍 Sawa, nimeona uko *{place}*. Bado sina taarifa za kanda ya kilimo ya eneo hilo "
                "kwenye data yangu, kwa hiyo ushauri unaotegemea eneo (mbegu, wakati wa kupanda) "
                "utakuwa wa jumla tu — sitabuni."
                + (f"\n\n📍 Maeneo niliyo na taarifa kamili: {known}." if known else '')
                + "\n\nNiulize swali lako, mf. _nipande lini?_ au _mahindi yana mashimo, nifanye nini?_")
    _log_all(user, raw_message, normalized, crop, None, place, None, response, False, start_time,
             message_id=message_id, trace={'mode': 'profile', 'decision': 'location_not_in_data', 'place': place})
    return response


def _unclear(user, raw_message, normalized, frame, start_time, message_id):
    """Hatukuelewa: swali MOJA la kufafanua — tofauti likijirudia (kigezo 1)."""
    sess = dict(user.session_state or {})
    repeat = time.time() - float(sess.get('unclear_at', 0)) < 600
    sess['unclear_at'] = time.time()
    crop = frame.get('crop')
    words = normalized.split()
    if len(words) == 1 and not crop:
        response = (f"Samahani, sijaelewa \"*{raw_message.strip()[:40]}*\" peke yake. 🙏 Kama ni jina la eneo "
                    "lako, bado halimo kwenye data yangu ya maeneo.\n\nNiandikie swali lako kamili, mf. "
                    "_nipande lini mahindi?_ au _mbegu gani inafaa eneo langu?_")
        decision = 'single_unknown_word'
    elif crop:
        sess['goal_pending'] = True
        response = ("Samahani, sijaelewa vizuri swali lako. 🙏\n\n" if repeat else '') + \
            dg.build_crop_menu(crop.crop_name_sw)
        decision = 'crop_menu'
    else:
        sess['goal_pending'] = True
        response = (dg.build_goal_question(opener="Bado sijaelewa unachohitaji. 🙏 Tafadhali chagua:")
                    if repeat else
                    dg.build_goal_question(opener="Samahani, sijaelewa vizuri unachohitaji. 🙏"))
        decision = 'goal_menu'
    user.session_state = sess
    user.save(update_fields=['session_state'])
    _log_all(user, raw_message, normalized, crop, None, '', None, response, False, start_time,
             message_id=message_id, trace={'mode': 'understand', 'decision': decision,
                                           'frame': understanding.as_trace(frame)})
    _log_unresolved(user, raw_message, normalized, crop, None, response)
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
    known = adv_coverage.places_line(limit=6)
    have = f"\n\n📍 Kwa sasa nina taarifa za maeneo haya: {known}." if known else ''
    return (f"📍 Nimeona uko *{place}*, lakini bado sina taarifa za kanda ya kilimo (AEZ) ya eneo hilo "
            f"kwenye data yangu, kwa hiyo siwezi {purpose} kwa uhakika — na sitabuni.{have}\n\n"
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
    if not loc and (user.session_state or {}).get('place_no_data'):
        # Mkulima amesema yuko eneo lisilo kwenye data (mf. Ruvuma) baada ya eneo la profile —
        # tusimpe ushauri wa eneo la zamani (Kondoa) kana kwamba ndilo lake
        return None
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
        if not _strict():
            return None                 # mtiririko wa zamani (templates) unaendelea
        # Live 15 Nov: "2" (mbegu) kwa Mpunga → "Uko mkoa gani?" ya mtiririko wa zamani, kisha
        # "nahitaji kidogo zaidi". Sasa: ukweli kwamba data ya mbegu ya zao hili haipo bado.
        from advisory.models import VarietyAgronomy
        have = sorted(set(VarietyAgronomy.objects.filter(is_active=True).exclude(crop=None)
                          .values_list('crop__crop_name_sw', flat=True)))
        _set_adv(user, None)
        response = (f"🌱 Samahani, bado sina taarifa zilizothibitishwa za *mbegu za {crop.crop_name_sw}* "
                    "kwenye data yangu — kwa hiyo sitabuni.\n\n"
                    + (f"Kwa sasa ushauri wa mbegu unapatikana kwa: *{', '.join(have)}*.\n\n" if have else '')
                    + "📞 Afisa ugani wa eneo lako atakusaidia kuchagua mbegu ya "
                    + f"{crop.crop_name_sw}.")
        _log_all(user, raw_message, normalized, crop, None, '', None, response, False, start_time,
                 message_id=message_id, trace={'mode': 'seed_advisor', 'decision': 'crop_without_seed_data'})
        _log_unresolved(user, raw_message, normalized, crop, None, response)
        return response
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
        _ov = adv_planting.zone_overview(crop)
        if _ov:
            response += '\n\n' + _ov
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
        if attempts >= 2 or dg.is_problem_message(normalized, None):
            _set_adv(user, None)
            return None
        place = _place_without_data(user, normalized)
        if place:
            _set_adv(user, None)
            response = _no_data_place_message(place, 'kukuambia tarehe sahihi za kupanda')
            overview = adv_planting.zone_overview(crop)
            if overview:
                response += '\n\n' + overview
            _log_all(user, raw_message, normalized, crop, None, place, None, response, False, start_time,
                     message_id=message_id, trace={'mode': 'planting_advisor', 'decision': 'location_not_in_data',
                                                   'place': place})
            return response
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
        if attempts >= 2 or dg.is_problem_message(normalized, None):
            _set_adv(user, None)
            return None
        place = _place_without_data(user, normalized)
        if place:
            _set_adv(user, None)
            response = _no_data_place_message(place, 'kukuambia tarehe sahihi za kupanda')
            overview = adv_planting.zone_overview(crop)
            if overview:
                response += '\n\n' + overview
            _log_all(user, raw_message, normalized, crop, None, place, None, response, False, start_time,
                     message_id=message_id, trace={'mode': 'planting_advisor', 'decision': 'location_not_in_data',
                                                   'place': place})
            return response
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
    if done and trace.get('decision') == 'diagnosed':
        _remember_diagnosis(user, state, trace, response)
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
    state = rx.new_state()
    if not fresh_crop:
        # Muktadha: zao lililotajwa kwenye ujumbe uliotangulia (ndani ya dakika 30)
        # — "mahindi yangu hayako sawa" → "majani yana mistari ya njano" isiulize "zao gani?".
        fresh_crop = _recent_crop(user)
    if not fresh_crop and len(normalized.split()) >= 3:
        # "majani yamekuwa ya kahawia" bila zao: tunauliza zao, lakini maelezo haya
        # yanatumika baadaye — mkulima asiulizwe dalili mara ya pili.
        state['early_symptoms'] = normalized
    return _rx_step(user, state, raw_message, normalized, start_time,
                    message_id, fresh_crop=fresh_crop)


# Mada za kilimo ambazo bado hazina dataset iliyothibitishwa (MHD) wala wasifu wa zao.
KNOWLEDGE_GAPS = [
    (re.compile(r'\b(ku)?palili\w*|\bmagugu\b|\bpalizi\b'), 'kupalilia na kudhibiti magugu'),
    (re.compile(r'\b(samadi|mbolea)\b'), '__mbolea__'),          # "samadi ya kuku" ni mbolea, si mifugo
    (re.compile(r'\b(mifugo|ufugaji|kufuga|ng\'?ombe|ng ombe|mbuzi|kondoo|kuku|nguruwe)\b'), 'mifugo'),
    (re.compile(r'\b(ku)?pogoa\b|\bkupunguza matawi\b'), 'kupogoa'),
]


# Hali ya data pekee: mada ambazo dataset za MHD hazina bado. Zamani zilijibiwa na majibu ya demo
# au AI ya bure (live: "bei za takriban 2024", "Actellic Super", "maji ya baridi 15-20 °C kupalilia").
STRICT_GAPS = [
    (re.compile(r'\b(kuvuna|mavuno|kuvunwa|nivune|tuvune|ukomavu|yamekomaa|imekomaa|yamekomaa)\b'),
     'kuvuna'),
    (re.compile(r'\b(kuhifadhi|uhifadhi|kuhifadhiwa|ghala|nihifadhi)\b'), 'kuhifadhi mazao'),
    (re.compile(r'\b(bei|soko|masoko|sokoni|kuuza|nauza|niuze|yanauzwa|inauzwa|kuuzwa|shilingi ngapi)\b'),
     'bei na masoko'),
    (re.compile(r'\b(hali ya hewa|utabiri|hewa ikoje)\b'), 'hali ya hewa'),
    (re.compile(r'\b(mbolea|dap|urea|can|npk|samadi)\b'), 'mbolea'),
    (re.compile(r'\b(vifaa|zana|jembe|trekta|kuandaa shamba|maandalizi ya shamba|kulima shamba)\b'),
     'maandalizi ya shamba na zana'),
    (re.compile(r'\b(umwagiliaji|kumwagilia|nimwagilie)\b'), 'umwagiliaji'),
    (re.compile(r'\b(nafasi ya kupanda|nafasi za kupanda|umbali wa kupanda|spacing|hatua za kupanda|jinsi ya kupanda'
                r'|namna ya kupanda|mbinu za kupanda)\b'), 'nafasi za kupanda'),
]


NEW_TOPIC = re.compile(r'\b(swali (jipya|jingine|lingine)|kitu (kingine|kipya)|jambo (jingine|jipya)|nina swali)\b')
RESUME = re.compile(r'\b(tuendelee|endelea|tuendeleee|turudi|rudi|hapo hapo|hapohapo|ndiyo|ndio|sawa|yes|poa)\b')
CROP_SWITCH = re.compile(r'\b(sasa|ni|kuhusu|tuongelee|turudi|kwenye|basi|nataka|zao|la|ya|kwa|tuendelee|na)\b')
TOPIC_NAMES = {'planting_advisor': 'wakati wa kupanda', 'seed_advisor': 'mbegu bora', 'soil_advisor': 'udongo',
               'rotation_advisor': 'mzunguko wa mazao', 'rules_engine': 'tatizo shambani'}


def _last_topic(user):
    for last in Conversation.objects.filter(user=user, message_direction='outbound').order_by('-id')[:6]:
        mode = (last.trace or {}).get('mode')
        if mode in TOPIC_NAMES:
            return TOPIC_NAMES[mode]
    mode = ''
    return TOPIC_NAMES.get(mode, '')


def _crop_menu_reply(user, raw_message, normalized, crop, start_time, message_id, decision):
    topic = _last_topic(user) if decision == 'resume' else ''
    _clear_pending(user)
    if user.last_crop_id != crop.id:
        user.last_crop_id = crop.id
        user.save(update_fields=['last_crop_id'])
    sess = dict(user.session_state or {})
    sess['goal_pending'] = True
    user.session_state = sess
    user.save(update_fields=['session_state'])
    response = dg.build_crop_menu(crop.crop_name_sw, topic)
    _log_all(user, raw_message, normalized, crop, None, '', None, response, True, start_time,
             message_id=message_id, trace={'mode': 'goal_question', 'decision': decision})
    return response


def _handle_resume_or_crop_only(user, raw_message, normalized, start_time, message_id):
    """
    Live 15 Nov: salamu iliuliza "tuendelee hapo, au una swali jipya?", lakini "Sasa ni mpunga"
    ilipata salamu ileile tena, "Nina swali jipya" ikapata "sielewi", na "turudi kwenye mahindi"
    ikarudia jibu la zamani bila kuuliza. Sasa majibu hayo yanashughulikiwa hapa.
    """
    sess = dict(user.session_state or {})
    offer = sess.pop('resume_offer', None)
    if offer is not None:
        user.session_state = sess
        user.save(update_fields=['session_state'])
    fresh = (offer is not None and time.time() - float(offer) < 900)
    words = normalized.split()
    if len(words) > 6 or rx.get_state(sess):
        return None
    crop = detect_crop(normalized)
    if NEW_TOPIC.search(normalized) and not crop and (fresh or len(words) <= 5):
        _clear_pending(user)
        response = ("Sawa, karibu! 🌿 Uliza swali lako — kuhusu *tatizo shambani*, *mbegu bora*, "
                    "*wakati wa kupanda*, *udongo* au *mzunguko wa mazao*.")
        _log_all(user, raw_message, normalized, None, None, '', None, response, True, start_time,
                 message_id=message_id, trace={'mode': 'goal_question', 'decision': 'new_topic'})
        return response
    adv = sess.get('adv') or {}
    if adv.get('stage') in ('crop', 'location') and not fresh:
        return None                              # "mahindi"/"kondoa" ni jibu la swali linalosubiriwa
    leftover = [w for w in words if not CROP_SWITCH.match(w) and not RESUME.match(w)
                and not (crop and (w in crop.crop_name_sw.lower().split() or w in crop.crop_name_en.lower().split()))]
    if NEW_TOPIC.search(normalized) and not crop and (fresh or len(words) <= 5):
        response = ("Sawa, karibu! 🌿 Uliza swali lako — kuhusu *tatizo shambani*, *mbegu bora*, "
                    "*wakati wa kupanda*, *udongo* au *mzunguko wa mazao*.")
        _log_all(user, raw_message, normalized, None, None, '', None, response, True, start_time,
                 message_id=message_id, trace={'mode': 'goal_question', 'decision': 'new_topic'})
        return response
    if crop and not leftover:
        # "Sasa ni mpunga", "mpunga", "turudi kwenye mahindi" — zao tu, bila swali
        return _crop_menu_reply(user, raw_message, normalized, crop, start_time, message_id,
                                'resume' if user.last_crop_id == crop.id else 'crop_switch')
    if fresh and RESUME.search(normalized) and not leftover and user.last_crop_id:
        last = Crop.objects.filter(id=user.last_crop_id).first()
        if last:
            return _crop_menu_reply(user, raw_message, normalized, last, start_time, message_id, 'resume')
    return None


def understanding_enabled():
    from diagnosis import ai_layer
    return getattr(settings, 'UNDERSTAND_FIRST', True) and ai_layer.available()


def _clear_pending(user, keep_rx=False):
    sess = dict(user.session_state or {})
    for k in ('adv', 'awaiting_location', 'awaiting_crop', 'saved_intent', 'goal_pending'):
        sess.pop(k, None)
    if not keep_rx:
        sess.pop(rx.STATE_KEY, None)
    user.session_state = sess
    user.save(update_fields=['session_state'])


def _route_goal(user, raw_message, normalized, frame, start_time, message_id):
    """Kidhibiti kimoja kwa kila lengo. Kila tawi linarudisha jibu (halirudishi None)."""
    goal = frame['goal']
    crop = frame['crop'] or detect_crop(normalized)
    ctx_crop = crop or _recent_crop(user) or (
        Crop.objects.filter(id=user.last_crop_id).first() if user.last_crop_id else None)
    in_rx = bool(rx.get_state(user.session_state or {}))
    trace = {'mode': 'understand', 'frame': understanding.as_trace(frame)}

    def log(response, success=True, c=None, decision=None):
        _log_all(user, raw_message, normalized, c or crop, None, frame.get('place') or '', None, response,
                 success, start_time, message_id=message_id, trace={**trace, 'decision': decision or goal})
        return response

    def unclear():
        return _unclear(user, raw_message, normalized, frame, start_time, message_id)

    if goal == 'greeting':
        return log(build_greeting(is_returning=user.message_count > 1,
                                  last_crop=ctx_crop.crop_name_sw if ctx_crop else ''))
    if goal == 'diagnosis':
        _clear_pending(user)
        return _start_diagnostic(user, raw_message, normalized, crop, start_time, message_id)
    if goal == 'followup':
        response = _diagnosis_followup(user, normalized, force=True)
        if response:
            return log(response)
        if dg.is_problem_message(normalized, None):
            _clear_pending(user)
            return _start_diagnostic(user, raw_message, normalized, crop, start_time, message_id)
        return unclear()
    if goal == 'abiotic':
        _clear_pending(user)
        return _abiotic_reply(user, raw_message, normalized, ctx_crop, start_time, message_id)
    if goal == 'challenge':
        # Changamoto ya wazi kwa maneno ("kwa nini umenishauri…") inakubaliwa; ya AI peke yake
        # inahitaji ushauri halisi kwenye majibu ya karibuni (live: "jua ni kali…" haikuwa changamoto)
        if ctx_crop and (frame['source'] != 'ai' or understanding.advice_recent(user)):
            _clear_pending(user)
            return _self_correction(user, raw_message, normalized, ctx_crop, start_time, message_id)
        goal = 'complaint'
    if goal == 'complaint':
        _clear_pending(user)
        question = frame.get('question') or ''
        if question and question.strip().lower() != raw_message.strip().lower() and understanding_enabled():
            q_norm = apply_synonyms(normalize_text(question))
            inner = understanding.understand(question, user, normalized=q_norm, use_ai=True)
            if inner['goal'] not in ('complaint', 'challenge', 'answer', 'unclear'):
                st = dict(user.session_state or {})
                st['apologize'] = True
                user.session_state = st
                user.save(update_fields=['session_state'])
                return _route_goal(user, raw_message, q_norm, inner, start_time, message_id)
        st = dict(user.session_state or {})
        st.pop('apologize', None)
        st['goal_pending'] = True
        user.session_state = st
        user.save(update_fields=['session_state'])
        return log(dg.build_goal_question(opener="Samahani, nadhani nilikuelewa vibaya. 🙏 Niambie unahitaji nini:"))
    if goal == 'gap':
        _clear_pending(user)
        response = gap_answer(frame['topic'], ctx_crop)
        log(response, success=False, c=ctx_crop)
        _log_unresolved(user, raw_message, normalized, ctx_crop, None, response)
        return response
    if goal == 'where_grows':
        _clear_pending(user)
        _s = dict(user.session_state or {})
        rep = time.time() - float(_s.get('where_grows_at', 0)) < RECENT_CROP_MINUTES * 60
        _s['where_grows_at'] = time.time()
        user.session_state = _s
        user.save(update_fields=['session_state'])
        response = adv_coverage.where_grows_message(ctx_crop, repeat=rep)
        log(response, success=False, c=ctx_crop)
        _log_unresolved(user, raw_message, normalized, ctx_crop, None, response)
        return response
    if goal == 'coverage':
        return log(adv_coverage.coverage_message())
    if goal in ('seed', 'planting', 'soil', 'rotation'):
        _clear_pending(user)
        if crop and user.last_crop_id != crop.id:
            user.last_crop_id = crop.id
            user.save(update_fields=['last_crop_id'])
        mcrop = crop or (ctx_crop if goal != 'rotation' else None)
        if goal == 'seed':
            handled = _seed_turn(user, raw_message, normalized, mcrop, start_time, message_id)
        elif goal == 'planting':
            handled = _planting_turn(user, raw_message, normalized, mcrop, start_time, message_id)
        elif goal == 'soil':
            handled = _soil_turn(user, raw_message, normalized, mcrop, start_time, message_id)
        else:
            handled = _rotation_turn(user, raw_message, normalized, start_time, message_id)
        if handled is not None:
            return handled
        return _module_no_data(user, raw_message, normalized, goal, mcrop, start_time, message_id)
    if goal == 'crop_only' and crop:
        return _crop_menu_reply(user, raw_message, normalized, crop, start_time, message_id,
                                'resume' if user.last_crop_id == crop.id else 'crop_switch')
    if goal == 'location_only':
        handled = _location_only(user, raw_message, normalized, crop, start_time, message_id)
        if handled is not None:
            return handled
    if goal == 'thanks' and not in_rx:
        return log(build_acknowledgement(ctx_crop.crop_name_sw if ctx_crop else ''))
    if goal == 'identity':
        return log(build_identity_message())
    if goal == 'capability':
        return log(build_capability_message())
    if goal == 'offtopic':
        return log(build_offtopic_message())
    return unclear()


def _self_correction(user, raw_message, normalized, crop, start_time, message_id):
    """Kiri kosa, futa ushauri wa awali, anza uchunguzi upya kwa kuuliza dalili (intake)."""
    state = rx.new_state()
    state.update({'phase': 'intake', 'crop_id': crop.id, 'intake_tries': 0})
    _save_rx(user, state)
    response = ("Uko sahihi, samahani. 🙏 Nilipaswa kuanza kwa kukuuliza maswali kabla ya kukushauri "
                "chochote. Ushauri wowote wa kuondoa, kuchoma au kunyunyizia mimea *usiufuate* mpaka "
                "tatizo lithibitishwe.\n\nTuanze upya. " + rx.intake_message(crop.crop_name_sw))
    _log_all(user, raw_message, normalized, crop, None, '', None, response, True,
             start_time, message_id=message_id,
             trace={'mode': 'rules_engine', 'decision': 'self_correction', 'asked': 'intake'})
    return response


def knowledge_gap_topic(normalized):
    for rx_, topic in KNOWLEDGE_GAPS:
        if rx_.search(normalized):
            if topic == '__mbolea__':
                if _strict() and not dg.is_problem_message(normalized, None):
                    return 'mbolea'
                continue
            return topic
    if (_strict() and not dg.is_problem_message(normalized, None) and not adv_rotation.wants_rotation(normalized)
            and not adv_seed.wants_seed(normalized)):
        for rx_, topic in STRICT_GAPS:
            if rx_.search(normalized):
                return topic
    return ''


def gap_answer(topic, crop):
    """Jibu la mada isiyo na data — pamoja na kipande chochote kilichopo kwenye dataset."""
    if topic == 'kuvuna' and crop:
        from advisory.models import VarietyAgronomy
        rows = [v for v in VarietyAgronomy.objects.filter(crop=crop, is_active=True)
                if v.maturity_days_min and v.maturity_days_max][:5]
        if rows:
            items = '\n'.join(f"• {v.name}: siku *{v.maturity_days_min}–{v.maturity_days_max}*" for v in rows)
            return (f"🌾 Muda wa kukomaa wa mbegu za {crop.crop_name_sw} (kutoka taarifa zangu za mbegu):\n"
                    f"{items}\n\nHesabu kuanzia siku ya kupanda. Kuhusu dalili za kukomaa na jinsi ya kuvuna, "
                    "bado sina taarifa zilizothibitishwa — kwa hiyo sitabuni. 📞 Afisa ugani atakusaidia.")
    return knowledge_gap_message(topic)


def knowledge_gap_message(topic):
    return (
        f"🌱 Swali lako kuhusu *{topic}* ni muhimu, lakini bado sina taarifa za kitaalamu "
        "zilizothibitishwa kuhusu hilo kwenye data yangu — kwa hiyo sitabuni.\n\n"
        "📞 Afisa ugani wa eneo lako atakusaidia kwa hili.\n\n"
        "Kwa sasa naweza kukusaidia kuhusu: *matatizo ya mazao* (wadudu, magonjwa, dalili), "
        "*mbegu bora*, *wakati wa kupanda*, *udongo* na *mzunguko wa mazao*."
    )


RECENT_CROP_MINUTES = 30


# ── Maji / ukame / mbolea (hali za mazingira) ──
# Live 14 Nov: "ardhi imekauka, mbolea sikuweka — hiyo inaweza kuwa sababu?" ilipuuzwa na bot
# ikaendelea na maswali ya wadudu, kisha "mbona hunijibu swali langu?" ikajibiwa kwa mfano wa mbegu.
# MHD-007 haina kanuni za hali hizi, kwa hiyo tunajibu swali kwa ukweli bila kubuni utambuzi.
ABIOTIC = re.compile(
    r'\b(ukame|hakuna mvua|mvua (hakuna|haipo|imekata|imegoma|ni shida|kidogo|zimezingua|imezingua|haijanyesha)'
    r'|ardhi (imekauka|kavu|ni kavu)|udongo (umekauka|mkavu|ni mkavu)|ukosefu wa maji|maji (hakuna|kidogo|ni shida)'
    r'|sikuweka mbolea|sijaweka mbolea|hatukuweka mbolea|bila mbolea|mbolea (pia )?(sikuweka|sijaweka|hatukuweka)'
    r'|virutubisho|upungufu wa (mbolea|naitrojeni|nitrojeni|virutubisho))\b')
ABIOTIC_ASK = re.compile(
    r'\?|\b(inaweza|yaweza|huenda|sababu|chanzo|unadhani|au ni|ni hiyo|ndiyo inasababisha|inasababisha'
    r'|nifanyeje|nifanye nini|tu au|au kuna)\b')


def is_abiotic_question(normalized):
    return bool(ABIOTIC.search(normalized) and ABIOTIC_ASK.search(normalized))


def _abiotic_reply(user, raw_message, normalized, crop, start_time, message_id):
    name = crop.crop_name_sw if crop else 'mimea'
    sess = dict(user.session_state or {})
    repeat = time.time() - float(sess.get('abiotic_at', 0)) < RECENT_CROP_MINUTES * 60
    sess['abiotic_at'] = time.time()
    user.session_state = sess
    user.save(update_fields=['session_state'])
    if repeat:
        # Asirudishiwe jibu lilelile (kigezo 1): jibu fupi, la moja kwa moja
        response = ("Samahani kama jibu langu halikuwa wazi. 🙏 Kwa ufupi:\n\n"
                    "• Kwa uliyoniambia, sioni ushahidi wa wadudu au magonjwa niliyo na taarifa zake.\n"
                    "• Ukame na kukosa mbolea *vinaweza* kuwa chanzo, lakini data yangu haina kanuni za kuthibitisha "
                    "hilo — kwa hiyo sitakupa jibu la kubahatisha.\n"
                    "• Usinyunyizie dawa ya wadudu kwa sasa.\n\n"
                    "📞 Afisa ugani akikagua shamba na udongo atakupa uhakika na ushauri wa mbolea na maji.")
        _log_all(user, raw_message, normalized, crop, None, '', None, response, True, start_time,
                 message_id=message_id, trace={'mode': 'profile', 'decision': 'abiotic_question', 'repeat': True})
        return response
    opener = ("Samahani kwa kutokujibu swali lako moja kwa moja. 🙏" if _is_complaint(normalized)
              else "Swali zuri, asante kwa kunieleza hali ya shamba lako. 🙏")
    lines = [opener, '',
             "Hali kama *ukame* au *kutoweka mbolea* inaweza kuchangia majani kuwa ya njano. Lakini kwa "
             "uaminifu: taarifa zangu za uchunguzi zilizothibitishwa kwa sasa zinahusu *wadudu na magonjwa* tu "
             "— hazina kanuni za upungufu wa maji au virutubisho. Kwa hiyo *siwezi kuthibitisha* kama hicho "
             "ndicho chanzo, na sitakisia."]
    profile = None
    if crop and not _strict():
        from crops.models import CropProfile
        profile = CropProfile.objects.filter(crop=crop).exclude(fertilizer_top_dressing='').first()
    if profile:
        lines += ['', f"*Kuhusu mbolea ya kukuzia {name}* (kutoka taarifa zangu):", profile.fertilizer_top_dressing]
    lines += ['', "*Hatua salama za sasa:*",
              "• Kagua mimea sehemu tofauti za shamba: kama huoni wadudu, funza wala mistari/madoa, "
              "huenda tatizo si la wadudu au magonjwa",
              "• *Usinyunyizie dawa ya wadudu* kabla tatizo halijathibitishwa",
              '', "📞 *Afisa ugani* wa kata yako anaweza kukagua shamba na udongo, na kukushauri kuhusu "
              "maji na mbolea inayofaa."]
    response = '\n'.join(lines)
    _log_all(user, raw_message, normalized, crop, None, '', None, response, True, start_time,
             message_id=message_id, trace={'mode': 'profile', 'decision': 'abiotic_question',
                                           'data_used': 'CropProfile.fertilizer_top_dressing' if profile else ''})
    _log_unresolved(user, raw_message, normalized, crop, None, response)
    return response


# ── Kufuatilia utambuzi uliotolewa ──
FOLLOWUP = re.compile(r'\b(nifanye nini|nifanyeje|hatua gani|dawa gani|nitumie dawa|nitumie nini|nichanganye'
                      r'|kiasi gani cha dawa|mililita|ml ngapi|nitibu|tiba yake)\b')
DOSAGE = re.compile(r'\b(dawa gani|nitumie dawa|nichanganye|mililita|ml ngapi|kiasi gani cha dawa|bomba la lita)\b')


def _remember_diagnosis(user, state, trace, response):
    actions = ''
    if '*Hatua za kuchukua:*' in response:
        actions = response.split('*Hatua za kuchukua:*', 1)[1].split(rx.DISCLAIMER)[0].strip()
    sess = dict(user.session_state or {})
    sess['last_dx'] = {'cid': trace.get('diagnosis'), 'crop_id': state.get('crop_id'), 'at': time.time(),
                       'confidence': trace.get('confidence'), 'actions': actions}
    user.session_state = sess
    user.save(update_fields=['session_state'])


def _diagnosis_followup(user, normalized, force=False):
    dx = (user.session_state or {}).get('last_dx')
    if not dx or time.time() - float(dx.get('at', 0)) > RECENT_CROP_MINUTES * 60:
        return ''
    cause = rx._cause(dx['cid'])
    if cause is None:
        return ''
    name = rx._cause_name(cause)
    low = normalized.lower()
    name_words = [w for w in re.findall(r'[a-z]+', name.lower()) if len(w) >= 5]
    mentions = any(w in low for w in name_words)
    # Maelezo ya dalili mpya bila kutaja tatizo lililotambuliwa = uchunguzi mpya, si kufuatilia
    new_symptoms = not rx.is_vague(low)
    if not force and not (mentions or (FOLLOWUP.search(low) and not new_symptoms)):
        return ''
    conf = dx.get('confidence')
    lines = [("Ndiyo. " if mentions else '') + f"Kwa majibu uliyonipa, tatizo linaloendana zaidi ni *{name}*"
             + (f" (uhakika {round(conf * 100)}%)." if conf else '.')]
    if dx.get('actions'):
        lines += ['', '*Hatua za kuchukua:*', dx['actions']]
    if DOSAGE.search(low):
        lines += ['', "*Kuhusu dawa na kiasi cha kuchanganya:* sitoi jina la dawa wala kipimo chake. "
                      "Ukihitaji dawa, nunua iliyosajiliwa kwa duka la pembejeo, fuata maelekezo ya *kibandiko* "
                      "chake, na mshirikishe *afisa ugani* kwanza."]
    lines += ['', rx.DISCLAIMER]
    return '\n'.join(lines)


def _recent_crop(user):
    """Zao la ujumbe wa mwisho wa mkulima, ikiwa ulikuwa ndani ya dakika 30."""
    from datetime import timedelta
    from django.utils import timezone
    prev = (Conversation.objects.filter(user=user, message_direction='inbound',
                                        created_at__gte=timezone.now() - timedelta(minutes=RECENT_CROP_MINUTES))
            .exclude(detected_crop=None).order_by('-id').first())
    return prev.detected_crop if prev else None


# ── Mkulima akibadilisha mada au akilalamika katikati ya uchunguzi ──
# Live: "Jinsi ya kupanda mahindi chunya" katikati ya maswali ilijibiwa "Samahani kama swali
# halikuwa wazi…", na "Nimeuliza hatua za kupanda mahindi" ikajibiwa "Hakuna shida" + Swali 2.
COMPLAINT = re.compile(
    r'\b(sijauliza|sikuuliza|nimeuliza|nimekuuliza|mbona|hujanielewa|hujaelewa|umenielewa vibaya'
    r'|sio hivyo|si hivyo|sio swali langu|si swali langu|swali langu ni|sikuuliza hilo'
    r'|sijakuambia|sijakueleza|sijataja|hukuniuliza|umekosea|si ungeanza|ungeanza|ungeniuliza'
    r'|kwa nini umenishauri|kwa nini unanishauri|kwa nini umesema|kwa nini unasema)\b')
# Changamoto kwa USHAURI wa bot (Test 2 ya mteja): "kwa nini umenishauri niondoe na kuchoma
# mimea? Si ungeanza kwa kuniuliza maswali?" → kiri, futa ushauri, anza upya kwa kuuliza.
CHALLENGE = re.compile(
    r'\b(umenishauri|unanishauri|ushauri wako|kuniuliza maswali|ungeniuliza|ungeanza|hukuniuliza'
    r'|sijakuambia|sijakueleza|sijataja)\b')
NEW_QUESTION = re.compile(
    r'\b(jinsi ya|namna ya|hatua za|bei ya|bei za|soko la|masoko|mbolea gani|mbolea ya|mbegu gani'
    r'|mbegu ya|nipande|nitapanda|kupanda|nivune|kuvuna|wakati wa kupanda|lini)\b')


def _is_complaint(normalized):
    return bool(COMPLAINT.search(normalized))


def _is_new_question(normalized):
    """Ujumbe ni swali jipya (si jibu la swali la uchunguzi)."""
    if rx.parse_answer(normalized) != 'unknown':
        return False                       # "ndiyo nimeona…" ni jibu
    if adv_coverage.wants_coverage(normalized) or adv_rotation.wants_rotation(normalized):
        return True
    if len(normalized.split()) < 3:
        return False
    return bool(NEW_QUESTION.search(normalized))


def _apology_prefix(user):
    """Jibu la kwanza baada ya malalamiko linaanza kwa kuomba radhi."""
    sess = dict(user.session_state or {})
    if sess.pop('apologize', None):
        user.session_state = sess
        user.save(update_fields=['session_state'])
        return "Samahani, nadhani nilikuelewa vibaya. 🙏\n\n"
    return ''


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
        _gcrop = detect_crop(normalized) or (Crop.objects.filter(id=user.last_crop_id).first()
                                             if user.last_crop_id else None)
        if route == 'seed_selection':
            handled = _seed_turn(user, raw_message, normalized, _gcrop, start_time, message_id)
            if handled is not None:
                return handled
        if route == 'planting_time':
            handled = _planting_turn(user, raw_message, normalized, _gcrop, start_time, message_id)
            if handled is not None:
                return handled
        if route == 'soil':
            return _soil_turn(user, raw_message, normalized, _gcrop, start_time, message_id)
        if route == 'rotation':
            return _rotation_turn(user, raw_message, normalized, start_time, message_id)
        if route in ('seed_selection', 'planting_time'):
            return _module_no_data(user, raw_message, normalized,
                                   'seed' if route == 'seed_selection' else 'planting', _gcrop,
                                   start_time, message_id)
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

    # Mkulima anauliza kama ni maji/ukame/mbolea → mjibu swali lake (live: "mbona hunijibu swali langu?")
    if state['phase'] != 'crop' and is_abiotic_question(normalized):
        _save_rx(user, None)
        crop = Crop.objects.filter(id=state.get('crop_id')).first() if state.get('crop_id') else None
        return _abiotic_reply(user, raw_message, normalized, crop, start_time, message_id)

    # Mkulima amebadilisha mada ("jinsi ya kupanda mahindi…") au analalamika
    # ("nimeuliza hatua za kupanda") → acha uchunguzi, shughulikia ujumbe wake.
    complaint = _is_complaint(normalized)
    if state['phase'] != 'crop' and (complaint or _is_new_question(normalized)):
        _save_rx(user, None)
        if complaint:
            sess = dict(user.session_state or {})
            sess['apologize'] = True
            user.session_state = sess
            user.save(update_fields=['session_state'])
        return None

    return _rx_step(user, state, raw_message, normalized, start_time, message_id,
                    fresh_crop=detect_crop(normalized) if state['phase'] == 'crop' else None)
