"""
Kuelewa kwanza, kisha data
==========================

Kila ujumbe wa mkulima unaeleweka KABLA ya kwenda kwenye dataset. Matokeo ni
"fomu" (frame) moja yenye majibu kutoka orodha funge:

    goal      — mkulima anataka nini (GOALS hapa chini)
    topic     — mada ya pengo la data (goal == 'gap'), mf. 'mbolea'
    crop      — zao lililotajwa (Crop) au None
    place     — eneo kama alivyolitaja, likitambuliwa na mfumo
    answer    — 'yes' | 'no' | 'unknown' | None (anapojibu swali letu)
    affirmed  — dalili alizosema ZIPO (maneno yake mwenyewe)
    denied    — dalili alizosema HAZIPO
    question  — swali lake la moja kwa moja, kama ameuliza
    source    — 'ai' au 'rules'

AI (Groq) ni ya LUGHA tu: inajaza fomu, haitoi ushauri. Kila jibu lake
linathibitishwa: goal lazima liwe kwenye orodha, zao lazima liwe kwenye
database, eneo lazima litambuliwe na mfumo, dalili lazima ziwe na maneno
yaliyomo kwenye ujumbe. AI isipopatikana au ikishindwa, kanuni za maneno
(rule_frame) zinajaza fomu ileile — mfumo unaendelea kufanya kazi.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

GOALS = {
    'diagnosis': 'anaeleza tatizo la zao/mmea (dalili, wadudu, ugonjwa, mimea haiko sawa) au anauliza tatizo ni nini',
    'answer': 'anajibu swali ambalo bot imemuuliza sasa hivi (ndiyo/hapana/sijui, namba, eneo, ukubwa wa shamba, umri)',
    'followup': 'anauliza kuhusu utambuzi au ushauri aliopewa sasa hivi (nifanye nini, ni hilo kweli?, dawa gani, kiasi gani)',
    'seed': 'anataka kuchagua mbegu/aina ya mbegu, au anauliza kama mbegu fulani inafaa',
    'planting': 'anauliza wakati, mwezi au msimu wa kupanda, au apande sasa kulingana na mvua',
    'soil': 'anauliza kuhusu udongo wake au kama udongo unafaa zao',
    'rotation': 'anauliza zao gani lifuate baada ya jingine (mzunguko wa mazao)',
    'where_grows': 'anauliza zao hustawi wapi / maeneo au mikoa gani ya Tanzania',
    'coverage': 'anauliza bot ina taarifa za maeneo au mazao gani',
    'abiotic': 'anauliza kama ukame, ukosefu wa maji/mvua au kutoweka mbolea ndiyo chanzo cha tatizo la mimea',
    'challenge': 'anapinga ushauri ambao bot imempa (kwa nini umenishauri…, ungeanza kuniuliza…)',
    'complaint': 'analalamika kwamba bot haikumuelewa au haikujibu swali lake',
    'gap': 'anauliza mada ambayo bot haina data yake bado (tazama TOPICS)',
    'greeting': 'salamu tu',
    'thanks': 'shukrani au kukubali (asante, sawa, poa) bila swali jipya',
    'identity': 'anauliza bot ni nani',
    'capability': 'anauliza bot inaweza kusaidia nini',
    'offtopic': 'jambo lisilo la kilimo kabisa',
    'unclear': 'haieleweki',
}

TOPICS = {
    'mbolea': 'mbolea (aina, kiasi, wakati)',
    'kuvuna': 'kuvuna na dalili za kukomaa',
    'kuhifadhi mazao': 'kuhifadhi mazao baada ya kuvuna',
    'bei na masoko': 'bei na masoko',
    'hali ya hewa': 'hali ya hewa / utabiri',
    'kupalilia na kudhibiti magugu': 'kupalilia na magugu',
    'mifugo': 'mifugo (ng\'ombe, mbuzi, kuku…)',
    'maandalizi ya shamba na zana': 'kuandaa shamba, vifaa na zana',
    'umwagiliaji': 'umwagiliaji',
    'nafasi za kupanda': 'nafasi/umbali na mbinu za kupanda',
    'kupogoa': 'kupogoa',
}

# Goals ambazo ni "moduli" za data (zinaweza kukatisha mazungumzo yanayosubiri)
MODULE_GOALS = {'seed', 'planting', 'soil', 'rotation', 'where_grows', 'coverage', 'gap', 'abiotic'}


def empty(source='rules'):
    return {'goal': 'unclear', 'topic': '', 'crop': None, 'place': '', 'answer': None,
            'affirmed': [], 'denied': [], 'question': '', 'source': source}


# ─────────────────────────── Muktadha ───────────────────────────

def pending_kind(user):
    """Bot inasubiri nini kutoka kwa mkulima sasa hivi (kutoka session)."""
    from diagnosis import engine as rx
    sess = (user.session_state or {}) if user else {}
    state = rx.get_state(sess)
    if state:
        return {'questions': 'question', 'extent': 'extent', 'intake': 'intake',
                'crop': 'crop', 'symptoms': 'symptoms'}.get(state.get('phase'), 'question')
    if sess.get('goal_pending'):
        return 'menu'
    adv = sess.get('adv') or {}
    if adv.get('stage'):
        return {'location': 'location', 'crop': 'crop', 'rain': 'question'}.get(adv['stage'], 'question')
    if sess.get('awaiting_location'):
        return 'location'
    if sess.get('awaiting_crop'):
        return 'crop'
    if sess.get('last_dx'):
        import time
        if time.time() - float(sess['last_dx'].get('at', 0)) < 1800:
            return 'after_diagnosis'
    return ''


def recent_turns(user, limit=4):
    from bot.models import Conversation
    if not user:
        return []
    rows = list(Conversation.objects.filter(user=user).order_by('-id')[:limit])
    rows.reverse()
    return [('mkulima' if r.message_direction == 'inbound' else 'bot', (r.raw_message or '')[:400]) for r in rows]


# ─────────────────────────── Kanuni (akiba) ───────────────────────────

ANSWER_PENDING = {'question', 'extent', 'intake', 'location', 'crop', 'menu', 'offer', 'symptoms'}


def rule_frame(text, pending='', normalized=None):
    """Fomu kwa kanuni za maneno tu — mpangilio uleule wa injini ya zamani."""
    from bot import engine as E
    from bot import diagnostic as dg
    from bot.messages import detect_offtopic_kind
    from diagnosis import engine as rx
    from advisory import coverage, planting, rotation, seed, soil

    raw = text or ''
    low = normalized if normalized is not None else E.apply_synonyms(E.normalize_text(raw))
    f = empty('rules')
    f['crop'] = E.detect_crop(low)
    try:
        f['place'] = E.detect_location(low)
    except Exception:
        f['place'] = ''
    ans = rx.parse_answer(low)
    f['answer'] = ans if ans != 'unknown' or any(p in low for p in rx.UNKNOWN_PHRASES) else None
    words = low.split()

    def done(goal, topic=''):
        f['goal'], f['topic'] = goal, topic
        return f

    if E.is_greeting(low) and len(words) <= 4:
        return done('greeting')
    if E.CHALLENGE.search(low):
        return done('challenge')
    if E.is_abiotic_question(low) and not seed.wants_seed(low):
        return done('abiotic')
    if E._is_complaint(low) and not E._is_new_question(low):
        return done('complaint')
    if pending == 'after_diagnosis' and (E.FOLLOWUP.search(low)) and rx.is_vague(low):
        return done('followup')
    if pending in ANSWER_PENDING:
        if f['answer'] or len(words) <= 4 or (pending == 'location' and f['place']) \
                or (pending == 'intake' and rx.parse_intake(low)[0]):
            if not (coverage.wants_where_grows(low, bool(f['crop'])) or E.knowledge_gap_topic(low)):
                return done('answer')
    if coverage.wants_where_grows(low, has_crop_context=bool(f['crop'])):
        return done('where_grows')
    if coverage.wants_coverage(low):
        return done('coverage')
    if rotation.wants_rotation(low):
        return done('rotation')
    gap = E.knowledge_gap_topic(low)
    if gap:
        return done('gap', gap)
    if ('udongo' in words or soil.wants_soil(low)) and not dg.is_problem_message(low, None):
        return done('soil')
    if planting.wants_planting(low) and not seed.mentioned_variety(low):
        return done('planting')
    if seed.wants_seed(low):
        return done('seed')
    if dg.is_problem_message(low, None):
        return done('diagnosis')
    if pending == 'after_diagnosis' and E.FOLLOWUP.search(low):
        return done('followup')
    if E.is_acknowledgement(low):
        return done('thanks')
    kind = detect_offtopic_kind(low)
    if kind in ('identity', 'capability'):
        return done(kind)
    if kind:
        return done('offtopic')
    return f


# ─────────────────────────── AI (lugha tu) ───────────────────────────

SYSTEM = (
    "Wewe ni sehemu ya KUELEWA ya Kilimoni AI, msaidizi wa kilimo wa WhatsApp kwa wakulima wa Tanzania. "
    "Kazi yako ni kusoma ujumbe wa mkulima (pamoja na mazungumzo yaliyotangulia) na kujaza fomu. "
    "HUTOI ushauri, HUAMUI tatizo, HUBUNI chochote. Wakulima huandika Kiswahili cha mtaani, chenye "
    "makosa ya tahajia. Soma MAANA, si neno moja: 'vumbi la mbao' si 'hapana'; 'naomba kufahamu' si "
    "'kufa'; 'sijaona funza' maana yake funza HAWAPO. Jibu kwa JSON pekee."
)


def _prompt(text, pending, turns, crops):
    goals = '\n'.join(f"- {k}: {v}" for k, v in GOALS.items())
    topics = '\n'.join(f"- {k}: {v}" for k, v in TOPICS.items())
    history = '\n'.join(f"{who}: {msg}" for who, msg in turns) or '(hakuna)'
    waiting = {
        'question': 'bot imemuuliza swali la ndiyo/hapana la uchunguzi',
        'extent': 'bot imemuuliza ukubwa wa shamba ulioathirika',
        'intake': 'bot imemuuliza achague dalili kwa namba na umri wa mimea',
        'location': 'bot imemuuliza eneo lake (mkoa/wilaya/kata)',
        'crop': 'bot imemuuliza zao gani',
        'menu': 'bot imempa menyu ya namba',
        'symptoms': 'bot imemuuliza dalili',
        'after_diagnosis': 'bot imempa utambuzi na ushauri sasa hivi',
    }.get(pending, 'bot haisubiri jibu maalum')
    return (
        f"MAZUNGUMZO YALIYOTANGULIA:\n{history}\n\n"
        f"BOT INASUBIRI: {waiting}\n\n"
        f"UJUMBE MPYA WA MKULIMA: \"{text}\"\n\n"
        f"GOALS (chagua MOJA linaloeleza anachotaka sasa):\n{goals}\n\n"
        f"TOPICS (kwa goal 'gap' tu):\n{topics}\n\n"
        f"MAZAO YALIYOPO: {', '.join(crops) or '(hakuna)'}\n\n"
        "Kanuni:\n"
        "- Kama anajibu swali la bot NA pia anauliza jambo jipya, chagua goal la jambo jipya "
        "(mf. 'abiotic', 'followup'), lakini jaza 'answer' pia.\n"
        "- 'crop': jina la zao kutoka MAZAO YALIYOPO tu (au kutoka mazungumzo kama ni wazi), vinginevyo null.\n"
        "- 'place': eneo kama alivyoandika (hata kwa makosa ya tahajia), au null.\n"
        "- 'affirmed'/'denied': dalili kwa maneno YAKE mwenyewe (vipande vifupi vya ujumbe), si kubuni.\n"
        "- 'question': swali lake la moja kwa moja kwa maneno yake, au null.\n"
        "- Ukame/mvua kama SIFA ya mbegu (\"mbegu inayostahimili ukame\") ni 'seed', si 'abiotic'.\n"
        "- Mbolea, samadi, bei, kuvuna, kuhifadhi, hali ya hewa n.k. ni 'gap' (bot haina data yake bado).\n\n"
        "Mifano:\n"
        "[bot imeuliza swali] \"ee nimeona unga kama wa mbao kwenye kitovu\" → goal answer, answer yes\n"
        "[bot imeuliza swali] \"sijaona wadudu, ila mvua haijanyesha mwezi mzima, ndio sababu?\" → goal abiotic, answer no\n"
        "\"mbegu ipi inavumilia ukame?\" → goal seed\n"
        "\"nataka kujua bei ya maharage\" → goal gap, topic \"bei na masoko\"\n"
        "\"umenishauri nichome mimea bila kuniuliza chochote\" → goal challenge (TU kama bot imetoa ushauri)\n"
        "\"jua ni kali sana, nilime au niache kwanza?\" → goal planting\n"
        "[bot imetoa utambuzi] \"sawa nimeelewa\" → goal thanks\n\n"
        'JSON: {"goal": "...", "topic": null, "crop": null, "place": null, "answer": null, '
        '"affirmed": [], "denied": [], "question": null}'
    )


def _grounded(phrase, text):
    """Kipande cha AI kinakubaliwa tu kama maneno yake mahususi yamo kwenye ujumbe."""
    from diagnosis import engine as rx
    own = rx._tokens(text)
    toks = rx._tokens(phrase)
    return bool(toks) and sum(1 for t in toks if any(rx._same(t, o) for o in own)) >= max(1, len(toks) // 2)


def _call(ai_layer, prompt):
    """Wito wa AI ya kuelewa: model yake (GROQ_UNDERSTAND_MODEL) na timeout fupi."""
    from django.conf import settings
    model = getattr(settings, 'GROQ_UNDERSTAND_MODEL', '') or None
    try:
        return ai_layer._chat(SYSTEM, prompt, max_tokens=700, timeout=10, model=model)
    except TypeError:                              # mbadala wa _chat (tests) bila vigezo hivi
        return ai_layer._chat(SYSTEM, prompt, max_tokens=700)


def ai_frame(text, pending='', turns=(), normalized=None):
    """Fomu kutoka AI, iliyothibitishwa. None = AI haipo/imeshindwa → tumia kanuni."""
    from diagnosis import ai_layer
    from crops.models import Crop
    from bot import engine as E
    if not ai_layer.available():
        return None
    crops = list(Crop.objects.filter(active_status='active').values_list('crop_name_sw', flat=True)) \
        if hasattr(Crop, 'active_status') else list(Crop.objects.values_list('crop_name_sw', flat=True))
    out = _call(ai_layer, _prompt(text, pending, list(turns), crops))
    if not isinstance(out, dict) or out.get('goal') not in GOALS:
        logger.info("[understand] AI haikutoa goal halali: %s", str(out)[:200])
        return None
    f = empty('ai')
    f['goal'] = out['goal']
    if f['goal'] == 'gap':
        f['topic'] = out.get('topic') if out.get('topic') in TOPICS else ''
        if not f['topic']:
            f['goal'] = 'unclear'
    low = normalized if normalized is not None else E.apply_synonyms(E.normalize_text(text))
    name = out.get('crop')
    if isinstance(name, str) and name.strip():
        f['crop'] = E.detect_crop(E.normalize_text(name)) or None
    if not f['crop']:
        f['crop'] = E.detect_crop(low)
    place = out.get('place')
    if isinstance(place, str) and place.strip():
        try:
            f['place'] = E.detect_location(E.normalize_text(place)) or ''
        except Exception:
            f['place'] = ''
    if out.get('answer') in ('yes', 'no', 'unknown'):
        f['answer'] = out['answer']
    for key in ('affirmed', 'denied'):
        f[key] = [p for p in (out.get(key) or []) if isinstance(p, str) and _grounded(p, text)][:6]
    if isinstance(out.get('question'), str):
        f['question'] = out['question'][:300]
    return f


# Goals za kanuni zinazoaminika zikigundua kitu mahususi (kipimo: benki ya majaribio,
# 15 Nov — kanuni zikisema goal mahususi zilikuwa sahihi mara nyingi kuliko AI; AI ilikuwa
# bora pale kanuni zilipokosa: 'unclear' / 'offtopic').
RULE_UNSURE = {'unclear', 'offtopic'}


ADVICE_MARKERS = ('hatua za kuchukua', 'tatizo linalowezekana', 'ondoa mimea', 'ichome', 'nyunyiz',
                  'mbegu zinazofaa', 'unaweza kupanda', 'subiri kwanza', 'ningependekeza', 'pendekez')


def advice_recent(user, limit=3):
    """Bot imetoa ushauri kwenye majibu yake ya karibuni? ('challenge' inahitaji ushauri wa kupinga.)"""
    from bot.models import Conversation
    if not user:
        return False
    rows = Conversation.objects.filter(user=user, message_direction='outbound').order_by('-id')[:limit]
    return any(m in (r.raw_message or '').lower() for r in rows for m in ADVICE_MARKERS)


def context_check(f, pending, advice=True):
    """
    AI ilichanganya goals za muktadha (live eval): 'answer' ambapo bot haikuuliza chochote,
    'followup' bila utambuzi uliotangulia. Goal lisilowezekana kwa muktadha huu → 'unclear'.
    """
    if f['goal'] == 'answer' and pending not in ANSWER_PENDING:
        f['goal'] = 'unclear'
    if f['goal'] == 'followup' and pending != 'after_diagnosis':
        f['goal'] = 'answer' if pending in ANSWER_PENDING else 'unclear'
    if f['goal'] == 'challenge' and not advice:
        # Live 15 Nov: "jua ni kali sana nilime au niache kwanza" ilisomwa kama changamoto
        # na bot ikaomba radhi kwa ushauri ambao haikuwahi kutoa
        f['goal'] = 'unclear'
    return f


def combine(ai, rules):
    """
    Fomu ya mwisho: goal la kanuni likiwa mahususi linashinda; vinginevyo goal la AI.
    Sehemu nyingine zinajazwa na chanzo chochote chenye taarifa.
    """
    if ai is None:
        return rules
    f = dict(rules) if rules['goal'] not in RULE_UNSURE else dict(ai)
    f['source'] = 'rules+ai' if rules['goal'] not in RULE_UNSURE else 'ai'
    if f['goal'] == 'gap' and not f.get('topic'):
        f['topic'] = ai.get('topic') or rules.get('topic') or ''
    f['crop'] = rules['crop'] or ai['crop']
    f['place'] = rules['place'] or ai['place']
    f['answer'] = ai['answer'] or rules['answer']
    for key in ('affirmed', 'denied', 'question'):
        f[key] = ai.get(key) or rules.get(key) or ([] if key != 'question' else '')
    return f


def understand(text, user=None, pending=None, normalized=None, use_ai=True):
    """Fomu ya ujumbe: kanuni + AI (ikipatikana), zikiunganishwa kwa combine()."""
    pending = pending_kind(user) if pending is None else pending
    rules = rule_frame(text, pending, normalized)
    ai = None
    if use_ai and rules['goal'] in RULE_UNSURE | {'answer', 'diagnosis', 'complaint'}:
        # AI inaitwa tu pale inapoongeza kitu: kanuni hazijaelewa, au tunahitaji
        # jibu/dalili/swali la ndani (huokoa maombi — vikomo vya maombi)
        try:
            ai = ai_frame(text, pending, recent_turns(user), normalized)
            if ai is not None:
                ai = context_check(ai, pending, advice=advice_recent(user) if user else True)
        except Exception as e:                     # AI isiangushe mazungumzo
            logger.error("[understand] AI error: %s", e)
            ai = None
    f = combine(ai, rules)
    f['pending'] = pending
    return f


def as_trace(f):
    return {k: (v.crop_name_sw if k == 'crop' and v else v) for k, v in f.items()}


def dumps(f):
    return json.dumps(as_trace(f), ensure_ascii=False)
