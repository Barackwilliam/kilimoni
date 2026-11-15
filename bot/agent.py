"""
Wakala wa Kilimoni AI: AI inapokea ujumbe, inaelewa, inatumia dataset kama marejeo
===================================================================================

Mtiririko (kama mteja alivyotaka):
  1. AI inasoma ujumbe pamoja na mazungumzo yaliyotangulia na kuelewa mkulima anataka nini.
  2. Swali likihitaji data (mbegu, kupanda, udongo, mzunguko, wadudu/magonjwa) AI inaita ZANA
     zinazochunguza dataset na kurudisha ukweli wake. Mkulima akieleza dalili za tatizo, AI
     inakabidhi kwa uchunguzi wa kanuni (maswali + uhakika unaotokana na kanuni).
  3. AI inaandika jibu kwa Kiswahili cha kawaida kutoka kwenye ukweli huo. Kisipopatikana,
     inamwambia mkulima wazi kwamba hakipo kwenye data.
  4. Kabla ya kutumwa, jibu linakaguliwa: hakuna namba, mwezi, jina la mbegu, dawa wala jina
     la mdudu/ugonjwa ambalo halikutoka kwenye zana au mazungumzo. Likishindwa mara mbili,
     au AI isipopatikana, mfumo wa kanuni (bot/engine.py) unajibu.
"""
import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

MAX_STEPS = 4


def enabled():
    from diagnosis import ai_layer
    return getattr(settings, 'AGENT_MODE', True) and ai_layer.available() and not ai_layer.rate_limited()


# ─────────────────────────── Zana (dataset kama marejeo) ───────────────────────────

def _fn(name, description, props, required=()):
    return {'type': 'function', 'function': {
        'name': name, 'description': description,
        'parameters': {'type': 'object', 'properties': props, 'required': list(required)}}}


_S = {'type': 'string'}
TOOLS = [
    _fn('mbegu_bora', 'Chunguza dataset ya mbegu: mbegu zinazofaa zao fulani kwenye eneo fulani, au kama mbegu '
        'iliyotajwa inafaa.', {'zao': _S, 'eneo': _S, 'mahitaji': {
            'type': 'string', 'description': 'mf. "inastahimili ukame", "inakomaa haraka", jina la mbegu'}},
        ['zao']),
    _fn('wakati_wa_kupanda', 'Chunguza kalenda ya kupanda: lini kupanda zao kwenye eneo, au apande sasa au asubiri.',
        {'zao': _S, 'eneo': _S, 'hali_ya_mvua': {
            'type': 'string', 'description': 'alichosema mkulima kuhusu mvua, mf. "zimeanza", "bado", ""'}},
        ['zao']),
    _fn('udongo', 'Chunguza dataset ya udongo: aina ya udongo na kama unafaa zao.',
        {'maelezo_ya_udongo': _S, 'zao': _S}, ['maelezo_ya_udongo']),
    _fn('mzunguko_wa_mazao', 'Chunguza dataset ya mzunguko wa mazao: zao gani lifuate baada ya jingine.',
        {'zao_lililotangulia': _S, 'zao_linalofuata': _S}, ['zao_lililotangulia']),
    _fn('tafuta_kwenye_data', 'Tafuta maelezo ya jumla kwenye dataset (mf. "funza jeshi ni nini", jinsi ya kuzuia '
        'mdudu fulani). USITUMIE kutambua tatizo la mmea wa mkulima — kwa hilo tumia anza_uchunguzi.',
        {'maneno': _S}, ['maneno']),
    _fn('orodha_ya_data', 'Mazao na maeneo ambayo Kilimoni ina taarifa zake.', {}),
    _fn('anza_uchunguzi', 'Mkulima ameeleza tatizo/dalili za mmea wake (wadudu, ugonjwa, majani, kunyauka…). '
        'Anzisha uchunguzi wa kanuni wenye maswali. Usitaje jina la tatizo mwenyewe.',
        {'zao': _S, 'dalili': _S}, ['dalili']),
]


