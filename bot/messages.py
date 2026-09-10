import random

# ═══════════════════════════════════════════════════════
# MAZUNGUMZO — Kiswahili cha kawaida, si cha kikompyuta
#
# Kanuni tunazofuata hapa:
#  1. Tunaongea kama mtu, si kama fomu. Hakuna mistari
#     mirefu ya mapambo wala emoji nyingi.
#  2. Tunarudia kile mkulima alichokisema, ili ajue
#     tumemsikia ("Umeuliza kuhusu mbegu...").
#  3. Tunabadilisha maneno kila mara ili isionekane
#     kama rekodi inayojirudia.
#  4. Hata tukishindwa, tunaendeleza mazungumzo —
#     hatuonyeshi kwamba mfumo umekwama.
# ═══════════════════════════════════════════════════════


def _pick(options):
    """Chagua msemo mmoja — kuepusha bot kujirudia kila mara."""
    return random.choice(options)


# Maelezo ya kila intent kwa lugha ya kawaida.
# Hii ndiyo inayotuwezesha kusema "kuhusu mbolea" badala ya
# "fertilizer_planting" au kunyamaza kabisa.
INTENT_TOPICS = {
    'seed_selection': 'mbegu',
    'variety_by_location': 'aina ya mbegu',
    'planting_time': 'wakati wa kupanda',
    'spacing': 'nafasi ya kupanda',
    'fertilizer_planting': 'mbolea ya kupandia',
    'fertilizer_top_dressing': 'mbolea ya kukuzia',
    'fertilizer_amount': 'kiasi cha mbolea',
    'pest_identification': 'wadudu',
    'disease_identification': 'ugonjwa',
    'symptom_analysis': 'dalili unazoziona',
    'harvest_time': 'wakati wa kuvuna',
    'storage_advice': 'kuhifadhi',
    'market_question': 'bei na soko',
}


def topic_of(intent) -> str:
    """Rudisha jina la mada kwa lugha ya kawaida."""
    if not intent:
        return ''
    return INTENT_TOPICS.get(intent.intent_name, '')


# ── Salamu ────────────────────────────────────────────
def build_greeting(is_returning: bool = False, last_crop: str = '') -> str:
    """
    Salamu fupi. Mkulima anayerudi hapewi utangulizi mrefu tena —
    tunamkumbuka na kuendelea pale tulipoishia.
    """
    if is_returning:
        opening = _pick([
            "Karibu tena! 🌿",
            "Habari yako! 🌿",
            "Shikamoo, karibu tena. 🌿",
        ])
        if last_crop:
            return (
                f"{opening}\n\n"
                f"Mara ya mwisho tuliongelea *{last_crop}*. "
                "Unataka tuendelee hapo, au una swali jipya?"
            )
        return (
            f"{opening}\n\n"
            "Niambie unahitaji msaada gani leo shambani."
        )

    return (
        "🌿 *Karibu Kilimoni AI*\n\n"
        "Mimi ni msaidizi wako wa kilimo. Naweza kukusaidia kuhusu "
        "mbegu, wakati wa kupanda, mbolea, wadudu na magonjwa, "
        "kuvuna, na bei za sokoni.\n\n"
        "Uliza tu kwa Kiswahili cha kawaida.\n"
        "_Mfano: Ni mbegu gani ya mahindi nipande Singida?_\n\n"
        "Ukihitaji mwongozo wakati wowote, andika *0*."
    )


# ── Kuomba zao ────────────────────────────────────────
def build_crop_prompt(intent=None) -> str:
    """
    Tunataja mada aliyoiuliza, ili ajue swali lake halijapotea.
    """
    topic = topic_of(intent)

    if topic:
        opening = _pick([
            f"Sawa, umeuliza kuhusu *{topic}*.",
            f"Nimekusikia — swali lako ni la *{topic}*.",
            f"Vizuri, tuzungumzie *{topic}*.",
        ])
        question = "Ni zao gani unalolima?"
    else:
        opening = _pick([
            "Nisaidie kidogo.",
            "Nikuelewe vizuri.",
        ])
        question = "Ni zao gani unalouliza?"

    return (
        f"{opening}\n\n"
        f"{question}\n\n"
        "🌽 Mahindi   🫘 Maharage   🌾 Mpunga\n\n"
        "_Andika jina la zao tu, mfano: mahindi_"
    )


