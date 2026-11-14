"""
Rules-based Diagnostic Engine (MHD-007)
=======================================

Injini inafanya maamuzi yote kwa kanuni za dataset ya mteja. Hakuna AI
inayoamua, na hakuna sentensi ya kubuni: kila neno la jibu linatoka
kwenye records za MHD-007 au kwenye maandishi ya mfumo yaliyoandikwa hapa.

Mtiririko kwa kila uchunguzi:

  1. Linganisha dalili za mkulima na dalili za dataset
     (007D Diagnosis rules, 007A/B decision rules, 007C symptoms,
     Visible_Symptoms za kila mdudu/ugonjwa).
  2. Orodha ya visababishi + score ya mwanzo. Kila kisababishi kinapata
     score kutoka chanzo KIMOJA, kwa kipaumbele (EngineSetting
     'initial_source'): 007D → 007A/B → Confidence_Rules ya master → 007C.
     CONF001 inaongezwa tu kama score ilitoka kwenye lebo (si kanuni ya
     namba), ili isihesabiwe mara mbili.
  3. Swali linalotenganisha visababishi zaidi. Halirudiwi (asked[]), na
     swali ambalo mkulima ameshalijibu kwenye ujumbe wake halisiulizwi.
  4. Jibu → mabadiliko ya score. Swali moja = ushahidi mmoja = uzito
     mmoja (hakuna double counting). Ishara kuu (key differentiator)
     ikithibitishwa: max(uzito wa swali, CONF002). Kikomo: confidence_cap.
  5. Kusimama: kisababishi cha kwanza ≥ diagnosis_threshold, kinaongoza
     kwa ≥ min_lead_margin, NA ishara yake kuu imethibitishwa. Vinginevyo
     maswali yakiisha → "sina uhakika" + hatua salama + afisa ugani.
  6. Safety gate: kemikali (kwa category tu, bila majina ya bidhaa —
     SAFE001) inatajwa tu kama Recommendation Rule inatimia
     (confidence ≥ Confidence_Min NA severity ≥ rec_min_severity) na
     hakuna Escalation Rule inayozuia.
  7. Explainability: kwa nini hiki, kwa nini si vingine, kanuni zilizotumika.

Hali ya uchunguzi (state) ni dict inayohifadhiwa kwenye
User.session_state['rx'] — JSON tu, hakuna objects.
"""
import re
import time

from . import models as m
from . import ai_layer, plain
from .models import get_setting

STATE_KEY = 'rx'
TIMEOUT_SECONDS = 1800

# ─────────────────────────── Maandishi ya mfumo ───────────────────────────

ASK_CROP = (
    "Pole kwa tatizo hilo. Nikusaidie kuchunguza hatua kwa hatua. 🔍\n\n"
    "Kwanza, ni *zao gani* lenye tatizo?\n"
    "_Mfano: mahindi, maharage, mpunga_"
)
ASK_SYMPTOMS = (
    "Sawa. Sasa nieleze *dalili unazoziona* kwenye {crop}.\n\n"
    "Sehemu gani imeathirika (majani, shina, gunzi) na inaonekanaje "
    "(mashimo, rangi, mistari, kukauka)?\n"
    "_Mfano: majani yana mashimo makubwa_"
)
ASK_EXTENT = (
    "Swali la mwisho: ni *kiasi gani cha shamba* kimeathirika, na je, "
    "tatizo linaenea haraka?\n"
    "_Mfano: mimea michache, nusu ya shamba, shamba lote_"
)
ANSWER_HINT = "_Jibu: ndiyo / hapana / sijui_"
REFER_EXTENSION = (
    "📞 Wasiliana na *afisa ugani* wa kata yako. Ukiweza, mpelekee picha "
    "au sampuli ya mmea ulioathirika."
)
NO_CHEMICAL_YET = (
    "• Kemikali si hatua ya kwanza. Anza na hatua zilizo juu, na kagua "
    "shamba tena baada ya siku 2–3."
)
# Hatua za tahadhari KABLA tatizo halijajulikana: zisimsababishie mkulima hasara.
# (Zamani: "ondoa mimea iliyoathirika, ichome au izike" — maoni ya mteja: hatua
# inayoharibu mimea haipaswi kutolewa kabla ya ushahidi.)
SAFE_FIRST_STEPS = (
    "• Kagua mimea mingine sehemu tofauti za shamba uone kama dalili zinaenea\n"
    "• Weka alama kwenye mimea michache iliyoathirika na uiangalie tena baada ya siku 2–3\n"
    "• *Usitumie kemikali yoyote* wala usiharibu mimea kabla tatizo halijathibitishwa"
)

# ── Maelezo yasiyo na dalili ("mimea haionekani vizuri") ──
# Taarifa HAZITOSHI ≠ SINA UJUZI: tunauliza kama afisa ugani badala ya kuhitimisha.
SYMPTOM_STEMS = (
    'jani', 'majani', 'shina', 'mizizi', 'mzizi', 'gunzi', 'mbelewele', 'ndevu', 'kitovu', 'tunda', 'matunda',
    'rangi', 'njano', 'manjano', 'kahawia', 'nyeusi', 'cheusi', 'nyeupe', 'jeupe', 'zambarau', 'nyekundu',
    'doa', 'madoa', 'michirizi', 'mistari', 'mstari', 'mabaka', 'mashimo', 'shimo', 'matundu', 'tundu',
    'tobo', 'tobolewa', 'liwa', 'meliwa', 'nyauka', 'nyong', 'kauka', 'dumaa', 'oza', 'ozea', 'kunja',
    'kunjamana', 'pukutika', 'anguka', 'vunjika', 'funza', 'mdudu', 'wadudu', 'kiwavi', 'viwavi', 'panzi',
    'buu', 'ukungu', 'kutu', 'vumbi', 'kinyesi', 'utando', 'chipukizi', 'ungua', 'babuka',
    'kula', 'tafuna', 'haribu', 'haribika',
)
_STEM_PREFIX = r'(?:ya|ma|ki|vi|ku|wa|zi|li|mi|me|na|ta|ka|ji|ni|si|ha|hu|i|a|u|m|n)*'
_SYMPTOM_RE = re.compile(r'\b' + _STEM_PREFIX + '(' + '|'.join(sorted(SYMPTOM_STEMS, key=len, reverse=True)) + ')')

INTAKE_OPTIONS = [
    # (kinachoonyeshwa kwa mkulima, maneno ya kulinganisha na dalili za dataset)
    ("Majani yana rangi isiyo ya kawaida (njano, kahawia au mistari)", "majani yana mistari ya njano madoa rangi ya kahawia"),
    ("Majani yana mashimo au yameliwa", "majani yana mashimo makubwa yameliwa"),
    ("Mimea inanyauka au majani yanakauka", "majani hukauka mmea unanyauka"),
    ("Mimea imedumaa, haikui vizuri", "mmea unadumaa haukui"),
    ("Kuna wadudu au funza wanaoonekana kwenye mmea", "kuna wadudu funza kwenye mmea"),
    ("Shina au gunzi limeharibika au lina matundu", "shina lina matundu limeharibika gunzi"),
]
NUMBERS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣']


