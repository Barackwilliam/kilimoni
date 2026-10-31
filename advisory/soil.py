"""
Ushauri wa udongo kwa kanuni (MHD-004 R1–R3)
=============================================

1. Kutambua udongo kwa maneno ya mkulima — visawe (Soil_Synonyms), majina ya
   kawaida ("udongo mwekundu", "kichanga", "tifutifu"), majina ya WRB; AI
   (orodha funge) ikiwa sentensi ni ndefu. Usipotambulika → RULE-SOIL-001:
   "Udongo wako unaonekana zaidi kama kichanga, tifutifu, mfinyanzi…?"
2. Udongo + zao → Soil_Crop_Suitability (score/100 na rating), kanuni kwa score:
     ≥ 85  RULE-SCROP-001 (unafaa)
     65–84 RULE-SCROP-002 (unafaa kwa masharti — maboresho)
     < 65  hatua_ya_AI ya record ("usipendekeze bila maboresho/taarifa zaidi")
   Zao bila tathmini kwa udongo huo → udongo bora wa zao (Crop_Top_Soil_Ranking).
3. Sifa za udongo (R2), changamoto zake (Soil_Constraint_Master) na hatua za
   usimamizi — kwa Kiswahili rahisi (kamusi ya plain.py).
"""
import re

from diagnosis import plain

from .models import AdvisoryRule, ExplainTemplate, SoilConstraint, SoilRanking, SoilSuitability, SoilSynonym, SoilType

STOP = {'udongo', 'wa', 'ya', 'na', 'wenye', 'uliovuja', 'virutubisho', 'soil', 'mzito', 'nyingi', 'sana',
        'kidogo', 'mwingi', 'mchanga', 'aluminium', 'mweusi', 'mzuri'}
DISCLAIMER = "_Ushauri huu unatokana na taarifa za kitaalamu za Kilimoni AI; kipimo cha udongo kinatoa uhakika zaidi._"
HIGH, MEDIUM = 85, 65


def _norm(text):
    return ' '.join(re.findall(r"[a-z0-9']+", (text or '').lower()))


def _clean(text):
    return plain.clean(text or '')[0]


def _variants(text):
    """'Udongo mwekundu/tindikali' → {'udongo mwekundu/tindikali', 'udongo mwekundu', 'udongo tindikali'}."""
    out = set()
    t = _norm(text.replace('/', ' / ')) if text else ''
    if not t:
        return out
    out.add(_norm(text))
    if '/' in (text or ''):
        head, *alts = [p.strip() for p in text.split('/')]
        out.add(_norm(head))
        prefix = ' '.join(head.split()[:-1])
        for a in alts:
            out.add(_norm(f"{prefix} {a}" if prefix and len(a.split()) == 1 else a))
    return {v for v in out if len(v) >= 4}


def _index():
    """term → soil. Maneno ya neno moja yanatumika tu yakiwa ya udongo mmoja (yasiyo na utata)."""
    soils = list(SoilType.objects.filter(is_active=True))
    terms = {}
    for s in soils:
        for text in (s.name_sw, s.farmer_name, s.wrb_name):
            for v in _variants(text):
                terms.setdefault(v, set()).add(s.pk)
    for syn in SoilSynonym.objects.filter(is_active=True):
        for v in _variants(syn.term):
            terms.setdefault(v, set()).add(syn.soil_id)
    words = {}
    for s in soils:
        for w in set(_norm(f"{s.name_sw} {s.farmer_name}").split()) - STOP:
            if len(w) >= 5:
                words.setdefault(w, set()).add(s.pk)
    for w, ids in words.items():
        if len(ids) == 1 and w not in terms:
            terms[w] = ids
    by_id = {s.pk: s for s in soils}
    return {t: [by_id[i] for i in ids] for t, ids in terms.items() if len(ids) == 1}


FILLER = {'wangu', 'yangu', 'langu', 'wetu', 'ni', 'huu', 'shambani', 'kwangu', 'sana', 'kweli'}