# ── Kuomba eneo ───────────────────────────────────────
def build_location_prompt(crop, intent=None) -> str:
    """
    Tunaeleza KWA NINI tunahitaji eneo — mkulima asijisikie
    anahojiwa bure.
    """
    crop_name = crop.crop_name_sw if crop else 'zao lako'
    topic = topic_of(intent)

    if topic in ('mbegu', 'aina ya mbegu'):
        reason = f"Mbegu bora za *{crop_name}* hutofautiana kulingana na eneo"
    elif topic == 'wakati wa kupanda':
        reason = "Wakati wa kupanda hutegemea mvua za eneo lako"
    elif topic == 'bei na soko':
        reason = "Bei hutofautiana kati ya mkoa na mkoa"
    else:
        reason = f"Ushauri wa *{crop_name}* hutegemea hali ya hewa ya eneo lako"

    return (
        f"{reason}. 📍\n\n"
        f"{_pick(['Uko mkoa gani?', 'Niambie mkoa au wilaya yako.', 'Uko wapi?'])}\n\n"
        "_Mfano: Singida, Mbeya, Mwanza_"
    )


# ── Eneo halikueleweka ────────────────────────────────
def build_location_retry() -> str:
    return (
        "Samahani, sijalitambua hilo eneo. 📍\n\n"
        "Jaribu kuandika jina la *mkoa* au *wilaya* peke yake.\n"
        "_Mfano: Singida, Dodoma, Mbeya, Mwanza_\n\n"
        "_Au uliza swali lingine lolote — tutaendelea._"
    )


# ── Dalili: kuomba maelezo zaidi ──────────────────────
def build_symptom_followup(crop_name: str) -> str:
    return (
        f"Pole kwa hilo. Tuchunguze *{crop_name}* yako. 🔍\n\n"
        "Nisaidie kwa mambo matatu:\n\n"
        "*1.* Sehemu gani imeathirika — majani, shina au tunda?\n"
        "*2.* Dalili ni ya aina gani — njano, kahawia, madoa, mashimo?\n"
        "*3.* Mmea una umri gani?\n\n"
        "_Mfano: majani ya chini yana madoa ya kahawia, mmea una miezi 2_"
    )


# ── Jibu kuu ──────────────────────────────────────────
def format_response(answer_data: dict, crop, intent, location: str) -> str:
    """
    Jibu jepesi la kusoma kwenye simu. Hakuna mistari ya mapambo —
    kichwa kifupi tu, kisha maudhui.
    """
    if not answer_data.get('found'):
        return None

    parts = []

    if crop and location:
        parts.append(f"🌾 *{crop.crop_name_sw}* — {location}\n")
    elif crop:
        parts.append(f"🌾 *{crop.crop_name_sw}*\n")

    parts.append(answer_data['answer_text'])

    if answer_data.get('caution'):
        parts.append(f"\n⚠️ {answer_data['caution']}")

    if answer_data.get('follow_up'):
        parts.append(f"\n_{answer_data['follow_up']}_")

    return '\n'.join(parts)


# ── Kukubali / shukrani ───────────────────────────────
def build_acknowledgement(last_crop: str = '') -> str:
    """
    Mkulima akisema "sawa", "asante", "poa" — tunajibu kama mtu,
    si kwa kumuuliza tena swali lile lile.
    """
    base = _pick([
        "Karibu sana! 🌿",
        "Asante kwa kuuliza. 🌿",
        "Nimefurahi kukusaidia. 🌿",
    ])

    if last_crop:
        tail = _pick([
            f"Ukiwa na swali lingine kuhusu *{last_crop}* au zao lingine, niko hapa.",
            "Ukihitaji kitu kingine, niandikie tu.",
        ])
    else:
        tail = "Ukihitaji msaada mwingine wowote, niandikie tu."

    return f"{base}\n\n{tail}"