def is_vague(text):
    """Hakuna dalili yoyote halisi (sehemu ya mmea, rangi, mashimo, wadudu…)."""
    return not _SYMPTOM_RE.search((text or '').lower())


def intake_message(crop_name, again=False):
    head = ("Bado sijaelewa tatizo vizuri. Tafadhali " if again else
            "Pole sana. Ili nielewe tatizo vizuri *kabla ya kukushauri chochote*, ")
    lines = [head + f"niambie unachokiona kwenye {crop_name}. Chagua namba moja au zaidi:", '']
    lines += [f"{NUMBERS[i]} {label}" for i, (label, _) in enumerate(INTAKE_OPTIONS)]
    lines += ['', f"Pia, kama unajua: {crop_name.lower()} yana umri gani? (mf. wiki 6)",
              "_Mfano wa jibu: 2 na 5, wiki 6 — au eleza kwa maneno yako_"]
    return '\n'.join(lines)


NUMBER_WORDS = {'moja': 1, 'mbili': 2, 'tatu': 3, 'nne': 4, 'tano': 5, 'sita': 6, 'saba': 7, 'nane': 8,
                'tisa': 9, 'kumi': 10}


def parse_age_weeks(text):
    """'nilipanda wiki tatu zilizopita' → 3; 'miezi 2' → 8; hakuna → None."""
    return parse_intake(text)[1]


def parse_intake(text):
    """'2 na 5, wiki 6' → ([1, 4], 6). Namba 1–6 (si ile ya umri) ni chaguo."""
    low = (text or '').lower()
    weeks = None
    for word, num in NUMBER_WORDS.items():                  # "wiki tatu" → "wiki 3"
        low = re.sub(rf'\b(wiki|week|mwezi|miezi)\s+{word}\b', rf'\1 {num}', low)
    # "wiki 6" (namba BAADA ya neno) kwanza: "2 wiki 6" = chaguo 2, umri wiki 6
    for unit, mult in (('wiki|week', 1), ('mwezi|miezi', 4)):
        m_age = (re.search(rf'(?:{unit})\s*(\d{{1,2}})', low)
                 or re.search(rf'(\d{{1,2}})\s*(?:{unit})', low))
        if m_age:
            weeks = int(m_age.group(1)) * mult
            low = low[:m_age.start()] + ' ' + low[m_age.end():]
            break
    picks = []
    for n in re.findall(r'(?<![\d.])([1-6])(?![\d.])', low):
        if int(n) - 1 not in picks:
            picks.append(int(n) - 1)
    return picks, weeks


def _stage_from_weeks(weeks):
    if weeks is None:
        return None
    return 'seedling' if weeks <= 3 else 'vegetative' if weeks <= 10 else None
DISCLAIMER = "_Ushauri huu unatokana na taarifa za kitaalamu za Kilimoni AI; si mbadala wa afisa ugani._"

# ─────────────────────────── Misamiati ───────────────────────────

STOPWORDS = {
    'yangu', 'wangu', 'yako', 'yake', 'yana', 'ina', 'kwa', 'na', 'ya', 'wa',
    'la', 'za', 'kwenye', 'katika', 'sana', 'hii', 'hiyo', 'huu', 'zao',
    'mazao', 'shamba', 'nifanye', 'nini', 'naomba', 'msaada', 'tafadhali',
    'pia', 'lakini', 'kama', 'tu', 'hapa', 'sasa', 'kuna', 'je', 'au', 'ni',
    'cha', 'vya', 'mahindi', 'maize', 'the', 'and', 'with', 'mmea', 'mimea',
    'unaona', 'umeona', 'ndani', 'kuanzia', 'yanaweza', 'inaweza', 'vizuri',
    'mwenye', 'wako', 'kwenye',
}
# Dhana (concepts) za ishara kuu. Swali linahesabiwa kuwa limejibiwa na
# maelezo ya mkulima, au ni marudio ya swali lililoulizwa, TU kupitia dhana
# hizi — si kwa neno lolote linalofanana. Dalili za jumla (mashimo, mistari
# ya njano) hazimo kwa makusudi: ndizo zilizoleta visababishi, haziwezi pia
# kuthibitisha ishara kuu (ingekuwa kuhesabu ushahidi mmoja mara mbili).
CONCEPTS = {
    'frass': ('kinyesi', 'frass'),
    'larva': ('lava', 'funza', 'kiwavi', 'viwavi', 'buu', 'mabuu'),
    'grasshopper': ('panzi',),
    'swarm': ('makundi', 'kundi'),
    'dead_heart': ('dead heart',),
    'stem_tunnel': ('pasua', 'iliyochimbwa'),
    'mosaic': ('mosaic',),
    'vein_streak': ('mishipa',),
}
YES_WORDS = {'ndiyo', 'ndio', 'naam', 'yes', 'ee', 'eeh', 'nimeona', 'naona', 'ipo',
             'zipo', 'wapo', 'yupo', 'yapo', 'kuna', 'nimewaona', 'nimeiona', 'sawa'}
NO_WORDS = {'hapana', 'sijaona', 'hakuna', 'hamna', 'siyo', 'sio', 'no', 'sioni',
            'haipo', 'hazipo', 'hawapo', 'hayapo', 'la'}
UNKNOWN_PHRASES = ('sijui', 'sina uhakika', 'sielewi', 'sikumbuki', 'haijulikani')
CANCEL_WORDS = ('acha', 'ghairi', 'basi', 'sitaki', 'stop', 'swali jingine', 'swali lingine')
SPREAD_STEMS = ('inaenea', 'yanaenea', 'zinaenea', 'linaenea', 'kuenea', 'haraka', 'ghafla')

# Sehemu ya mmea (dataset kwa Kiingereza) → maneno ya mkulima
PLANT_PARTS = {
    'leaves': ('majani', 'jani'),
    'whorl': ('kamba', 'whorl', 'kitovu'),
    'stem': ('shina', 'bua'),
    'ear': ('gunzi', 'hindi', 'punje'),
    'tassel': ('ndevu', 'maua'),
    'roots': ('mizizi', 'mzizi'),
}
STAGES = {
    'seedling': ('kuota', 'kuchipua', 'miche', 'mchanga', 'michanga', 'chipukizi'),
    'vegetative': ('kukua', 'majani mengi', 'magoti', 'wiki'),
}
SEVERITY_ORDER = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}


def _words(text):
    return re.findall(r"[a-z0-9']+", (text or '').lower())


def _tokens(text):
    return {w for w in _words(text) if len(w) >= 4 and w not in STOPWORDS}


def _same(a, b):
    """Linganisha neno la Kiswahili kwa mzizi wa herufi 5 (mashimo ~ mashimoni)."""
    return a == b or (len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5])


def _overlap(farmer_tokens, phrase):
    """Rudisha (maneno yaliyolingana, uwiano) kati ya maneno ya mkulima na kifungu."""
    p = _tokens(phrase)
    if not p:
        return [], 0.0
    hit = [w for w in p if any(_same(w, f) for f in farmer_tokens)]
    return hit, len(hit) / len(p)


def _clauses(text):
    return [c.strip() for c in re.split(r'[;\.\n]', text or '') if len(c.strip()) > 3]