def identify(text, state=None):
    # "udongo wangu ni wa kichanga" → "udongo wa kichanga" (maneno ya kujaza yanaondolewa)
    words = _norm(text).split()
    low = f" {' '.join(w for w in words if w not in FILLER)} "
    best = None
    for term, soils in _index().items():
        if re.search(r'(?<![a-z])' + re.escape(term) + r'(?![a-z])', low) and (best is None or len(term) > len(best[0])):
            best = (term, soils[0])
    if best:
        return best[1]
    if len(low.split()) >= 4:
        from diagnosis import ai_layer
        options = {s.source_id: f"{s.name_sw}; {s.farmer_name}; {s.description_sw}"[:200]
                   for s in SoilType.objects.filter(is_active=True)}
        code = ai_layer.match_option(text, options, state, step='soil')
        return SoilType.objects.filter(source_id=code).first() if code else None
    return None


def wants_soil(text):
    low = _norm(text)
    return 'udongo' in low.split() or 'soil' in low.split() or identify_quick(text) is not None


def identify_quick(text):
    low = f" {' '.join(w for w in _norm(text).split() if w not in FILLER)} "
    for term, soils in _index().items():
        if ' ' in term and term in low:
            return soils[0]
    return None


def _rule(source_id):
    return AdvisoryRule.objects.filter(source_id=source_id, is_active=True).first()


def ask_soil_message():
    r = _rule('RULE-SOIL-001')
    q = _clean(r.farmer_message_sw) if r else 'Udongo wako unaonekana zaidi kama kichanga, tifutifu, mfinyanzi au mweusi?'
    return f"🟤 Sawa, tuangalie udongo wako.\n\n{q.rstrip('.')}\n_Mfano: udongo wa kichanga, au udongo mwekundu_"


def _soil_rules(soil):
    """
    Kanuni za udongo ambazo trigger yake inautaja udongo huu kwa JINA KAMILI
    ("udongo wa kichanga", "Acrisols") — si kwa neno moja, ili "tifutifu wa
    kichanga" isipewe kanuni za "udongo wa kichanga". Pasi ya pili: kanuni
    zinazotaja WRB sawa (mf. kichanga ↔ Arenosols kwenye RULE-SOIL-002).
    """
    names = {_norm(n) for n in (soil.name_sw, soil.wrb_name) if n}
    rules = list(AdvisoryRule.objects.filter(module='soil', is_active=True))
    out = [r for r in rules if any(n and n in _norm(r.trigger) for n in names)]
    groups = _equivalent_groups(soil, out)
    for r in rules:
        if r not in out and any(g in _norm(r.trigger) for g in groups):
            out.append(r)
    return out


def _equivalent_groups(soil, rules):
    """WRB za udongo huu: jina lake + WRB zinazotajwa pamoja nao kwenye trigger ya kanuni (mf. kichanga ↔ Arenosols)."""
    groups = {soil.wrb_name.lower()} if soil.wrb_name else set()
    for r in rules:
        groups |= {g.lower() for g in re.findall(r'\b([A-Z][a-z]+sols)\b', r.trigger)}
    return groups


def suitability(soil, crop):
    return SoilSuitability.objects.filter(soil=soil, crop=crop, is_active=True).first() if crop else None


