"""
Ushauri wa mbegu kwa kanuni (MHD-003A, ukitumia eneo la MHD-001)
================================================================

Mtiririko (AI_Conversation_Flow ya dataset):

  1. Zao       — bot inajua zao (au inauliza, kama kawaida).
  2. Eneo      — RULE-AGR-001 / MHD003A-AI-005: HAKUNA jina la mbegu kabla ya
                 eneo. Eneo linatoka kwenye ujumbe au profile ya mkulima
                 (User.ward / aez_code). Mkoa wenye kanda nyingi → uliza wilaya/kata.
  3. Kigezo    — Farmer_Intent_Mapping (mapema, mavuno mengi…), kwa maneno ya
                 dataset au AI (orodha funge).
  4. Uamuzi    — Varieties zinazofaa = zile zenye AEZ ya mkulima kwenye
                 AEZ_zinazofaa (Release 2). Mpangilio:
                   a) AI_Decision_Engine (Release 3) inayolingana na AEZ + kigezo
                   b) RULE-AGR-002: mvua chache → za mapema kwanza
                   c) vinginevyo kwa siku za kukomaa
                 Variety isiyo na sifa za kilimo (Release 2) HAIPENDEKEZWI.
  5. Maelezo   — Explainability_Templates ({variety}, {rainfall_band}…) na
                 Confidence_Engine (High → bila tahadhari; Medium → tahadhari).

Mkulima akitaja mbegu ("SC 403 inafaa Kondoa?"): RULE-SEEDREG-001/002 —
inatambuliwa kupitia visawe, kisha inalinganishwa na kanda yake.
"""
import re

from diagnosis import plain

from .models import (
    AdvisoryConfidenceBand, AdvisoryRule, Aez, ExplainTemplate, SeedDecisionRule, SeedIntent,
    VarietyAgronomy, VarietyRegistry, VarietySynonym,
)

SEED_STEMS = ('mbegu', 'variety', 'varieti', 'hybrid', 'aina gani', 'aina ya mahindi', 'aina bora')
LOW_RAIN_MAX_MM = 800          # AEZ ambayo kiwango cha juu cha mvua ≤ hiki = "mvua chache" (RULE-AGR-002)
NO_RULE_CONFIDENCE = 0.80      # Hakuna AI_Decision_Engine inayolingana — Confidence_Engine "Medium"
DISCLAIMER = "_Ushauri huu unatokana na taarifa za kitaalamu za Kilimoni AI; nunua mbegu halisi iliyothibitishwa._"
VERIFY_NOTE = ("Kabla ya kununua, thibitisha na afisa ugani au muuzaji wa pembejeo aliyesajiliwa kwamba "
               "mbegu hii inapatikana na inafaa shamba lako.")


def _norm(text):
    return ' '.join(re.findall(r"[a-z0-9']+", (text or '').lower()))


def _key(text):
    return re.sub(r'[^a-z0-9]', '', (text or '').lower())


def _clean(text):
    return plain.clean(text or '')[0]


# ─────────────────────────── Kutambua ombi ───────────────────────────

def has_data(crop):
    return bool(crop) and VarietyAgronomy.objects.filter(crop=crop, is_active=True).exists()


def mentioned_variety(text, crop=None):
    """Variety iliyotajwa (kwa visawe vya dataset: 'sc 403', 'sc-403', 'sc403'), au None."""
    compact = _key(text)
    if not compact:
        return None
    qs = VarietySynonym.objects.filter(is_active=True).select_related('variety')
    if crop:
        qs = qs.filter(variety__crop=crop)
    best = None
    for syn in qs:
        k = _key(syn.term)
        if len(k) >= 4 and re.search(r'(?<![a-z0-9])' + re.escape(k) + r'(?![0-9])', compact) \
                and (best is None or len(k) > len(_key(best.term))):
            best = syn
    if best is None:
        # Jina la variety lenyewe (bila kisawe)
        for v in VarietyRegistry.objects.filter(is_active=True, **({'crop': crop} if crop else {})):
            k = _key(v.name)
            if len(k) >= 4 and k in compact:
                return v
        return None
    return best.variety


def wants_seed(text, intent=None):
    low = _norm(text)
    if any(s in low for s in SEED_STEMS):
        return True
    if intent is not None and getattr(intent, 'intent_name', '') in ('variety_by_location', 'seed_selection'):
        return True
    return mentioned_variety(text) is not None