def _norm_q(text):
    return ' '.join(_words(text))


def _label_value(label):
    label = (label or '').strip().lower()
    for name in ('high', 'medium', 'low'):
        if label.startswith(name):
            return get_setting(f'label_{name}')
    return None


def _range_value(lo, hi):
    if lo is None and hi is None:
        return None
    lo = hi if lo is None else lo
    hi = lo if hi is None else hi
    strategy = get_setting('range_strategy', cast=None)
    if strategy == 'min':
        return lo if abs(lo) <= abs(hi) else hi
    if strategy == 'max':
        return lo if abs(lo) >= abs(hi) else hi
    return round((lo + hi) / 2, 4)


def _cap(score):
    return max(0.0, min(get_setting('confidence_cap'), round(score, 4)))


def _cause(cid):
    if not cid:
        return None
    model = m.Disease if cid.upper().startswith('DIS') else m.Pest
    return model.objects.filter(source_id=cid, is_active=True).first()


def _cause_name(cause):
    if cause is None:
        return '?'
    if (cause.name_sw and cause.name_en and cause.name_en.lower() not in cause.name_sw.lower()
            and '(' not in cause.name_sw):
        return f"{cause.name_sw} ({cause.name_en})"
    return cause.name_sw or cause.name_en


def _rule_for(crop):
    """Kuna data ya rules kwa zao hili?"""
    return (m.Symptom.objects.filter(crop=crop, is_active=True).exists()
            or m.DiagnosisRule.objects.filter(crop=crop, is_active=True).exists())


def supported_crop_names():
    from crops.models import Crop
    ids = set(m.Symptom.objects.filter(is_active=True).values_list('crop_id', flat=True))
    ids |= set(m.DiagnosisRule.objects.filter(is_active=True).values_list('crop_id', flat=True))
    return [c.crop_name_sw for c in Crop.objects.filter(id__in=[i for i in ids if i])]


# ─────────────────────────── Hali (state) ───────────────────────────

def new_state():
    return {
        'active': True, 'phase': 'crop', 'crop_id': None, 'symptom_text': '',
        'growth_stage': None, 'candidates': {}, 'asked': [], 'pending': None,
        'evidence': [], 'extent': None, 'severity': None, 'spreading': False,
        'crop_attempts': 0, 'started': time.time(), 'updated': time.time(),
    }


def get_state(session):
    st = (session or {}).get(STATE_KEY)
    if not st or not st.get('active'):
        return None
    if time.time() - float(st.get('updated', 0)) > TIMEOUT_SECONDS:
        return None
    return st


def is_cancel(text):
    t = (text or '').strip().lower()
    return any(t == w or t.startswith(w + ' ') for w in CANCEL_WORDS)