def _norm(text):
    from bot.engine import apply_synonyms, normalize_text
    return apply_synonyms(normalize_text(text or ''))


def _crop(name, user):
    from bot.engine import detect_crop, _recent_crop
    from crops.models import Crop
    return detect_crop(_norm(name)) if name else (
        _recent_crop(user) or (Crop.objects.filter(id=user.last_crop_id).first() if user.last_crop_id else None))


def _loc(eneo, user):
    from advisory import location as adv_location, seed as adv_seed
    from bot.engine import remember_farm_location
    if eneo:
        loc = adv_location.resolve(_norm(eneo))
        if loc and loc.get('aez_id'):
            remember_farm_location(user, _norm(eneo))
            return loc, ''
        return None, eneo
    return adv_seed.location_from_user(user), ''


def _clean(text):
    return re.sub(r'\n{3,}', '\n\n', (text or '').strip())


def _places():
    from advisory.coverage import places_line
    return places_line(limit=10) or ''


def _crops_with(module):
    from advisory.coverage import crops_with_data
    return [c for c, mods in crops_with_data() if any(module in m.lower() for m in mods)]


def tool_mbegu_bora(user, zao='', eneo='', mahitaji=''):
    from advisory import seed as adv_seed
    crop = _crop(zao, user)
    if not crop:
        return {'matokeo': 'zao halijatajwa au halimo kwenye data — muulize mkulima zao gani'}
    if not adv_seed.has_data(crop):
        return {'matokeo': f'hakuna data ya mbegu za {crop.crop_name_sw}', 'mazao_yenye_data_ya_mbegu': _crops_with('mbegu')}
    loc, unknown = _loc(eneo, user)
    if unknown:
        return {'matokeo': f'eneo "{unknown}" halimo kwenye data ya maeneo', 'maeneo_yenye_data': _places()}
    text, trace = adv_seed.advise(crop, loc, f"{zao} {eneo} {mahitaji}", state={})
    if trace.get('decision') == 'need_location':
        return {'matokeo': 'eneo la mkulima halijulikani — muulize wilaya au kata yake',
                'maeneo_yenye_data': _places()}
    return {'zao': crop.crop_name_sw, 'jibu_la_data': _clean(text)}


def tool_wakati_wa_kupanda(user, zao='', eneo='', hali_ya_mvua=''):
    from advisory import planting as adv_planting
    crop = _crop(zao, user)
    if not crop:
        return {'matokeo': 'zao halijatajwa au halimo kwenye data — muulize mkulima zao gani'}
    loc, unknown = _loc(eneo, user)
    if unknown or not loc:
        out = {'matokeo': (f'eneo "{unknown}" halimo kwenye data ya maeneo' if unknown
                           else 'eneo la mkulima halijulikani — muulize wilaya au kata yake'),
               'maeneo_yenye_data': _places()}
        overview = adv_planting.zone_overview(crop)
        if overview:
            out['muhtasari_wa_kitaifa'] = overview
        return out
    text, trace = adv_planting.advise(crop, loc, f"{zao} {eneo} {hali_ya_mvua}", state={})
    return {'zao': crop.crop_name_sw, 'jibu_la_data': _clean(text)}


def tool_udongo(user, maelezo_ya_udongo='', zao=''):
    from advisory import soil as adv_soil
    crop = _crop(zao, user) if zao else None
    text, trace = adv_soil.advise(crop, _norm(maelezo_ya_udongo), state={})
    if trace.get('decision') == 'need_soil':
        return {'matokeo': 'aina ya udongo haikutambulika — muulize mkulima udongo wake ukoje '
                           '(kichanga, tifutifu, mfinyanzi, mwekundu, mweusi unaopasuka)'}
    return {'jibu_la_data': _clean(text)}