# ── Tumeshindwa kujibu ────────────────────────────────
def build_fallback_message(crop=None, intent=None, location: str = '') -> str:
    """
    Hii inatumika tu pale template na AI zote zimeshindwa.
    Hatuonyeshi kwamba mfumo umekwama — tunaomba maelezo zaidi
    kwa staha, na tunataja tunachokijua tayari.
    """
    known = []
    if crop:
        known.append(f"*{crop.crop_name_sw}*")
    if location:
        known.append(f"eneo la *{location}*")

    opening = _pick([
        "Nimeelewa swali lako.",
        "Asante kwa swali lako.",
        "Nimekusikia.",
    ])

    if known:
        middle = (
            f"Ninajua tunaongelea {' na '.join(known)}, "
            "lakini nahitaji kidogo zaidi ili nikupe jibu sahihi."
        )
        example = "_Mfano: majani yanageuka njano_ au _nipande lini?_"
    else:
        middle = (
            "Ili nikupe ushauri unaofaa, niambie *zao* unalolima "
            "na *eneo* lako."
        )
        example = "_Mfano: Mahindi yangu yana majani ya njano, niko Singida_"

    return f"{opening}\n\n{middle}\n\n{example}"


# ── Tatizo la kiufundi ────────────────────────────────
def build_technical_issue() -> str:
    """
    Pale kitu kimeharibika kabisa. Hata hapa hatumwambii mkulima
    lugha ya kiufundi — tunamwomba ajaribu tena kwa staha.
    """
    return _pick([
        (
            "Samahani, sijaweza kupata jibu kwa sasa. 🙏\n\n"
            "Jaribu tena baada ya dakika chache, au uliza kwa maneno mengine."
        ),
        (
            "Pole, kuna tatizo dogo upande wangu. 🙏\n\n"
            "Niandikie tena baada ya muda kidogo."
        ),
    ])


# ── Mwongozo ──────────────────────────────────────────
def build_help_message() -> str:
    return (
        "📋 *Jinsi ya kunitumia*\n\n"
        "Uliza tu kwa Kiswahili cha kawaida, kama unavyoongea na "
        "afisa ugani. Mifano:\n\n"
        "• _Ni mbegu gani ya mahindi nipande Singida?_\n"
        "• _Mahindi yapandwe lini Dodoma?_\n"
        "• _Mbolea ya kupandia mahindi ni ipi?_\n"
        "• _Mahindi yana viwavi, nifanye nini?_\n"
        "• _Mahindi yanavunwa lini?_\n"
        "• _Bei ya mahindi Mbeya ikoje?_\n\n"
        "💡 Ukitaja *zao* na *eneo* lako, jibu linakuwa sahihi zaidi.\n\n"
        "Unaweza pia kujibu kwa neno moja — nitakumbuka tuliyoongea."
    )


# ═══════════════════════════════════════════════════════
# MASWALI YASIYO YA KILIMO
#
# Mkulima akiuliza kitu nje ya kilimo ("unaweza kuimba?",
# "unaitwa nani?", "habari za mpira?"), jibu la kuomba zao
# na eneo halina maana kabisa. Bot inaonekana haielewi.
# Hapa tunajibu kwa staha, kisha tunamrudisha kwenye kilimo.
# ═══════════════════════════════════════════════════════