def _near(word, target):
    """Kosa moja la uchapaji (herufi moja imebadilika/imeongezwa/imepungua): 'hqpana' ≈ 'hapana'."""
    if word == target:
        return True
    if abs(len(word) - len(target)) > 1:
        return False
    i = j = edits = 0
    while i < len(word) and j < len(target):
        if word[i] == target[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(word) > len(target):
            i += 1
        elif len(word) < len(target):
            j += 1
        else:
            i += 1
            j += 1
    return edits + (len(word) - i) + (len(target) - j) <= 1


# Majibu yanayotambuliwa hata yakiwa na kosa moja la uchapaji ("Hqpana", "ndoyo", "sijuo")
TYPO_TARGETS = (('hapana', 'no'), ('sijaona', 'no'), ('hakuna', 'no'), ('ndiyo', 'yes'),
                ('nimeona', 'yes'), ('sijui', 'unknown'))


def parse_answer(text):
    low = (text or '').lower()
    if any(p in low for p in UNKNOWN_PHRASES):
        return 'unknown'
    words = set(_words(low))
    if words & NO_WORDS:
        return 'no'
    if words & YES_WORDS:
        return 'yes'
    if len(words) <= 3:
        for w in words:
            if len(w) >= 5:
                for target, answer in TYPO_TARGETS:
                    if _near(w, target):
                        return answer
    return 'unknown'


def parse_extent(text):
    """Rudisha asilimia ya shamba iliyoathirika, au None."""
    low = (text or '').lower()
    mt = re.search(r'(\d{1,3})\s*(%|asilimia)', low) or re.search(r'asilimia\s*(\d{1,3})', low)
    if mt:
        return min(100, int(mt.group(1)))
    for words, pct in ((('shamba lote', 'lote', 'kote'), 100),
                       (('sehemu kubwa', 'mimea mingi', 'mingi'), 60),
                       (('robo tatu',), 75), (('nusu',), 50), (('robo',), 25),
                       (('michache', 'chache', 'kidogo', 'baadhi', 'mmoja', 'miwili'), 5)):
        if any(w in low for w in words):
            return pct
    return None


def severity_from(extent, spreading):
    if spreading:
        return 'high'
    if extent is None:
        return None
    if extent < get_setting('severity_low_max'):
        return 'low'
    if extent <= get_setting('severity_medium_max'):
        return 'medium'
    return 'high'


def _detect_stage(text):
    low = (text or '').lower()
    for stage, words in STAGES.items():
        if any(w in low for w in words):
            return stage
    return None


def _mentioned_parts(text):
    toks = set(_words(text))
    return {part for part, words in PLANT_PARTS.items()
            if any(any(_same(w, t) for t in toks) for w in words)}


# ─────────────────────────── 1–2. Visababishi ───────────────────────────

def match_candidates(crop, text, stage=None):
    """
    Rudisha (candidates, matches). candidates = {cause_id: {...}}.
    Kila kisababishi kinapata score ya mwanzo kutoka chanzo kimoja tu.
    """
    farmer = _tokens(text)
    min_ratio = get_setting('symptom_match_ratio')
    found = {}   # cid -> list ya (priority, score, source_id, matched_words)

    def add(cid, priority, score, source, words):
        if cid and score is not None:
            found.setdefault(cid, []).append((priority, score, source, words))

    def matches(phrase):
        hit, ratio = _overlap(farmer, phrase)
        return hit if ratio >= min_ratio and len(hit) >= min(2, len(_tokens(phrase))) else None

    # 007D: Diagnosis Decision Rules
    for r in m.DiagnosisRule.objects.filter(crop=crop, is_active=True):
        if stage and r.growth_stage and r.growth_stage.lower() != stage:
            continue
        hit = matches(r.normalized_symptom or r.input_symptom_sw)
        if hit:
            add(r.cause_id, 1, r.base_confidence, r.source_id, hit)

    # 007A/007B: AI Decision Rules za symptom match (si za differentiator)
    for r in m.DecisionRule.objects.filter(is_active=True).select_related('pest', 'disease'):
        cause = r.pest or r.disease
        if cause is None or (cause.crop_id and cause.crop_id != crop.id):
            continue
        rtype = r.rule_type.lower()
        if 'differentiator' in rtype or 'differential' in rtype:
            continue
        for clause in _clauses(r.input_symptom_sw):
            hit = matches(clause)
            if hit:
                add(cause.source_id, 2, r.confidence, r.source_id, hit)
                break

    # Master (007A/007B): Visible_Symptoms + Farmer_Question_Examples,
    # score kutoka Confidence_Rules ("Medium if leaf holes only")
    for model in (m.Pest, m.Disease):
        for cause in model.objects.filter(is_active=True):
            if cause.crop_id and cause.crop_id != crop.id:
                continue
            phrases = _clauses(cause.visible_symptoms_sw) + _clauses(cause.farmer_question_examples)
            hit = next((h for h in (matches(p) for p in phrases) if h), None)
            if hit:
                add(cause.source_id, 3, _base_label_score(cause), f"{cause.source_id}:Confidence_Rules", hit)

    # 007C: Symptom_Master → Likely_Pest_IDs (lebo ya AI_Confidence_Default)
    symptoms = []
    for s in m.Symptom.objects.filter(crop=crop, is_active=True).prefetch_related('likely_pests'):
        if stage and s.growth_stage and s.growth_stage.lower() != stage:
            continue
        hit = matches(s.farmer_symptom_sw) or matches(s.normalized_symptom_sw)
        if hit:
            symptoms.append(s.source_id)
            for p in s.likely_pests.all():
                add(p.source_id, 4, _label_value(s.confidence_default), s.source_id, hit)
            for mp in s.mappings.filter(is_active=True):
                add(mp.target_id, 4, _label_value(s.confidence_default), mp.source_id, hit)

    preferred = get_setting('initial_source', cast=None)
    order = {'007D': (1, 2, 3, 4), '007A': (2, 1, 3, 4)}.get(preferred, (1, 2, 3, 4))
    parts = _mentioned_parts(text)
    conf001 = m.ConfidenceRule.objects.filter(condition_code='symptom_match', is_active=True).first()

    candidates = {}
    for cid, options in found.items():
        cause = _cause(cid)
        if cause is None:
            continue
        options.sort(key=lambda o: order.index(o[0]))
        priority, score, source, words = options[0]
        rules = [source]
        # CONF001 tu kama score ilitoka kwenye lebo (vyanzo 3–4), si kanuni ya namba
        if conf001 and priority in (3, 4) and _part_matches(cause, parts):
            score += conf001.adjustment
            rules.append(conf001.source_id)
        candidates[cid] = {
            'score': _cap(score), 'initial': _cap(score), 'kind': cause._meta.model_name,
            'confirmed': False, 'rejected': False, 'rules': rules, 'matched': sorted(set(words)),
        }
    return candidates, symptoms


def _base_label_score(cause):
    """Confidence_Rules: kifungu chenye 'only' ndicho cha dalili ya jumla."""
    text = (cause.raw or {}).get('Confidence_Rules') or (cause.raw or {}).get('Confidence_Rule') or ''
    for clause in text.split(';'):
        if 'only' in clause.lower():
            return _label_value(clause.strip().split(' ')[0])
    return get_setting('label_low')


def _part_matches(cause, parts):
    attacked = (getattr(cause, 'plant_part_attacked', '') or getattr(cause, 'plant_part_affected', '')).lower()
    return any(p in attacked for p in parts)


# ─────────────────────────── 3. Maswali ───────────────────────────

def build_questions(state):
    """
    Rudisha {key: spec}. spec = {text, effects: {cid: [yes, no]}, key_for: [cid],
    sources: [ids], priority}. Swali lenye maandishi sawa kutoka vyanzo tofauti
    linaunganishwa kuwa moja (ushahidi mmoja).
    """
    cands = state['candidates']
    qs = {}

    def put(text, cid, yes, no, source, priority, key=False):
        if not text or cid not in cands:
            return
        k = _norm_q(text)
        spec = qs.setdefault(k, {'text': text.strip(), 'effects': {}, 'key_for': [],
                                 'sources': [], 'priority': priority})
        spec['priority'] = min(spec['priority'], priority)
        if source not in spec['sources']:
            spec['sources'].append(source)
        # Uzito wa kwanza (kwa kipaumbele cha chanzo) unabaki — hakuna kujumlisha
        if cid not in spec['effects']:
            spec['effects'][cid] = [yes, no]
        if key and cid not in spec['key_for']:
            spec['key_for'].append(cid)

    no_default = get_setting('key_question_no_adjustment')
    conf002 = m.ConfidenceRule.objects.filter(condition_code='key_differentiator', is_active=True).first()
    key_yes = conf002.adjustment if conf002 else None

    # 007D: swali la uthibitisho la kila Diagnosis Rule + Follow-up nodes + Differential
    rules = {r.cause_id: r for r in m.DiagnosisRule.objects.filter(is_active=True, cause_id__in=list(cands))}
    for cid, r in rules.items():
        for node in m.FollowUpNode.objects.filter(is_active=True, rule_group=r.condition_code):
            is_key = _norm_q(node.question_sw) == _norm_q(r.follow_up_question_sw)
            put(node.question_sw, cid, node.adjustment_yes, node.adjustment_no,
                node.source_id, 1 if is_key else 4, key=is_key)
    for dd in m.DifferentialDiagnosis.objects.filter(is_active=True, primary_cause_id__in=list(cands)):
        put(dd.question_sw, dd.primary_cause_id, dd.if_yes_adjustment, dd.if_no_adjustment,
            dd.source_id, 3)

    # 007C: Follow-up questions za dalili zilizolingana
    for fq in m.FollowupQuestion.objects.filter(is_active=True, symptom__source_id__in=state.get('symptoms', [])):
        yes = _range_value(fq.if_yes_min, fq.if_yes_max)
        no = _range_value(fq.if_no_min, fq.if_no_max)
        key_pests = set(m.DecisionRule.objects.filter(followup=fq, is_active=True)
                        .filter(rule_type__icontains='differentiator')
                        .values_list('pest__source_id', flat=True)) if fq.is_key_differentiator else set()
        for p in fq.yes_routes_to.all():
            put(fq.question_sw, p.source_id, yes, no, fq.source_id, 2, key=p.source_id in key_pests)

    # 007A/007B master: Follow_Up_Question ya kila kisababishi = ishara yake kuu
    for cid in cands:
        cause = _cause(cid)
        if cause and cause.follow_up_question_sw:
            put(cause.follow_up_question_sw, cid, key_yes, no_default,
                f"{cid}:Follow_Up_Question", 2, key=True)
    return qs


def _ranked(cands):
    return sorted(cands.items(), key=lambda kv: (-kv[1]['score'], kv[0]))


def choose_question(state, qs):
    """Swali linalofuata: ishara kuu ya anayeongoza, kisha ya wa pili, n.k."""
    asked = set(state['asked'])
    open_qs = {k: v for k, v in qs.items() if k not in asked and not _redundant(state, v)}
    if not open_qs:
        return None
    ranked = [cid for cid, c in _ranked(state['candidates']) if not c['rejected']]
    for cid in ranked:
        if state['candidates'][cid]['confirmed']:
            continue
        keys = [k for k, v in open_qs.items() if cid in v['key_for']]
        if keys:
            return min(keys, key=lambda k: (open_qs[k]['priority'], k))
        if cid == ranked[0]:
            # Hakuna swali la ishara kuu kwa anayeongoza — tumia swali lolote linalomhusu
            keys = [k for k, v in open_qs.items() if cid in v['effects']]
            if keys:
                return min(keys, key=lambda k: (open_qs[k]['priority'], k))
    return None


def concepts(text):
    low = ' '.join(_words(text))
    return {name for name, terms in CONCEPTS.items()
            if any(re.search(r'\b' + re.escape(t), low) for t in terms)}


def preanswered(state, qs, text):
    """
    Maswali ambayo mkulima ameshayajibu kwenye ujumbe wake (kigezo 1:
    usiulize kilichokwisha jibiwa). Dhana ya swali ikitajwa → Ndiyo;
    ikitanguliwa na 'hakuna/sijaona' → Hapana.
    """
    words = _words(text)
    out, used = [], set()
    for k, spec in sorted(qs.items(), key=lambda kv: (kv[1]['priority'], kv[0])):
        qc = concepts(spec['text'])
        if k in state['asked'] or not qc or qc & used:
            continue
        for i, w in enumerate(words):
            if concepts(w) & qc:
                prev = words[max(0, i - 2):i]
                out.append((k, 'no' if set(prev) & NO_WORDS else 'yes'))
                used |= qc
                break
    return out


def _redundant(state, spec):
    """Swali linalouliza dhana iliyokwisha ulizwa ni marudio (kigezo 1)."""
    asked = set()
    for ev in state['evidence']:
        asked |= concepts(ev['question'])
    return bool(concepts(spec['text']) & asked)


def interpret(state, question, text):
    """
    Jibu la mkulima → yes/no/unknown/clarify. Majibu mafupi ("ndiyo",
    "sijui") yanasomwa kwa kanuni; sentensi ndefu zinaelezwa na AI kwanza
    ("nimeona vitu vyeusi kama unga ndani"), kanuni zikiwa akiba.
    """
    rule = parse_answer(text)
    if len(_words(text)) <= 2:
        return rule
    ai = ai_layer.interpret_answer(question, text, state)
    return ai or rule


def clarify_message(question):
    return (
        "Samahani kama swali halikuwa wazi. 🙏\n\n"
        f"Ninachouliza ni: {_plain_q(question)}\n\n"
        "Angalia mmea wako kwa makini, kisha nijibu: *ndiyo* kama umeona, "
        "*hapana* kama hujaona, au *sijui* kama huna uhakika."
    )


# ─────────────────────────── 4. Ushahidi ───────────────────────────

def apply_answer(state, qs, key, answer, via='question'):
    spec = qs.get(key)
    state['asked'].append(key)
    ev = {'question': spec['text'] if spec else key, 'answer': answer, 'via': via,
          'sources': spec['sources'] if spec else [], 'deltas': {}}
    if spec and answer in ('yes', 'no'):
        conf002 = m.ConfidenceRule.objects.filter(condition_code='key_differentiator', is_active=True).first()
        for cid, (yes, no) in spec['effects'].items():
            c = state['candidates'].get(cid)
            if c is None:
                continue
            is_key = cid in spec['key_for']
            if answer == 'yes':
                delta = yes or 0.0
                if is_key and conf002:
                    # Ushahidi mmoja: kubwa kati ya uzito wa swali na CONF002
                    delta = max(delta, conf002.adjustment)
                    if conf002.source_id not in c['rules']:
                        c['rules'].append(conf002.source_id)
                if is_key:
                    c['confirmed'] = True
            else:
                delta = no or 0.0
                if is_key:
                    c['rejected'] = True
            c['score'] = _cap(c['score'] + delta)
            for s in spec['sources']:
                if s not in c['rules']:
                    c['rules'].append(s)
            ev['deltas'][cid] = round(delta, 4)
    state['evidence'].append(ev)
    return ev


def decide(state):
    """'diagnosed' | 'continue' | 'uncertain'."""
    ranked = [(cid, c) for cid, c in _ranked(state['candidates']) if not c['rejected']]
    if not ranked:
        return 'uncertain', None
    top_id, top = ranked[0]
    second = ranked[1][1]['score'] if len(ranked) > 1 else 0.0
    if (top['confirmed'] and top['score'] >= get_setting('diagnosis_threshold')
            and top['score'] - second >= get_setting('min_lead_margin')):
        return 'diagnosed', top_id
    return 'continue', top_id


# ─────────────────────────── 6. Safety gate ───────────────────────────

def _condition_holds(condition, facts):
    """'Diagnosis_Category=Disease; Severity=Critical; Confidence>=0.75'."""
    parts = [p.strip() for p in re.split(r'[;]|\bAND\b', condition or '') if p.strip()]
    parsed = 0
    for p in parts:
        mt = re.match(r'(\w+)\s*(>=|<=|=|>|<)\s*([\w\.]+)$', p)
        if not mt:
            continue
        parsed += 1
        key, op, val = mt.groups()
        have = facts.get(key.lower())
        if have is None:
            return False
        try:
            a, b = float(have), float(val)
        except (TypeError, ValueError):
            a, b = SEVERITY_ORDER.get(str(have).lower(), str(have).lower()), \
                SEVERITY_ORDER.get(val.lower(), val.lower())
        ok = {'=': a == b, '>=': a >= b, '<=': a <= b, '>': a > b, '<': a < b}[op] \
            if type(a) is type(b) else False
        if not ok:
            return False
    return parsed > 0


def safety_gate(state, cid):
    cause = _cause(cid)
    c = state['candidates'][cid]
    category = 'Disease' if c['kind'] == 'disease' else 'Pest'
    severity = state.get('severity')
    facts = {'diagnosis_category': category, 'confidence': c['score'],
             'severity': (cause.severity_level if c['kind'] == 'disease' else severity) or ''}
    gate = {'chemical_allowed': False, 'recommendation': None, 'escalations': [], 'blocked_by': None}

    for esc in m.EscalationRule.objects.filter(is_active=True):
        if _condition_holds(esc.condition, facts):
            gate['escalations'].append(esc.source_id)
            if 'chemical' in esc.ai_action.lower():
                gate['blocked_by'] = esc.source_id
        elif state.get('spreading') and 'spread' in esc.trigger.lower():
            gate['escalations'].append(esc.source_id)

    min_sev = SEVERITY_ORDER[get_setting('rec_min_severity', cast=None)]
    for rec in m.RecommendationRule.objects.filter(is_active=True, diagnosis_category__iexact=category):
        if c['score'] >= rec.min_confidence and SEVERITY_ORDER.get(severity or '', 0) >= min_sev:
            gate['recommendation'] = rec.source_id
            break
    gate['chemical_allowed'] = bool(gate['recommendation'] and not gate['blocked_by'])
    return gate


# ─────────────────────────── Majibu ───────────────────────────

def _band(score):
    band = m.ConfidenceBand.objects.filter(min_score__lte=score + 1e-9, max_score__gte=score - 1e-9,
                                           is_active=True).first()
    if band:
        return band.source_id, band.farmer_message_sw
    if score >= get_setting('label_medium'):
        return 'Medium', ''
    return 'Low', ''


ACKS = {'yes': 'Sawa, nimeelewa. 👍', 'no': 'Sawa, asante.', 'unknown': 'Hakuna shida.'}


def _ack(state):
    """Kitikio kifupi cha jibu la mwisho la mkulima — mazungumzo yasiwe ya kiroboti."""
    asked = [ev for ev in state['evidence'] if ev['via'] == 'question']
    return (ACKS.get(asked[-1]['answer'], '') + '\n\n') if asked else ''


REASON_STOP = {'ya', 'na', 'wa', 'za', 'la', 'kwa', 'kwenye', 'yangu', 'mmea', 'mimea', 'zao', 'yana', 'ina',
               'kuna', 'sana', 'kama', 'au', 'ni', 'mahindi', 'majani', 'jani'}
# Mipaka ya data: MHD-007 ina wadudu na magonjwa tu. Visababishi vingine (upungufu wa
# virutubisho, ukame/maji, udongo) havijawekwa — tunasema wazi badala ya kuvibuni.
COVERAGE_NOTE = ("_Kumbuka: taarifa zangu za uchunguzi kwa sasa zinahusu *wadudu na magonjwa* tu. "
                 "Upungufu wa virutubisho (mf. mbolea), ukame au hali ya udongo bado havimo kwenye "
                 "data yangu — kama unashuku hivyo, afisa ugani anaweza kukagua._")


def _reason_words(c):
    return [w for w in c.get('matched', []) if w not in REASON_STOP and len(w) > 2][:4]


def question_message(state, spec, number):
    ranked = [(cid, c) for cid, c in _ranked(state['candidates']) if not c['rejected']]
    intro = ''
    if number == 1 and ranked:
        lines = ["Kutokana na dalili ulizotaja, visababishi vinavyowezekana (kuanzia kinacholingana zaidi):"
                 if len(ranked) > 1 else "Kutokana na dalili ulizotaja, kisababishi kinachowezekana ni:"]
        for cid, c in ranked[:4]:
            why = _reason_words(c)
            lines.append(f"• *{_cause_name(_cause(cid))}*" + (f" — umetaja: {', '.join(why)}" if why else ''))
        lines += ['', COVERAGE_NOTE, '',
                  "Nitakuuliza maswali mafupi ili kuvitofautisha. 🔍" if len(ranked) > 1 else
                  "Nitakuuliza maswali mafupi ili kuthibitisha. 🔍", '', '']
        intro = '\n'.join(lines)
    return f"{_ack(state) if number > 1 else ''}{intro}*Swali {number}:* {_plain_q(spec['text'])}\n{ANSWER_HINT}"


def _explanation(cid, kind):
    q = m.ExplainabilityRecord.objects.filter(is_active=True)
    rec = (q.filter(level='pest', pest__source_id=cid, explanation_type__icontains='diagnosis').first()
           if kind == 'pest' else
           q.filter(level='disease', disease__source_id=cid, explanation_type__icontains='positive').first())
    return rec


def _plain_q(text):
    """Swali kwa lugha rahisi (kamusi tu — swali halitupwi)."""
    return plain._apply_terms(text or '', plain._terms())


def _farmer(state, text, terms=None):
    """Safisha maandishi ya dataset; yaliyoondolewa yanaandikwa kwenye state (trace)."""
    out, dropped = plain.clean(text, terms)
    for sentence, why in dropped:
        state.setdefault('dropped_text', []).append({'text': sentence, 'reason': why})
    return out


def _rules_used(state, cid, gate):
    c = state['candidates'][cid]
    return list(dict.fromkeys(c['rules'] + [r for r in (gate['recommendation'],) if r]
                              + gate['escalations']))


SEVERITY_SW = {'low': 'ndogo', 'medium': 'ya wastani', 'high': 'kubwa', 'critical': 'hatari'}


def _summary_facts(state, cid, crop_name, gate, band):
    """Ukweli ULIOKWISHA amuliwa na kanuni — AI inaueleza tu, haiongezi."""
    cause = _cause(cid)
    c = state['candidates'][cid]
    return {
        'zao': crop_name,
        'tatizo': cause.name_sw if cause else '',
        'tatizo_en': getattr(cause, 'name_en', '') or '',
        'aina': 'ugonjwa' if c['kind'] == 'disease' else 'mdudu',
        'kiwango_cha_uhakika': plain.band_sw(band),
        'dalili_alizotaja_mkulima': state['symptom_text'].strip(),
        'alichothibitisha': [plain.as_statement(_plain_q(ev['question'])) for ev in state['evidence']
                             if ev['answer'] == 'yes' and cid in ev['deltas']],
        'ukubwa_wa_tatizo': SEVERITY_SW.get(state.get('severity') or '', 'haijulikani'),
        'linaenea_haraka': bool(state.get('spreading')),
        'ni_hatari_wasiliana_na_afisa_ugani_haraka': bool(gate['escalations']),
        'kemikali_inaruhusiwa': gate['chemical_allowed'],
    }


def diagnosis_message(state, cid, crop_name, gate):
    cause = _cause(cid)
    c = state['candidates'][cid]
    terms = plain._terms()
    band, band_msg = _band(c['score'])
    lines = [f"🔍 *Matokeo ya uchunguzi — {crop_name.capitalize()}*", '']
    human = ai_layer.summary(_summary_facts(state, cid, crop_name, gate, band), state)
    if human:
        lines += [human, '']
    elif band_msg:
        lines += [_farmer(state, band_msg, terms), '']
    lines.append(f"*Tatizo linalowezekana zaidi:* {_cause_name(cause)}")
    lines.append(f"*Kiwango cha uhakika:* {round(c['score'] * 100)}% ({plain.band_sw(band)})")
    lines += ['', '*Kwa nini:*']
    # Kwa chaguo za intake tunaonyesha alichochagua mkulima (si maneno ya kulinganisha)
    shown = '; '.join(state.get('intake_picks') or []) or state['symptom_text'].strip().rstrip('.')
    lines.append(f"• Dalili ulizotaja: {shown}")
    if state.get('crop_age_weeks'):
        lines.append(f"• Umri wa mimea: wiki {state['crop_age_weeks']}")
    for ev in state['evidence']:
        if ev['answer'] == 'yes' and cid in ev['deltas']:
            lines.append(f"• Ulijibu *ndiyo*: {plain.as_statement(_plain_q(ev['question']))}")
    rec = _explanation(cid, c['kind'])
    if rec and rec.reason_sw:
        reason = _farmer(state, rec.reason_sw, terms)
        if reason:
            lines.append(f"• {reason}")

    others = [(o, oc) for o, oc in _ranked(state['candidates']) if o != cid]
    if others:
        lines += ['', '*Kwa nini si vingine:*']
        for o, oc in others[:3]:
            name = _cause_name(_cause(o))
            denied = [ev['question'] for ev in state['evidence']
                      if ev['answer'] == 'no' and o in ev['deltas']]
            if denied:
                lines.append(f"• {name} — ulijibu *hapana*: {plain.as_statement(_plain_q(denied[0]))}")
            else:
                lines.append(f"• {name} — dalili yake kuu haijathibitishwa "
                             f"(uhakika {round(oc['score'] * 100)}%)")

    lines += ['', '*Hatua za kuchukua:*'] + action_lines(state, cid, gate)
    for esc_id in gate['escalations']:
        esc = m.EscalationRule.objects.filter(source_id=esc_id).first()
        if esc:
            msg = _farmer(state, esc.farmer_message_sw, terms)
            if msg:
                lines += ['', f"⚠️ {msg}"]
    if gate['blocked_by'] or c['kind'] == 'disease':
        lines += ['', REFER_EXTENSION]

    lines.append('')
    if get_setting('show_rules_to_farmer') >= 1:
        lines += [f"_Kanuni zilizotumika: {', '.join(_rules_used(state, cid, gate))}_",
                  "_Chanzo: dataset ya Kilimoni (MHD-007)._"]
    lines.append(DISCLAIMER)
    # Ukaguzi wa mwisho: kemikali isiporuhusiwa, sentensi yoyote ya dataset
    # inayogusa dawa (mf. "viuatilifu vya asili") inaondolewa; ikiruhusiwa,
    # tahadhari ya kibandiko inahakikishwa.
    from bot.diagnostic import validate_output
    text, _ = validate_output('\n'.join(lines), crop_name, gate['chemical_allowed'])
    return text


def action_lines(state, cid, gate):
    cause = _cause(cid)
    out = []
    symptom = m.Symptom.objects.filter(source_id__in=state.get('symptoms', [])).first()
    terms = plain._terms()

    def add(val):
        val = _farmer(state, val, terms) if val else ''
        if val and f"• {val}" not in out:
            out.append(f"• {val}")

    if state['candidates'][cid]['kind'] == 'disease':
        for field in ('prevention_sw', 'sanitation_control_sw', 'cultural_control_sw'):
            add(getattr(cause, field))
        add(cause.chemical_control_safety_text)
        return out

    treatment = m.Treatment.objects.filter(pest=cause, is_active=True).first()
    if treatment:
        for field in ('immediate_action_sw', 'cultural_control', 'mechanical_control', 'biological_control'):
            add(getattr(treatment, field))
    else:
        add(cause.ai_summary_sw)
        if symptom:
            add(symptom.immediate_action_sw)
    if gate['chemical_allowed']:
        if treatment:
            add(treatment.chemical_control_guidance)
        for safe in m.SafetyRule.objects.filter(is_active=True):
            add(safe.farmer_message_sw)
        if get_setting('allow_product_names') >= 1 and treatment:
            add(treatment.active_ingredient_examples)
    else:
        out.append(NO_CHEMICAL_YET)
    return out


def uncertain_message(state, crop_name):
    err = m.ErrorHandlingRule.objects.filter(error_code='LOW_CONFIDENCE', is_active=True).first()
    lines = [f"🔍 *Uchunguzi — {crop_name.capitalize()}*", '']
    lines.append(_farmer(state, err.user_message_sw) if err else "Sina uhakika wa kutosha.")
    lines.append("Siwezi kukupa utambuzi wa uhakika kwa taarifa zilizopo.")
    ranked = [(cid, c) for cid, c in _ranked(state['candidates']) if not c['rejected']]
    if ranked:
        # Bila asilimia: "90%" kando ya "sina uhakika" kingemchanganya mkulima.
        # Score ziko kwenye trace kwa ajili ya admin.
        lines += ['', '*Visababishi vinavyowezekana (havijathibitishwa):*']
        for cid, c in ranked[:3]:
            lines.append(f"• {_cause_name(_cause(cid))}")
    lines += ['', '*Hatua salama za sasa:*', SAFE_FIRST_STEPS, '', REFER_EXTENSION, '', DISCLAIMER]
    return '\n'.join(lines)


def no_match_message(crop_name, crop=None):
    """Dalili ZIMEELEZWA lakini hazilingani na kanuni — pengo la ujuzi, si la taarifa."""
    known = ''
    if crop is not None:
        names = [c.name_sw for c in list(m.Pest.objects.filter(crop=crop, is_active=True))
                 + list(m.Disease.objects.filter(crop=crop, is_active=True)) if c.name_sw]
        if names:
            known = ("\n\nMatatizo ya " + crop_name + " ninayoweza kuchunguza kwa sasa: "
                     + ', '.join(names[:8]) + '.')
    return (
        f"Asante kwa maelezo. Nimeelewa dalili ulizotaja, lakini hazilingani na matatizo ya *{crop_name}* "
        "yaliyo kwenye taarifa zangu za kitaalamu zilizothibitishwa — kwa hiyo sitabuni utambuzi. 🌱"
        + known + "\n\n*Hatua salama za sasa:*\n" + SAFE_FIRST_STEPS + "\n\n" + REFER_EXTENSION
    )


def insufficient_message(crop_name):
    """Mkulima hakuweza kueleza dalili hata baada ya kuulizwa — taarifa hazitoshi, si pengo la ujuzi."""
    return (
        f"Sawa. Bila kujua dalili za *{crop_name}* siwezi kukisia tatizo — na sitabuni. 🌱\n\n"
        "Ukiweza, kagua mimea kwa makini (majani, shina, mizizi) kisha niambie unachokiona; "
        "nitaendelea kukusaidia.\n\n*Hatua salama za sasa:*\n" + SAFE_FIRST_STEPS + "\n\n" + REFER_EXTENSION
    )


# ─────────────────────────── Mazungumzo ───────────────────────────

def step(state, text, crop=None):
    """
    Endeleza uchunguzi kwa ujumbe mmoja. Rudisha (jibu, trace, imekwisha).
    `crop` ni zao lililotambuliwa kwenye ujumbe huu (kama lipo).
    """
    from crops.models import Crop
    state['updated'] = time.time()
    if any(s in (text or '').lower() for s in SPREAD_STEMS):
        state['spreading'] = True
    trace = {'mode': 'rules_engine', 'phase_in': state['phase']}

    if state['phase'] == 'crop':
        if crop:
            state['crop_id'] = crop.id
            state['phase'] = 'symptoms'
        else:
            state['crop_attempts'] += 1
            return None, trace, False          # bot inashughulikia zao lisilojulikana

    crop = Crop.objects.filter(id=state['crop_id']).first()
    crop_name = crop.crop_name_sw if crop else 'zao lako'

    if state['phase'] == 'symptoms':
        # Mkulima alieleza dalili KABLA ya kutaja zao ("majani yamekuwa ya kahawia" → "zao gani?"
        # → "Mahindi"): tumia maelezo hayo badala ya kumuuliza dalili tena (kigezo 1).
        early = state.pop('early_symptoms', '')
        if not state['symptom_text'] and early and len(_tokens(early)) >= 2:
            state['symptom_text'] = early
        if not state['symptom_text']:
            if len(_tokens(text)) >= 2:
                state['symptom_text'] = text
            elif state.get('symptoms_asked'):
                state['symptom_text'] = text
        if not state['symptom_text']:
            state['symptoms_asked'] = True
            return ASK_SYMPTOMS.format(crop=crop_name), {**trace, 'asked': 'symptoms'}, False
        # "Mimea haionekani vizuri" — hakuna dalili halisi: uliza (intake), usihitimishe.
        if is_vague(state['symptom_text']) and not state.get('intake_done'):
            state['phase'] = 'intake'
            state['intake_tries'] = 0
            state['vague_text'] = state['symptom_text']
            state['symptom_text'] = ''
            return intake_message(crop_name), {**trace, 'asked': 'intake', 'decision': 'need_symptoms'}, False

    if state['phase'] == 'intake':
        picks, weeks = parse_intake(text)
        if weeks is not None:
            state['crop_age_weeks'] = weeks
        described = text if not is_vague(text) else ''
        if picks or described:
            parts = [INTAKE_OPTIONS[i][1] for i in picks]
            if described:
                parts.append(described)
            state['symptom_text'] = '. '.join(parts)
            state['intake_picks'] = [INTAKE_OPTIONS[i][0] for i in picks]
            state['intake_done'] = True
            state['phase'] = 'symptoms'
        else:
            state['intake_tries'] = state.get('intake_tries', 0) + 1
            if state['intake_tries'] >= 2:
                state['active'] = False
                return insufficient_message(crop_name), {**trace, 'decision': 'insufficient_info'}, True
            return intake_message(crop_name, again=True), {**trace, 'asked': 'intake'}, False

    if state['phase'] == 'symptoms':
        if not _rule_for(crop):
            state['active'] = False
            names = ', '.join(supported_crop_names()) or '—'
            return (f"Samahani, kwa sasa uchunguzi wa matatizo kwa kanuni unapatikana kwa: "
                    f"*{names}* tu. Sina kanuni za *{crop_name}* bado, kwa hiyo sitabuni ushauri.\n\n"
                    + REFER_EXTENSION), {**trace, 'decision': 'crop_without_rules'}, True
        # AI (lugha): maelezo ya mkulima → dalili za orodha ya dataset.
        # Kanuni ndizo zinazoamua; AI inaongeza tu maneno ya dataset
        # yaliyothibitishwa kuwa kwenye orodha funge.
        match_text = state['symptom_text']
        understood = ai_layer.understand_symptoms(crop, state['symptom_text'], state)
        if understood:
            if understood['phrases']:
                match_text += '. ' + '. '.join(understood['phrases'])
            if understood['extent_pct'] is not None:
                state['extent'] = understood['extent_pct']
            if understood['spreading']:
                state['spreading'] = True
            trace['ai_symptoms'] = understood['phrases']
        if state.get('crop_age_weeks') is None:
            state['crop_age_weeks'] = parse_age_weeks(state['symptom_text'])
        state['growth_stage'] = (_stage_from_weeks(state.get('crop_age_weeks')) or _detect_stage(state['symptom_text'])
                                 or (understood or {}).get('growth_stage'))
        cands, symptoms = match_candidates(crop, match_text, state['growth_stage'])
        if not cands and state['growth_stage']:
            cands, symptoms = match_candidates(crop, match_text)
        state['candidates'], state['symptoms'] = cands, symptoms
        trace['initial'] = {cid: {'score': c['score'], 'rules': list(c['rules'])} for cid, c in cands.items()}
        state['initial'] = trace['initial']
        if not cands:
            state['active'] = False
            return no_match_message(crop_name, crop), {**trace, 'decision': 'no_rule_matched'}, True
        qs = build_questions(state)
        for key, ans in preanswered(state, qs, state['symptom_text']):
            apply_answer(state, qs, key, ans, via='farmer_message')
        # AI: maswali ambayo mkulima ameshayajibu kwa maneno yake (kigezo 1)
        open_qs = {k: v['text'] for k, v in qs.items()
                   if k not in state['asked'] and not _redundant(state, v)}
        for key, ans in ai_layer.answered_questions(state['symptom_text'], open_qs, state).items():
            if key not in state['asked'] and not _redundant(state, qs[key]):
                apply_answer(state, qs, key, ans, via='farmer_message_ai')
        state['phase'] = 'questions'
        return _next(state, crop_name, trace)

    qs = build_questions(state)
    if state['phase'] == 'questions':
        if state['pending']:
            key = state['pending']
            answer = interpret(state, qs[key]['text'] if key in qs else key, text)
            if answer == 'clarify':
                clar = state.setdefault('clarified', {})
                if clar.get(key, 0) < 1:
                    clar[key] = clar.get(key, 0) + 1
                    return (clarify_message(qs[key]['text'] if key in qs else key),
                            {**trace, 'asked': key, 'clarify': True}, False)
                answer = 'unknown'
            apply_answer(state, qs, key, answer)
            state['pending'] = None
        return _next(state, crop_name, trace)

    if state['phase'] == 'extent':
        state['extent'] = parse_extent(text)
        if state['extent'] is None:
            got = ai_layer.interpret_extent(text, state)
            if got:
                state['extent'] = got[0]
                state['spreading'] = state['spreading'] or got[1]
        state['severity'] = severity_from(state['extent'], state['spreading'])
        return _finish(state, crop_name, trace)
    return None, trace, False


def _next(state, crop_name, trace):
    qs = build_questions(state)
    decision, top = decide(state)
    asked_count = sum(1 for ev in state['evidence'] if ev['via'] == 'question')
    if decision == 'continue' and asked_count < int(get_setting('max_questions')):
        key = choose_question(state, qs)
        if key:
            state['pending'] = key
            return (question_message(state, qs[key], asked_count + 1),
                    {**trace, 'asked': key, 'sources': qs[key]['sources'], 'scores': _scores(state)}, False)
    if decision == 'diagnosed':
        state['diagnosed'] = top
        if state['severity'] is None and not state['spreading']:
            low = state['symptom_text'].lower()
            ext = parse_extent(low) if ('shamba' in low or '%' in low or 'asilimia' in low) else None
            if ext is None:
                ext = state.get('extent')          # AI ilielewa ukubwa kwenye maelezo
            if ext is None:
                state['phase'] = 'extent'
                return _ack(state) + ASK_EXTENT, {**trace, 'asked': 'extent', 'scores': _scores(state)}, False
            state['extent'] = ext
        state['severity'] = severity_from(state['extent'], state['spreading'])
        return _finish(state, crop_name, trace)
    state['active'] = False
    return uncertain_message(state, crop_name), {**trace, 'decision': 'uncertain',
                                                 'scores': _scores(state),
                                                 'evidence': state['evidence'],
                                                 'dropped_text': state.get('dropped_text', []),
                  'initial': state.get('initial', {}), 'ai': state.get('ai', [])}, True


def _finish(state, crop_name, trace):
    cid = state.get('diagnosed')
    state['active'] = False
    if not cid:
        return uncertain_message(state, crop_name), {**trace, 'decision': 'uncertain'}, True
    gate = safety_gate(state, cid)
    text = diagnosis_message(state, cid, crop_name, gate)
    return text, {**trace, 'decision': 'diagnosed', 'diagnosis': cid, 'scores': _scores(state),
                  'evidence': state['evidence'], 'severity': state['severity'],
                  'extent': state['extent'], 'gate': gate,
                  'rules_used': state['candidates'][cid]['rules'],
                  'chemical_allowed': gate['chemical_allowed'],
                  'confidence': state['candidates'][cid]['score'],
                  'rules_text': ', '.join(_rules_used(state, cid, gate)),
                  'dropped_text': state.get('dropped_text', []),
                  'initial': state.get('initial', {}), 'ai': state.get('ai', [])}, True


def _scores(state):
    return {cid: c['score'] for cid, c in state['candidates'].items()}