def detect_criterion(text, state=None, use_ai=True):
    """Farmer_Intent_Mapping kwa maneno ya dataset; AI (orodha funge) ikiwa sentensi ni ndefu."""
    low = _norm(text)
    words = set(low.split())
    best, best_score = None, 0
    for it in SeedIntent.objects.filter(is_active=True):
        for phrase in it.phrases:
            p = _norm(phrase)
            pw = {w for w in p.split() if len(w) > 3}
            if p and p in low:
                return it
            score = len(pw & words) / len(pw) if pw else 0
            if score >= 0.6 and score > best_score:
                best, best_score = it, score
    if best or len(low.split()) < 4 or not use_ai:
        return best
    from diagnosis import ai_layer
    options = {it.intent_code: '; '.join(it.phrases) for it in SeedIntent.objects.filter(is_active=True)}
    code = ai_layer.match_option(text, options, state, step='seed_criterion')
    return SeedIntent.objects.filter(intent_code=code).first() if code else None


# ─────────────────────────── Eneo ───────────────────────────

def location_from_user(user):
    if not user or not user.aez_code:
        return None
    aez = Aez.objects.filter(source_id=user.aez_code).first()
    if not aez:
        return None
    return {'level': 'ward' if user.ward else 'district', 'ward': user.ward, 'district': user.district,
            'region': user.region, 'aez_id': aez.source_id, 'aez_name': aez.name_sw, 'from_profile': True}


def _place(loc):
    if loc.get('ward'):
        return f"{loc['ward']}, {loc['district']}"
    return loc.get('district') or loc.get('region') or ''


def _rule_msg(rule_id, default):
    r = AdvisoryRule.objects.filter(source_id=rule_id, is_active=True).first()
    return _clean(r.farmer_message_sw) if r and r.farmer_message_sw else default


def ask_location_message(variety=None, loc=None):
    if variety:
        head = f"Nimetambua mbegu uliyoitaja: *{variety.name}*. 🌱"
        body = _rule_msg('RULE-SEEDREG-002', "Tafadhali taja mkoa, wilaya au kata yako ili nilinganishe "
                                             "mbegu hii na mazingira yako.")
    else:
        head = "Sawa, nitakusaidia kuchagua mbegu. 🌱"
        body = _rule_msg('RULE-AGR-001', "Tafadhali taja mkoa, wilaya au kata yako ili nichague mbegu "
                                         "inayofaa mazingira yako.")
    if loc and loc.get('level') == 'region' and not loc.get('aez_id'):
        body = (f"Mkoa wa *{loc['region']}* una kanda za kilimo zaidi ya moja, kwa hiyo mbegu zinazofaa "
                "zinatofautiana. Tafadhali taja *wilaya au kata* yako.")
    return f"{head}\n\n{body}\n_Mfano: Kondoa, au kata ya Changaa_"


# ─────────────────────────── Uamuzi ───────────────────────────

def _band_max(text):
    nums = [int(n) for n in re.findall(r'\d{2,5}', text or '')]
    return max(nums) if nums else None


def _band_span(text):
    nums = [int(n) for n in re.findall(r'\d{2,5}', text or '')]
    return (nums[0], nums[-1]) if nums else (None, None)


def _rule_matches_criterion(rule, criterion):
    """
    Kanuni inatumika kama kigezo chake kinalingana na kigezo cha mkulima.
    Kigezo cha kanuni kinatafsiriwa kwa Farmer_Intent_Mapping ileile
    ("anataka mbegu ya kukomaa mapema" → early_maturity). Mkulima asipotaja
    kigezo, kanuni ya kanda yake inatumika (ndiyo ushauri wa msingi wa eneo).
    """
    if criterion is None or not rule.farmer_criterion:
        return True
    rule_intent = detect_criterion(rule.farmer_criterion, use_ai=False)
    return rule_intent is None or rule_intent.pk == criterion.pk