def advise(crop, text, state=None, soil=None):
    trace = {'mode': 'soil_advisor', 'crop': crop.crop_name_sw if crop else ''}
    soil = soil or identify(text, state)
    if state and state.get('ai'):
        trace['ai'] = state['ai']
    if soil is None:
        trace.update({'decision': 'need_soil', 'rules_used': ['RULE-SOIL-001']})
        return ask_soil_message(), trace

    rules = _soil_rules(soil)
    used = [soil.source_id] + [r.source_id for r in rules]
    trace.update({'soil': soil.source_id, 'soil_name': soil.name_sw})
    title = soil.name_sw + (f" ({soil.wrb_name})" if soil.wrb_name else '')
    lines = [f"🟤 *Udongo: {title}*"]
    if soil.farmer_name and soil.farmer_name.lower() not in soil.name_sw.lower():
        lines.append(f"_Kwa jina la kawaida: {soil.farmer_name}_")
    if soil.description_sw:
        lines += ['', _clean(soil.description_sw)]

    decision = 'soil_info'
    if crop:
        s = suitability(soil, crop)
        if s and s.score is not None:
            used.append(s.source_id)
            lines += ['', f"*Ufaafu wa {crop.crop_name_sw} kwenye udongo huu:* {s.rating} ({s.score}/100)"]
            if s.score >= HIGH:
                decision, rid, tpl_hint = 'suitable', 'RULE-SCROP-001', 'juu'
            elif s.score >= MEDIUM:
                decision, rid, tpl_hint = 'suitable_with_conditions', 'RULE-SCROP-002', 'wastani'
            else:
                decision, rid, tpl_hint = 'not_suitable_without_improvement', None, None
            r = _rule(rid) if rid else None
            if r:
                lines.append(_clean(r.farmer_message_sw))
                used.append(r.source_id)
            elif decision == 'not_suitable_without_improvement':
                lines.append(f"Si vyema kupanda {crop.crop_name_sw} kwenye udongo huu bila maboresho au "
                             "taarifa zaidi (kama kipimo cha udongo).")
            if s.reason_sw:
                lines.append(f"• Sababu: {_clean(s.reason_sw).rstrip('.')}")
            if s.improvements_sw and decision != 'suitable':
                lines.append(f"• Kabla ya kupanda: {_clean(s.improvements_sw).rstrip('.')}")
            if tpl_hint:
                t = ExplainTemplate.objects.filter(module='soil', is_active=True,
                                                   situation__icontains=tpl_hint).first()
                if t:
                    try:
                        why = _clean(t.template_sw.format(crop=crop.crop_name_sw, soil=soil.name_sw, score=s.score,
                                                         reason=s.reason_sw, improvement=s.improvements_sw))
                        lines += ['', f"*Kwa nini:* {why}"]
                        used.append(t.source_id)
                    except (KeyError, IndexError):
                        pass
            trace.update({'score': s.score, 'rating': s.rating})
        else:
            decision = 'no_assessment'
            lines += ['', f"Bado sina tathmini ya ufaafu wa *{crop.crop_name_sw}* kwa udongo huu, "
                          "kwa hiyo sitakisia."]
            ranks = SoilRanking.objects.filter(crop=crop, is_active=True).order_by('rank')[:3]
            if ranks:
                lines.append(f"Kwa {crop.crop_name_sw}, udongo unaofaa zaidi kwenye taarifa zetu ni: " +
                             ', '.join(f"{r.soil_wrb} ({r.score}/100)" for r in ranks) + '.')
                used += [r.source_id for r in ranks]

    prop = soil.properties.filter(is_active=True).first()
    if prop:
        facts = [(l, v) for l, v in (('Kiwango cha tindikali (pH)', prop.ph_tendency), ('Mboji/viumbe hai', prop.organic_matter),
                                     ('Kushika maji', prop.water_holding), ('Rutuba', prop.fertility),
                                     ('Mtiririko wa maji', prop.drainage)) if v]
        if facts:
            lines += ['', '*Sifa za udongo huu:*'] + [f"• {l}: {_clean(v).rstrip('.')}" for l, v in facts]
        if prop.management:
            lines += ['', f"*Usimamizi unaoshauriwa:* {_clean(prop.management)}"]
        used.append(prop.source_id)

    shown = []
    for r in rules:
        msg = _clean(r.farmer_message_sw)
        if msg and r.source_id != 'RULE-SOIL-001' and not any(msg[:45] == m[:45] for m in shown):
            lines += ['', f"💡 {msg}"]
            shown.append(msg)
    groups = _equivalent_groups(soil, rules)
    for c in SoilConstraint.objects.filter(is_active=True):
        if groups & {g.lower() for g in c.soil_groups}:
            lines += ['', f"⚠️ *{c.name_sw}:* {_clean(c.message_sw)}"]
            if c.farmer_signs_sw:
                lines.append(f"_Dalili zake shambani: {_clean(c.farmer_signs_sw).rstrip('.')}._")
            used.append(c.source_id)
    lines += ['', DISCLAIMER]
    trace.update({'decision': decision, 'rules_used': list(dict.fromkeys(used))})
    return '\n'.join(lines), trace