def tool_mzunguko_wa_mazao(user, zao_lililotangulia='', zao_linalofuata=''):
    from advisory import rotation as adv_rotation
    text, trace = adv_rotation.advise(_norm(f"baada ya {zao_lililotangulia} {zao_linalofuata}"), state={})
    if trace.get('decision') == 'need_crop':
        return {'matokeo': 'zao lililotangulia halikutambulika kwenye data ya mzunguko'}
    return {'jibu_la_data': _clean(text)}


SEARCH_FIELDS = ('name_sw', 'name_en', 'aliases', 'visible_symptoms_sw', 'ai_summary_sw', 'prevention',
                 'cultural_control', 'mechanical_control', 'key_differentiator', 'favourable_conditions',
                 'transmission', 'key_diagnostic_feature')


def tool_tafuta_kwenye_data(user, maneno=''):
    """Utafutaji wa maneno kwenye Pest/Disease na maktaba ya dataset (bila sehemu za dawa)."""
    from diagnosis import engine as rx
    from diagnosis.models import Disease, Pest
    from datasets.models import DatasetRow
    want = [t for t in rx._tokens(_norm(maneno)) if len(t) > 2]
    if not want:
        return {'matokeo': 'hakuna maneno ya kutafuta'}

    def score(text):
        toks = rx._tokens(text)
        return sum(1 for w in want if any(rx._same(w, t) for t in toks))

    hits = []
    for model in (Pest, Disease):
        for obj in model.objects.all()[:400]:
            parts = {f: getattr(obj, f, '') for f in SEARCH_FIELDS if getattr(obj, f, '')}
            sc = score(' '.join(parts.values()))
            if sc:
                hits.append((sc, {'chanzo': obj.source_id, **{k: str(v)[:300] for k, v in parts.items()}}))
    for row in DatasetRow.objects.select_related('sheet').all()[:3000]:
        values = [str(v) for k, v in (row.data or {}).items()
                  if v and not re.search(r'dose|dosage|chemical|product|price|bei|dawa', str(k), re.I)]
        text = ' | '.join(values)
        sc = score(text)
        if sc:
            hits.append((sc, {'chanzo': row.row_id or f'row{row.id}', 'maelezo': text[:400]}))
    hits.sort(key=lambda h: -h[0])
    if not hits:
        return {'matokeo': f'hakuna taarifa kuhusu "{maneno}" kwenye data'}
    return {'matokeo': [h[1] for h in hits[:4]]}


def tool_orodha_ya_data(user):
    from advisory.coverage import coverage_message
    return {'jibu_la_data': coverage_message()}


TOOL_FUNCS = {
    'mbegu_bora': tool_mbegu_bora, 'wakati_wa_kupanda': tool_wakati_wa_kupanda, 'udongo': tool_udongo,
    'mzunguko_wa_mazao': tool_mzunguko_wa_mazao, 'tafuta_kwenye_data': tool_tafuta_kwenye_data,
    'orodha_ya_data': tool_orodha_ya_data,
}


# ─────────────────────────── Maelekezo ───────────────────────────

NO_DATA_TOPICS = ('bei na masoko', 'mbolea', 'kuvuna na kuhifadhi', 'hali ya hewa', 'mifugo',
                  'magugu na kupalilia', 'umwagiliaji', 'zana na maandalizi ya shamba')