def decide(crop, aez, criterion=None):
    """Rudisha dict ya uamuzi (bila maandishi) — inatumika na advise() na tests."""
    profiles = list(VarietyAgronomy.objects.filter(crop=crop, is_active=True))
    suitable = [p for p in profiles if aez.source_id in p.aez_codes]
    excluded = [{'variety': p.name, 'reason': f"{aez.source_id} haipo kwenye AEZ_zinazofaa ({', '.join(p.aez_codes)})"}
                for p in profiles if p not in suitable]
    rain_max = _band_max(aez.rainfall_band_mm)
    low_rain = rain_max is not None and rain_max <= LOW_RAIN_MAX_MM

    rules = [r for r in SeedDecisionRule.objects.filter(crop=crop, is_active=True)
             if aez.source_id in r.aez_codes and r.priority_varieties]
    rule = next((r for r in sorted(rules, key=lambda r: -(r.confidence or 0))
                 if _rule_matches_criterion(r, criterion)), None)

    by_key = {_key(p.name): p for p in suitable}
    ranked, used = [], []
    if rule:
        for name in rule.priority_varieties:
            p = by_key.get(_key(name))
            if p and p not in ranked:
                ranked.append(p)
        used.append(rule.source_id)
    rest = sorted((p for p in suitable if p not in ranked),
                  key=lambda p: (p.maturity_days_max or 999, p.name))
    ranked += rest
    if low_rain and not rule:
        used.append('RULE-AGR-002')

    confidence = rule.confidence if rule and rule.confidence else NO_RULE_CONFIDENCE
    band = AdvisoryConfidenceBand.objects.filter(module='seed', is_active=True,
                                                 min_score__lte=confidence + 1e-9,
                                                 max_score__gte=confidence - 1e-9).first()
    # Mwinuko: onyo kama kanda iko nje kabisa ya mwinuko wa variety
    alt_lo, alt_hi = _band_span(aez.altitude_band_m)
    alt_notes = {}
    for p in ranked:
        if p.altitude_min and p.altitude_max and alt_lo and alt_hi and (alt_lo > p.altitude_max or alt_hi < p.altitude_min):
            alt_notes[p.name] = f"mwinuko wa kanda ({aez.altitude_band_m} m) uko nje ya {p.altitude_min}–{p.altitude_max} m"
    suggested_missing = []
    if criterion:
        known = {_key(p.name) for p in profiles}
        suggested_missing = [s for s in criterion.suggested if re.search(r'\d', s) and _key(s) not in known]
    return {'ranked': ranked, 'excluded': excluded, 'rule': rule, 'low_rain': low_rain,
            'confidence': confidence, 'band': band.label if band else '', 'rules_used': used,
            'criterion': criterion.intent_code if criterion else None, 'alt_notes': alt_notes,
            'suggested_missing': suggested_missing}


def _explain(top, aez, low_rain):
    tpls = list(ExplainTemplate.objects.filter(module='seed', is_active=True))
    tpl = None
    if low_rain:
        tpl = next((t for t in tpls if 'mvua chache' in t.situation.lower()), None)
    tpl = tpl or next((t for t in tpls if 'kawaida' in t.situation.lower()), None) or (tpls[0] if tpls else None)
    if not tpl:
        return '', None
    values = {'variety': top.name, 'rainfall_band': f"mvua ya {aez.rainfall_band_mm} mm kwa mwaka",
              'altitude_band': f"mwinuko wa {aez.altitude_band_m} m", 'maturity_days': top.days_text}
    try:
        return _clean(tpl.template_sw.format(**values)), tpl.source_id
    except (KeyError, IndexError):
        return '', None


def _variety_line(i, p):
    bits = [f"{i}. *{p.name}*"]
    if p.days_text:
        bits.append(f"— hukomaa {p.days_text}" + (f" ({p.maturity_class.lower()})" if p.maturity_class else ''))
    line = ' '.join(bits)
    extra = []
    if p.yield_text:
        extra.append(f"Mavuno: {_clean(p.yield_text).rstrip('.')}")
    if p.drought_tolerance and 'uchujwe' not in p.drought_tolerance.lower():
        extra.append(_clean(p.drought_tolerance).rstrip('.'))
    if extra:
        line += '\n   ' + '; '.join(e for e in extra if e)
    return line


