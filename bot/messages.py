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



def build_greeting(is_returning: bool = False, last_crop: str = '') -> str:
    """
    Salamu fupi. Mkulima anayerudi hapewi utangulizi mrefu tena —
    tunamkumbuka na kuendelea pale tulipoishia.
    """
    if is_returning:
        # Bot haitoi salamu za heshima/rika ("Shikamoo") — inakaribisha tu
        opening = "Karibu tena! 🌿"
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
        + _services_line() + ".\n\n"
        "Uliza tu kwa Kiswahili cha kawaida.\n"
        f"_Mfano: {_seed_example()}_\n\n"
        "Ukihitaji mwongozo wakati wowote, andika *0*."
    )


def _services_line():
    # Tunaahidi tu kile chenye data iliyothibitishwa
    return "matatizo ya mazao (wadudu, magonjwa, dalili), mbegu bora, wakati wa kupanda, udongo na mzunguko wa mazao"


# ── Kuomba zao ────────────────────────────────────────

# ── Kuomba eneo ───────────────────────────────────────

# ── Eneo halikueleweka ────────────────────────────────

# ── Dalili: kuomba maelezo zaidi ──────────────────────

# ── Jibu kuu ──────────────────────────────────────────

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

# ── Tatizo la kiufundi ────────────────────────────────

def _example_place():
    """Eneo LILILOMO kwenye data ya maeneo (MHD-001) — mfano usimpeleke mkulima kwenye 'sina taarifa'."""
    try:
        from advisory.coverage import example_place
        return example_place()
    except Exception:
        return ''


def _seed_example():
    place = _example_place()
    return f"Ni mbegu gani ya mahindi nipande {place}?" if place else "Ni mbegu gani ya mahindi inafaa eneo langu?"


def _planting_example():
    place = _example_place()
    return f"Mahindi yapandwe lini {place}?" if place else "Mahindi yapandwe lini?"


# ── Mwongozo ──────────────────────────────────────────
def _help_extra():
    return "• _Udongo wangu ni mfinyanzi, unafaa mahindi?_\n\n"


def build_help_message() -> str:
    return (
        "📋 *Jinsi ya kunitumia*\n\n"
        "Uliza tu kwa Kiswahili cha kawaida, kama unavyoongea na "
        "afisa ugani. Mifano:\n\n"
        f"• _{_seed_example()}_\n"
        f"• _{_planting_example()}_\n"
        "• _Mahindi yana viwavi, nifanye nini?_\n"
        + _help_extra() +
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
    'wewe ni nini', 'nani wewe', 'unaitwaje', 'mtu au roboti', 'wewe ni roboti', 'ni roboti',
    'wewe ni mtu', 'binadamu au', 'wewe ni ai', 'taarifa unatoa wapi', 'unatoa wapi taarifa',
    'unapata wapi taarifa', 'taarifa zako zinatoka', 'chanzo cha taarifa', 'unajuaje',
}

CAPABILITY_PATTERNS = {
    'unaweza nini', 'unaweza kufanya nini', 'unafanya nini', 'kunisaidia nini', 'unasaidia nini',
    'unaweza kusaidia nini', 'huduma gani',
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
        + _services_line() + ".\n\n"
        "Taarifa zangu zinatoka kwenye dataset za kitaalamu zilizoandaliwa na kuthibitishwa na timu ya "
        "*KILIMONI LABS*. Kitu kisichokuwemo kwenye data hiyo, nakwambia wazi — sibuni.\n\n"
        "Una swali lolote la shamba lako?"
    )


def build_capability_message() -> str:
    return (
        "Nasaidia mambo ya shamba 🌿\n\n"
        "• Matatizo ya mazao — wadudu, magonjwa na dalili (kwa maswali ya uchunguzi)\n"
        "• Mbegu bora kwa eneo lako\n"
        "• Wakati sahihi wa kupanda\n"
        "• Udongo na ufaafu wake kwa zao\n"
        "• Mzunguko wa mazao\n\n"
        f"_Mfano: {_seed_example()}_"
    )


def build_offtopic_message() -> str:
    """
    Swali ambalo bot haikulielewa au liko nje ya kilimo. Kwa unyenyekevu:
    tunaonyesha tunataka kumwelewa mkulima, na tunampa mada tunazoweza.
    """
    return (
        "Samahani, natamani nielewe vizuri shida yako. 🙏\n\n"
        "Tafadhali niulize kuhusu hali ya shamba, mazao, mbegu, mbolea, "
        "wadudu au masoko."
    )
