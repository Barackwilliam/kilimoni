"""
Tabaka la AI la lugha (Groq)
============================

Mgawanyo wa kazi uliokubaliwa na KILIMONI LABS:

    AI  = lugha na mazungumzo  (kuelewa mkulima, kumjibu kwa namna ya kawaida)
    Kanuni za MHD-007 = maamuzi (visababishi, maswali, uhakika, usalama wa dawa)

AI HAIAMUI chochote. Kazi zake ni nne, na kila moja inakaguliwa kabla
ya kutumika:

  1. understand_symptoms  Maelezo ya mkulima → dalili zipi za ORODHA YA
                          DATASET zinalingana (orodha funge: AI ikitaja
                          dalili isiyo kwenye orodha, inakataliwa).
  2. answered_questions   Maswali yapi ya kanuni mkulima ameshayajibu
                          kwenye maelezo yake (ili yasiulizwe tena).
  3. interpret_answer     Jibu la mkulima kwa maneno yake → ndiyo / hapana /
                          sijui / anaomba ufafanuzi.
  4. interpret_extent     "karibu robo tatu ya shamba" → asilimia.
  5. summary              Aya fupi ya kibinadamu juu ya jibu la kanuni.
                          Inakataliwa ikitaja dawa, tatizo jingine, namba
                          mpya, au ikizidi urefu.

AI ikikosekana (hakuna API key, mtandao, setting imezimwa) au jibu lake
likikataliwa, injini inaendelea kwa kulinganisha maneno kama kawaida.
Kila wito wa AI unaandikwa kwenye trace (state['ai']).
"""
import json
import logging
import re

from django.conf import settings

from .models import get_setting

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_CATALOG = 60
ANSWERS = ('yes', 'no', 'unknown', 'clarify')

BASE_RULES = (
    "Wewe ni sehemu ya mfumo wa Kilimoni AI unaosaidia wakulima wa Tanzania. "
    "Kazi yako ni KUELEWA LUGHA TU — huamui tatizo, hupendekezi dawa, hubuni chochote. "
    "Wakulima huandika Kiswahili cha kawaida, cha mtaani, chenye makosa ya tahajia, "
    "au Kiingereza kidogo. Jibu kwa JSON pekee, bila maelezo mengine."
)


# ─────────────────────────── Mawasiliano na Groq ───────────────────────────

def available():
    try:
        return bool(getattr(settings, 'GROQ_API_KEY', '')) and get_setting('ai_language') >= 1
    except Exception:
        return False