def advise(crop, loc, text, state=None, variety=None):
    """
    Rudisha (jibu, trace). loc = dict ya eneo (location.resolve au profile).
    Kama eneo/AEZ halijulikani → jibu ni swali la eneo na trace['decision']='need_location'.
    """
    trace = {'mode': 'seed_advisor', 'crop': crop.crop_name_sw if crop else ''}
    if variety is None:
        variety = mentioned_variety(text, crop)
    if variety:
        trace['variety'] = variety.source_id
    if not loc or not loc.get('aez_id'):
        trace.update({'decision': 'need_location', 'rules_used': ['RULE-AGR-001', 'MHD003A-AI-005']
                      + (['RULE-SEEDREG-002'] if variety else [])})
        return ask_location_message(variety, loc), trace

    aez = Aez.objects.get(source_id=loc['aez_id'])
    criterion = detect_criterion(text, state)
    d = decide(crop, aez, criterion)
    trace.update({'location': _place(loc), 'aez': aez.source_id, 'criterion': d['criterion'],
                  'low_rain': d['low_rain'], 'confidence': d['confidence'], 'band': d['band'],
                  'recommended': [p.name for p in d['ranked'][:3]], 'excluded': d['excluded'],
                  'rules_used': list(d['rules_used'])})
    if state and state.get('ai'):
        trace['ai'] = state['ai']
    place = _place(loc)
    header = (f"🌽 *Mbegu za {crop.crop_name_sw} — {place}*\n"
              f"_{aez.name_sw} · mvua {aez.rainfall_band_mm} mm · mwinuko {aez.altitude_band_m} m_")

    # ── Mkulima ametaja mbegu ──
    if variety:
        trace['rules_used'] = ['RULE-SEEDREG-001']
        prof = next((p for p in VarietyAgronomy.objects.filter(variety=variety, is_active=True)), None)
        ok = prof is not None and aez.source_id in prof.aez_codes
        trace['decision'] = 'variety_fits' if ok else ('variety_no_profile' if prof is None else 'variety_not_fit')
        lines = [header, '']
        if prof is None:
            lines.append(f"*{variety.name}* imesajiliwa ({variety.authority or 'sajili'}), lakini bado sina taarifa "
                         "za kilimo za kutosha kuilinganisha na eneo lako, kwa hiyo sitabahatisha.")
        elif ok:
            lines.append(f"✅ Ndiyo, *{variety.name}* imeorodheshwa kufaa kanda yako.")
            lines += ['', _variety_line(1, prof).replace('1. ', '', 1)]
            if prof.name in d['alt_notes']:
                lines.append(f"⚠️ Tahadhari: {d['alt_notes'][prof.name]}.")
            if prof.farmer_advice:
                lines += ['', _clean(prof.farmer_advice)]
        else:
            lines.append(f"⚠️ *{variety.name}* haijaorodheshwa kufaa {aez.name_sw} kwenye taarifa nilizonazo.")
        others = [p for p in d['ranked'] if not prof or p.pk != prof.pk][:3]
        if others and not ok:
            lines += ['', '*Mbegu zinazofaa kanda yako:*'] + [_variety_line(i, p) for i, p in enumerate(others, 1)]
        lines += ['', DISCLAIMER]
        return '\n'.join(lines), trace

    # ── Pendekezo ──
    top3 = d['ranked'][:3]
    if not top3:
        trace['decision'] = 'no_suitable_variety'
        return (f"{header}\n\nKwa sasa sina mbegu ya {crop.crop_name_sw} iliyoorodheshwa kufaa {aez.name_sw} "
                "kwenye taarifa nilizonazo, kwa hiyo sitabahatisha jina. 🌱\n\n"
                "📞 Wasiliana na afisa ugani wa kata yako kwa ushauri wa mbegu za eneo lako."), trace

    trace['decision'] = 'recommended'
    lines = [header, '']
    if d['rule'] and d['rule'].farmer_message_sw:
        lines += [_clean(d['rule'].farmer_message_sw), '']
    elif d['low_rain']:
        lines += [_rule_msg('RULE-AGR-002', 'Kwa eneo lenye mvua chache au msimu mfupi, mbegu za mapema zinafaa zaidi.'), '']
    lines.append('*Mbegu zinazofaa, kwa mpangilio wa kipaumbele:*')
    for i, p in enumerate(top3, 1):
        lines.append(_variety_line(i, p))
        if p.name in d['alt_notes']:
            lines.append(f"   ⚠️ {d['alt_notes'][p.name]}")
    why, tpl_id = _explain(top3[0], aez, d['low_rain'])
    if why:
        lines += ['', f"*Kwa nini:* {why}"]
        trace['rules_used'].append(tpl_id)
    if top3[0].farmer_advice:
        lines += ['', f"💡 {_clean(top3[0].farmer_advice)}"]
    if d['suggested_missing']:
        lines += ['', f"_({', '.join(d['suggested_missing'])} bado hazina taarifa kamili za kilimo kwenye mfumo, "
                      "kwa hiyo sijazipendekeza.)_"]
    if d['band'].lower() != 'high':
        lines += ['', f"ℹ️ {VERIFY_NOTE}"]
    lines += ['', DISCLAIMER]
    return '\n'.join(lines), trace