# Maneno yanayoonyesha swali LINAHUSU kilimo
FARMING_SIGNALS = {
    'mbegu', 'panda', 'kupanda', 'shamba', 'zao', 'mazao', 'mavuno',
    'kuvuna', 'vuna', 'mbolea', 'samadi', 'urea', 'dap', 'npk',
    'wadudu', 'mdudu', 'viwavi', 'funza', 'ugonjwa', 'magonjwa',
    'dawa', 'kunyunyizia', 'majani', 'shina', 'mizizi', 'maua',
    'mvua', 'ukame', 'umwagiliaji', 'maji', 'udongo', 'mkulima',
    'kilimo', 'lima', 'kulima', 'soko', 'bei', 'gunia', 'ekari',
    'hekta', 'ghala', 'kuhifadhi', 'mahindi', 'maharage', 'mpunga',
    'muhogo', 'viazi', 'alizeti', 'pamba', 'ndizi', 'nyanya',
    'kahawa', 'chai', 'korosho', 'mtama', 'ufuta', 'karanga',
    'afisa', 'ugani', 'ardhi', 'msimu', 'kupalilia', 'palizi',
}

# Maswali kuhusu bot yenyewe
IDENTITY_PATTERNS = {
    'unaitwa nani', 'jina lako', 'wewe ni nani', 'u nani',
    'wewe ni nini', 'nani wewe', 'unaitwaje',
}

CAPABILITY_PATTERNS = {
    'unaweza nini', 'unaweza kufanya nini', 'unafanya nini',
    'unasaidia nini', 'una uwezo gani', 'unajua nini',
}


def has_farming_signal(text: str) -> bool:
    """Angalia kama ujumbe una uhusiano wowote na kilimo."""
    words = set((text or '').lower().split())
    return bool(words & FARMING_SIGNALS)


def detect_offtopic_kind(text: str) -> str:
    """
    Rudisha aina ya swali lisilo la kilimo:
    'identity', 'capability', 'offtopic', au '' (ni la kilimo).
    """
    t = (text or '').lower().strip()

    if any(p in t for p in IDENTITY_PATTERNS):
        return 'identity'

    if any(p in t for p in CAPABILITY_PATTERNS):
        return 'capability'

    if has_farming_signal(t):
        return ''

    words = t.split()

    # "Unaweza ...?" bila dalili ya kilimo — anauliza uwezo wangu
    # kwa kitu nisichokifanya (mfano "unaweza kuimba?")
    if words and words[0] in ('unaweza', 'waweza', 'je') and len(words) >= 2:
        return 'offtopic'

    # Sentensi ya maneno 2+ isiyo na dalili yoyote ya kilimo.
    # Majibu mafupi ya mkulima ("mahindi", "Singida") ni neno moja,
    # kwa hiyo hayaguswi hapa.
    if len(words) >= 2:
        return 'offtopic'

    return ''


def build_identity_message() -> str:
    return (
        "Mimi ni *Kilimoni AI* 🌿\n\n"
        "Msaidizi wa kilimo kwa wakulima wa Tanzania. Nasaidia kuhusu "
        "mbegu, wakati wa kupanda, mbolea, wadudu na magonjwa, "
        "kuvuna, na bei za sokoni.\n\n"
        "Una swali lolote la shamba lako?"
    )


def build_capability_message() -> str:
    return (
        "Nasaidia mambo ya shamba 🌿\n\n"
        "• Mbegu bora kwa eneo lako\n"
        "• Wakati sahihi wa kupanda\n"
        "• Mbolea — aina na vipimo\n"
        "• Wadudu na magonjwa — kutambua na kutibu\n"
        "• Kuvuna na kuhifadhi\n"
        "• Bei za sokoni\n\n"
        "_Mfano: Mahindi yangu yana majani ya njano, niko Singida_"
    )


def build_offtopic_message() -> str:
    """
    Swali la nje ya kilimo. Tunajibu kwa ucheshi kidogo na staha —
    si kwa ukavu — kisha tunamrudisha kwenye kazi yetu.
    """
    opening = _pick([
        "Hilo liko nje ya uwezo wangu 😅",
        "Hapo umenishinda 😅",
        "Hilo silijui vizuri 😅",
    ])

    return (
        f"{opening}\n\n"
        "Mimi ni msaidizi wa *kilimo* — niko hapa kwa maswali ya shamba, "
        "mazao, mbegu, mbolea, wadudu na masoko.\n\n"
        "Una swali lolote la shamba lako?"
    )