def about():
    from advisory.coverage import crops_with_data
    crops = ', '.join(c for c, _ in crops_with_data()) or 'bado inaongezwa'
    places = _places() or 'bado inaongezwa'
    return (
        "Kilimoni AI ni msaidizi wa kilimo wa WhatsApp wa KILIMONI LABS kwa wakulima wa Tanzania. Taarifa zake "
        "zinatoka kwenye dataset za kitaalamu zilizoandaliwa na kuthibitishwa na timu ya KILIMONI LABS: wadudu na "
        "magonjwa ya mazao, mbegu bora, kalenda za kupanda, udongo, mzunguko wa mazao na kanda za kilimo. "
        f"Mazao yenye data: {crops}. Maeneo yenye taarifa kamili: {places}. "
        f"Bado haina data ya: {', '.join(NO_DATA_TOPICS)}. Haitoi majina ya dawa wala vipimo vyake. "
        "Si mbadala wa afisa ugani."
        + (f" Mfumo wake umejengwa na {_built_by()} — TAJA hili TU mkulima akiuliza moja kwa moja nani "
           "aliyekuunda/aliyekutengeneza, kwa sentensi: \"Kilimoni AI ni huduma ya KILIMONI LABS. Mfumo wake "
           f"umejengwa na {_built_by()}.\"" if _built_by() else '')
    )


def _built_by():
    return (getattr(settings, 'BUILT_BY', '') or '').strip()


def system_prompt():
    return (
        "Wewe ni Kilimoni AI, msaidizi wa kilimo anayeongea na wakulima wa Tanzania kwenye WhatsApp kwa "
        "Kiswahili. Wakulima huandika kimtaa na kwa makosa ya tahajia — elewa MAANA ya anachouliza.\n\n"
        "KANUNI:\n"
        "1. Ushauri wowote wa kilimo (mbegu, wakati wa kupanda, udongo, mzunguko, maelezo ya wadudu/magonjwa) "
        "LAZIMA utoke kwenye zana. Usijibu kutoka kichwani.\n"
        "2. Mkulima akieleza tatizo au dalili za mmea wake, tumia anza_uchunguzi. Usitaje wala kukisia jina la "
        "ugonjwa au mdudu mwenyewe.\n"
        "3. Zana ikisema hakuna data, au mada ni miongoni mwa zisizo na data, mwambie mkulima wazi na kwa upole "
        "kwamba taarifa hiyo haipo bado, mshauri afisa ugani, na taja unachoweza kumsaidia. Usitoe ushauri wa jumla.\n"
        "4. Usitaje dawa, bei, vipimo vya dawa/mbolea. Usibuni namba, miezi, tarehe, majina ya mbegu au maeneo — "
        "tumia yale ya zana kama yalivyo.\n"
        "5. Maswali kuhusu wewe (wewe ni nani, taarifa unatoa wapi, unaweza nini) jibu kutoka KUHUSU.\n"
        "6. Kama unahitaji zao au eneo ili kutumia zana na mkulima hajataja, muulize swali MOJA fupi.\n"
        "7. Jibu kwa Kiswahili cha kawaida na cha upole, kama afisa ugani: jibu swali kwanza, kisha maelezo "
        "mafupi. Mistari isiyozidi 10. Orodha ya • pale tu kuna vitu 3 au zaidi. *bold* kwa majina muhimu.\n"
        "8. Usiseme wewe ni model ya AI; wewe ni Kilimoni AI. Usisalimie kwa 'Shikamoo'.\n\n"
        f"KUHUSU: {about()}"
    )


# ─────────────────────────── Ukaguzi wa jibu ───────────────────────────

def _cause_names():
    from diagnosis.models import Disease, Pest
    names = set()
    for model in (Pest, Disease):
        for en, sw in model.objects.values_list('name_en', 'name_sw'):
            for n in (en, sw):
                n = (n or '').strip().lower()
                if len(n) >= 6:
                    names.add(n)
    return names


def check(text, evidence):
    """None = salama; vinginevyo sababu ya kukataa."""
    from bot.writer import validate
    if not text or len(text.strip()) < 3:
        return 'jibu tupu'
    why = validate(text, evidence) if len(text) >= 40 else None
    if why and not why.startswith('fupi'):
        return why
    low_t, low_e = text.lower(), evidence.lower()
    for name in _cause_names():
        if name in low_t and name not in low_e:
            return f'jina la tatizo lisilotoka kwenye zana: {name}'
    if 'shikamoo' in low_t:
        return 'shikamoo'
    return None