def _chat(system, user, max_tokens=900):
    """Wito mmoja kwa Groq (JSON mode). Rudisha dict au None. Tests hu-patch hii."""
    import requests
    from decouple import config
    body = {
        "model": getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
        "max_tokens": max_tokens,
        # gpt-oss ni reasoning model — bila 'low' content hurudi tupu
        "reasoning_effort": config('GROQ_REASONING', default='low'),
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=body, timeout=20)
        if resp.status_code == 400:
            # Model isiyokubali JSON mode — jaribu tena bila hiyo (prompt inaomba JSON)
            body.pop('response_format', None)
            resp = requests.post(GROQ_API_URL, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        content = (resp.json()['choices'][0]['message'].get('content') or '').strip()
        if not content:
            logger.warning("[AI layer] jibu tupu")
            return None
        content = re.sub(r'^```(?:json)?|```$', '', content).strip()
        if not content.startswith('{'):
            found = re.search(r'\{.*\}', content, re.S)
            content = found.group(0) if found else content
        data = json.loads(content)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning(f"[AI layer] imeshindwa: {exc}")
        return None


def _log(state, step, given, got, accepted, note=''):
    if state is None:
        return
    state.setdefault('ai', []).append({
        'step': step, 'input': given if isinstance(given, str) else json.dumps(given, ensure_ascii=False)[:600],
        'output': got, 'accepted': accepted, 'note': note,
    })


# ─────────────────────────── 1. Dalili ───────────────────────────

def symptom_catalog(crop):
    """
    Orodha funge ya dalili kama zilivyoandikwa kwenye dataset kwa zao hili.
    Rudisha list ya (id, maandishi). ID ni S1, S2… (si ID za dataset —
    AI haihitaji kuzijua).
    """
    from . import models as m
    from .engine import _clauses
    seen, phrases = set(), []

    def add(text):
        t = (text or '').strip().rstrip('.')
        k = t.lower()
        if len(t) > 3 and k not in seen:
            seen.add(k)
            phrases.append(t)

    for r in m.DiagnosisRule.objects.filter(crop=crop, is_active=True):
        add(r.normalized_symptom or r.input_symptom_sw)
    for s in m.Symptom.objects.filter(crop=crop, is_active=True):
        add(s.farmer_symptom_sw)
        add(s.normalized_symptom_sw)
    for model in (m.Pest, m.Disease):
        for cause in model.objects.filter(is_active=True):
            if cause.crop_id and cause.crop_id != crop.id:
                continue
            for c in _clauses(cause.visible_symptoms_sw):
                add(c)
    for r in m.DecisionRule.objects.filter(is_active=True).select_related('pest', 'disease'):
        cause = r.pest or r.disease
        if cause is None or (cause.crop_id and cause.crop_id != crop.id):
            continue
        rtype = (r.rule_type or '').lower()
        if 'differentiator' in rtype or 'differential' in rtype:
            continue
        for c in _clauses(r.input_symptom_sw):
            add(c)
    return [(f"S{i}", p) for i, p in enumerate(phrases[:MAX_CATALOG], 1)]


def understand_symptoms(crop, text, state=None):
    """
    Rudisha dict: {'phrases': [maandishi ya dataset], 'growth_stage': str|None,
    'extent_pct': int|None, 'spreading': bool} — au None AI ikikosekana/ikishindwa.
    """
    if not available():
        return None
    catalog = symptom_catalog(crop)
    if not catalog:
        return None
    listing = '\n'.join(f"{sid}: {p}" for sid, p in catalog)
    user = (
        f"Zao: {crop.crop_name_sw}\n"
        f"Maelezo ya mkulima: \"{text}\"\n\n"
        f"ORODHA YA DALILI ZA DATASET:\n{listing}\n\n"
        "Chagua ID za dalili kwenye orodha ambazo MAANA yake inalingana na kile mkulima "
        "alichoeleza (hata kama ametumia maneno tofauti). Usichague dalili ambayo mkulima "
        "hakuitaja. Kama hakuna inayolingana, rudisha orodha tupu.\n"
        "Pia toa: hatua ya ukuaji kama ameitaja (\"seedling\" kwa miche/mimea michanga, "
        "\"vegetative\" kwa mimea inayokua, vinginevyo null); asilimia ya shamba iliyoathirika "
        "kama ameitaja (namba 0-100 au null); na kama amesema tatizo linaenea haraka.\n"
        'JSON: {"matches": ["S1"], "growth_stage": null, "extent_pct": null, "spreading": false}'
    )
    out = _chat(BASE_RULES, user)
    if not out:
        _log(state, 'symptoms', text, None, False, 'hakuna jibu')
        return None
    ids = dict(catalog)
    matches = [i for i in (out.get('matches') or []) if isinstance(i, str) and i in ids]
    rejected = [i for i in (out.get('matches') or []) if i not in ids]
    stage = out.get('growth_stage') if out.get('growth_stage') in ('seedling', 'vegetative') else None
    extent = out.get('extent_pct')
    extent = int(extent) if isinstance(extent, (int, float)) and 0 <= extent <= 100 else None
    result = {'phrases': [ids[i] for i in matches], 'growth_stage': stage,
              'extent_pct': extent, 'spreading': out.get('spreading') is True}
    _log(state, 'symptoms', text, {**result, 'rejected_ids': rejected}, bool(matches),
         '' if not rejected else 'ID zisizo kwenye orodha zimekataliwa')
    return result


# ─────────────────────────── 2–4. Majibu ───────────────────────────

def answered_questions(text, questions, state=None):
    """
    questions: {key: maandishi ya swali}. Rudisha {key: 'yes'|'no'} kwa maswali
    ambayo mkulima ameshayajibu kwa uwazi kwenye maelezo yake.
    """
    if not available() or not questions:
        return {}
    keys = list(questions)
    listing = '\n'.join(f"Q{i}: {questions[k]}" for i, k in enumerate(keys, 1))
    user = (
        f"Maelezo ya mkulima: \"{text}\"\n\nMASWALI:\n{listing}\n\n"
        "Kwa kila swali, je maelezo ya mkulima yanalijibu WAZI? Andika \"yes\" kama ametaja "
        "kwamba ameona kitu hicho, \"no\" kama amesema hakipo, au usilitaje swali kabisa kama "
        "hakulizungumzia. Usikisie.\n"
        'JSON: {"answers": {"Q1": "yes"}}'
    )
    out = _chat(BASE_RULES, user)
    answers = (out or {}).get('answers') or {}
    result = {}
    for i, k in enumerate(keys, 1):
        v = answers.get(f"Q{i}")
        if v in ('yes', 'no'):
            result[k] = v
    _log(state, 'preanswered', text, result, bool(out))
    return result


def interpret_answer(question, reply, state=None):
    """Rudisha 'yes' | 'no' | 'unknown' | 'clarify', au None AI ikishindwa."""
    if not available():
        return None
    user = (
        f"Swali tuliloliuliza mkulima: \"{question}\"\n"
        f"Jibu lake: \"{reply}\"\n\n"
        "Jibu lake lina maana gani? \"yes\" (ameona/ndiyo), \"no\" (hajaona/hapana), "
        "\"unknown\" (hajui au hana uhakika), au \"clarify\" (anauliza maana ya swali au "
        "hajaelewa swali).\n"
        'JSON: {"answer": "yes"}'
    )
    out = _chat(BASE_RULES, user, max_tokens=500)
    ans = (out or {}).get('answer')
    ok = ans in ANSWERS
    _log(state, 'answer', reply, ans, ok)
    return ans if ok else None


def interpret_extent(reply, state=None):
    """Rudisha (asilimia|None, linaenea:bool) au None AI ikishindwa."""
    if not available():
        return None
    user = (
        f"Tulimuuliza mkulima ni kiasi gani cha shamba kimeathirika. Jibu lake: \"{reply}\"\n\n"
        "Kadiria asilimia ya shamba (0-100) kutoka jibu lake, au null kama hakusema kiasi. "
        "Pia, je amesema tatizo linaenea haraka?\n"
        'JSON: {"extent_pct": 50, "spreading": false}'
    )
    out = _chat(BASE_RULES, user, max_tokens=500)
    if not out:
        _log(state, 'extent', reply, None, False)
        return None
    pct = out.get('extent_pct')
    pct = int(pct) if isinstance(pct, (int, float)) and 0 <= pct <= 100 else None
    _log(state, 'extent', reply, {'extent_pct': pct, 'spreading': out.get('spreading') is True}, True)
    return pct, out.get('spreading') is True


def match_option(text, options, state=None, step='option'):
    """
    Chagua chaguo MOJA kutoka orodha funge {code: maelezo} kwa maana ya maneno
    ya mkulima, au None. Jibu lisilo kwenye orodha linakataliwa.
    """
    if not available() or not options:
        return None
    listing = '\n'.join(f"- {code}: {desc}" for code, desc in options.items())
    user = (
        f"Ujumbe wa mkulima: \"{text}\"\n\nCHAGUO:\n{listing}\n\n"
        "Chagua code MOJA ambayo maana yake inalingana na kile mkulima anataka, au null kama "
        "hakuna inayolingana. Usikisie.\n"
        'JSON: {"code": null}'
    )
    out = _chat(BASE_RULES, user, max_tokens=500)
    code = (out or {}).get('code')
    ok = code in options
    _log(state, step, text, code, ok or code is None)
    return code if ok else None


# ─────────────────────────── 5. Muhtasari wa kibinadamu ───────────────────────────

SUMMARY_MAX_WORDS = 60
SUMMARY_FORBIDDEN = re.compile(
    r'\bAI\b|dataset|kanuni|confidence|MHD|asilimia|%|\bdozi\b|\bml\b|\blita\b', re.IGNORECASE)


def _all_cause_names():
    from . import models as m
    names = set()
    for model in (m.Pest, m.Disease):
        for c in model.objects.filter(is_active=True):
            for n in (c.name_sw, c.name_en):
                if n and len(n) > 3:
                    names.add(n.lower())
    return names


def validate_summary(text, allowed_names):
    """Rudisha sababu ya kukataa, au None kama ni salama."""
    from bot.diagnostic import CHEMICAL_PATTERN
    if not text or not isinstance(text, str):
        return 'tupu'
    if len(text.split()) > SUMMARY_MAX_WORDS:
        return 'ndefu mno'
    if CHEMICAL_PATTERN.search(text):
        return 'inataja dawa'
    if SUMMARY_FORBIDDEN.search(text):
        return 'maneno ya mfumo au namba'
    if re.search(r'\d', text):
        return 'namba mpya'
    low = text.lower()
    allowed = {n.lower() for n in allowed_names if n}
    for name in _all_cause_names():
        if name in low and not any(name in a or a in name for a in allowed):
            return f"inataja tatizo jingine: {name}"
    return None


def summary(facts, state=None):
    """
    facts: dict ya ukweli uliokwisha amuliwa na kanuni. Rudisha aya fupi
    au None. Haiongezi taarifa — inaeleza tu kilichoamuliwa.
    """
    if not available() or get_setting('ai_summary') < 1:
        return None
    user = (
        "Andika aya FUPI (sentensi 2-3, maneno yasiyozidi 50) kwa Kiswahili cha kawaida na cha "
        "upole, kama afisa ugani anavyoongea na mkulima, ukieleza matokeo haya ya uchunguzi. "
        "Tumia TAARIFA HIZI PEKEE. Usitaje dawa, namba, asilimia, wala tatizo jingine lolote. "
        "Usiseme wewe ni AI. Usirudie orodha ya hatua — zitafuata chini ya aya yako.\n\n"
        f"TAARIFA:\n{json.dumps(facts, ensure_ascii=False, indent=1)}\n\n"
        'JSON: {"text": "..."}'
    )
    out = _chat(BASE_RULES, user, max_tokens=700)
    text = ((out or {}).get('text') or '').strip()
    allowed = [facts.get('tatizo', '')] + [facts.get('tatizo_en', '')]
    why = validate_summary(text, allowed) if out else 'hakuna jibu'
    _log(state, 'summary', facts.get('tatizo', ''), text, why is None, why or '')
    return text if why is None else None
