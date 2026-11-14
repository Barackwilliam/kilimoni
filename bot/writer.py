"""
AI kama mwandishi: jibu la data → maelezo ya kawaida (bila kuongeza ukweli wowote)
================================================================================

Moduli za data (mbegu, kupanda, udongo, mzunguko) zinatoa jibu lenye ukweli wa dataset
(rasimu). Hapa AI inaliandika upya kwa Kiswahili cha kawaida, kama afisa ugani
anavyoongea na mkulima — aya fupi, orodha pale tu inapohitajika.

Kabla ya kutumwa, jibu la AI linakaguliwa dhidi ya rasimu:
  • kila namba, tarehe/mwezi na jina la mbegu (mf. SC 403) lazima viwe kwenye rasimu;
  • hakuna jina la dawa / kemikali ambalo halikuwa kwenye rasimu;
  • tahadhari (⚠️) na mwelekeo wa afisa ugani (📞) wa rasimu vinabaki;
  • urefu unafaa WhatsApp.
Likishindwa ukaguzi, au AI isipopatikana, rasimu inatumwa kama ilivyo. Hakuna kubuni.
"""
import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

# Majibu yanayoandikwa upya: ushauri wa mwisho wa moduli za data (si menyu, si maswali)
REWRITE = {
    'seed_advisor': {'recommended', 'variety_fits', 'variety_not_fit', 'no_suitable_variety'},
    'planting_advisor': None,          # None = maamuzi yote isipokuwa yaliyo kwenye SKIP_DECISIONS
    'soil_advisor': None,
    'rotation_advisor': None,
}
SKIP_DECISIONS = {'need_location', 'need_crop', 'location_not_in_data', 'no_assessment', 'need_soil',
                  'crop_without_seed_data', 'unknown_soil', 'need_previous'}

SYSTEM = (
    "Wewe ni mwandishi wa Kilimoni AI, msaidizi wa kilimo wa WhatsApp kwa wakulima wa Tanzania. "
    "Unapewa RASIMU ya jibu iliyotengenezwa kutoka kwenye dataset iliyothibitishwa. Kazi yako ni "
    "kuiandika upya kwa Kiswahili cha kawaida na cha upole, kama afisa ugani anavyomweleza mkulima — "
    "maelezo mafupi yanayotiririka, si fomu. HUONGEZI ukweli wowote: kila namba, tarehe, mwezi, jina la "
    "mbegu, eneo na tahadhari lazima litoke kwenye rasimu, kama lilivyoandikwa. Usiongeze dawa, bei, "
    "vipimo wala ushauri mpya. Usiseme wewe ni AI. Jibu kwa JSON pekee."
)

NUM = re.compile(r'\d+(?:[.,]\d+)?')
VARIETY = re.compile(r'\b[A-Z]{2,}[\s-]?\d{2,4}[A-Z]?\b')
MONTHS = ('januari', 'februari', 'machi', 'aprili', 'mei', 'juni', 'julai', 'agosti', 'septemba',
          'oktoba', 'novemba', 'desemba')


def enabled():
    from diagnosis import ai_layer
    return getattr(settings, 'AI_WRITER', True) and ai_layer.available()


def eligible(trace):
    mode, decision = (trace or {}).get('mode'), (trace or {}).get('decision')
    if mode not in REWRITE or decision in SKIP_DECISIONS:
        return False
    allowed = REWRITE[mode]
    return allowed is None or decision in allowed


def _prompt(draft, question):
    return (
        f"SWALI LA MKULIMA: \"{question}\"\n\n"
        f"RASIMU (ukweli wote unaoruhusiwa):\n{draft}\n\n"
        "Andika jibu jipya:\n"
        "- Anza kwa kujibu swali lake moja kwa moja kwa sentensi 1-2.\n"
        "- Kisha eleza sababu na hatua kwa aya fupi. Tumia orodha ya • pale tu unapotaja vitu 3 au zaidi.\n"
        "- Hifadhi namba, tarehe, majina ya mbegu na tahadhari kama yalivyo kwenye rasimu.\n"
        "- Usizidi mistari 14. Unaweza kutumia *bold* kwa majina ya mbegu na tarehe muhimu.\n"
        "- Usiweke mstari wa 'Ushauri huu unatokana na…' — utaongezwa na mfumo.\n"
        'JSON: {"text": "..."}'
    )


def _norm_num(n):
    return n.replace(',', '.').lstrip('0') or '0'


def validate(text, draft):
    """Rudisha None kama jibu ni salama, vinginevyo sababu ya kulikataa."""
    from bot.diagnostic import CHEMICAL_PATTERN
    if not text or len(text) < 40:
        return 'fupi mno'
    if len(text) > 1800:
        return 'refu mno'
    have = {_norm_num(n) for n in NUM.findall(draft)}
    for n in NUM.findall(text):
        if _norm_num(n) not in have:
            return f'namba mpya: {n}'
    draft_vars = {v.replace(' ', '').replace('-', '').upper() for v in VARIETY.findall(draft)}
    for v in VARIETY.findall(text):
        if v.replace(' ', '').replace('-', '').upper() not in draft_vars:
            return f'jina jipya: {v}'
    low_t, low_d = text.lower(), draft.lower()
    for m in MONTHS:
        if m in low_t and m not in low_d:
            return f'mwezi mpya: {m}'
    for m in CHEMICAL_PATTERN.finditer(text):
        if m.group(0).lower() not in low_d:
            return f'kemikali/kipimo kipya: {m.group(0)}'
    if re.search(r'\b(nikiwa ai|mimi ni ai|kama ai|language model)\b', low_t):
        return 'inajitaja kama AI'
    return None


def _keep_lines(text, draft):
    """Tahadhari, mwelekeo wa afisa ugani na mstari wa chanzo vya rasimu vinabaki."""
    extra = []
    for line in draft.split('\n'):
        s = line.strip()
        if not s:
            continue
        if s.startswith('⚠️') and '⚠️' not in text:
            extra.append(s)
        elif s.startswith('📞') and '📞' not in text and 'afisa ugani' not in text.lower():
            extra.append(s)
        elif s.startswith('_') and s.endswith('_') and ('ushauri huu' in s.lower() or 'chanzo' in s.lower()):
            extra.append(s)
    return text.rstrip() + ('\n\n' + '\n'.join(extra) if extra else '')


def write(draft, question, trace=None):
    """Rudisha (jibu, taarifa_ya_trace). Jibu ni la AI likipita ukaguzi, vinginevyo rasimu."""
    from diagnosis import ai_layer
    info = {'writer': 'template'}
    if not enabled() or not eligible(trace):
        return draft, info
    model = getattr(settings, 'GROQ_WRITER_MODEL', '') or None
    try:
        out = ai_layer._chat(SYSTEM, _prompt(draft, question), max_tokens=900, timeout=12, model=model)
    except TypeError:
        out = ai_layer._chat(SYSTEM, _prompt(draft, question), max_tokens=900)
    except Exception as exc:                                  # AI isiangushe jibu
        logger.error("[writer] %s", exc)
        out = None
    text = ((out or {}).get('text') or '').strip() if isinstance(out, dict) else ''
    if not text:
        info['writer_note'] = 'AI haikujibu'
        return draft, info
    why = validate(text, draft)
    if why:
        info.update(writer='template', writer_rejected=why, writer_text=text[:600])
        logger.info("[writer] imekataliwa: %s", why)
        return draft, info
    info['writer'] = 'ai'
    return _keep_lines(text, draft), info


def dumps(info):
    return json.dumps(info, ensure_ascii=False)