def check_creator(text, question):
    """Aliyejenga mfumo anatajwa tu mtu akiuliza nani aliunda bot."""
    from bot.messages import asks_creator
    by = _built_by().lower()
    if by and by.split()[0] in (text or '').lower() and not asks_creator(question):
        return 'ametaja aliyejenga mfumo bila kuulizwa'
    return None


# ─────────────────────────── Mzunguko wa wakala ───────────────────────────

def _history(user, limit=6):
    from bot.models import Conversation
    rows = list(Conversation.objects.filter(user=user).order_by('-id')[:limit])
    rows.reverse()
    return [{'role': 'user' if r.message_direction == 'inbound' else 'assistant',
             'content': (r.raw_message or '')[:600]} for r in rows if r.raw_message]


def run(user, raw_message):
    """
    Rudisha:
      ('reply', jibu, trace)             — jibu lililokaguliwa
      ('diagnosis', crop, trace)         — kabidhi kwa uchunguzi wa kanuni
      None                               — AI haipo/imeshindwa/jibu limekataliwa → mfumo wa kanuni
    """
    from diagnosis import ai_layer
    history = _history(user)
    messages = [{'role': 'system', 'content': system_prompt()}] + history + \
               [{'role': 'user', 'content': raw_message}]
    evidence = [about()] + [m['content'] for m in history] + [raw_message]
    trace = {'mode': 'agent', 'tools': []}
    retried = False
    model = getattr(settings, 'GROQ_AGENT_MODEL', '') or None
    for _ in range(MAX_STEPS + 1):
        try:
            msg = ai_layer.chat_tools(messages, TOOLS, model=model)
        except TypeError:
            msg = ai_layer.chat_tools(messages, TOOLS)
        if not msg:
            trace['fail'] = 'AI haikujibu'
            return None
        calls = msg.get('tool_calls') or []
        if calls:
            messages.append({'role': 'assistant', 'content': msg.get('content') or '', 'tool_calls': calls})
            for call in calls:
                fn = (call.get('function') or {})
                name = fn.get('name', '')
                try:
                    args = json.loads(fn.get('arguments') or '{}')
                except (TypeError, ValueError):
                    args = {}
                args = {k: str(v) for k, v in (args or {}).items() if isinstance(k, str)}
                if name == 'anza_uchunguzi':
                    trace['tools'].append({'name': name, 'args': args})
                    trace['handoff'] = 'diagnosis'
                    return ('diagnosis', _crop(args.get('zao', ''), user) if args.get('zao') else None, trace)
                func = TOOL_FUNCS.get(name)
                try:
                    result = func(user, **{k: v for k, v in args.items()
                                           if k in func.__code__.co_varnames}) if func else \
                        {'matokeo': f'zana "{name}" haipo'}
                except Exception as exc:                      # zana isiangushe mazungumzo
                    logger.error("[agent] zana %s: %s", name, exc)
                    result = {'matokeo': 'hitilafu ya kusoma data'}
                content = json.dumps(result, ensure_ascii=False)[:6000]
                evidence.append(content)
                trace['tools'].append({'name': name, 'args': args, 'result': content[:300]})
                messages.append({'role': 'tool', 'tool_call_id': call.get('id', name), 'content': content})
            continue
        text = (msg.get('content') or '').strip()
        why = check(text, '\n'.join(evidence)) or check_creator(text, raw_message)
        if why is None:
            return ('reply', text, trace)
        trace.setdefault('rejected', []).append({'why': why, 'text': text[:400]})
        if retried:
            return None
        retried = True
        messages.append({'role': 'assistant', 'content': text})
        messages.append({'role': 'user', 'content': (
            f"[UKAGUZI WA MFUMO — si ujumbe wa mkulima] Jibu lako limekataliwa: {why}. Liandike upya ukitumia "
            "taarifa za zana na KUHUSU pekee, bila kuongeza namba, majina, miezi wala dawa.")})
    return None
