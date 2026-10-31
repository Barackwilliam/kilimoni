"""
Mzunguko wa mazao kwa kanuni (MHD-006 R4)
=========================================

Maswali yanayoshughulikiwa:
  • "Baada ya mahindi nipande nini?"      → zao la awali pekee
  • "Nipande mpunga baada ya mahindi?"    → zao la awali + linalofuata
  • "Mzunguko wa mazao"                   → mifuatano ya kanda ya mkulima

Uamuzi:
  1. Rotation_Compatibility_Master (score/100, rating, AI_action) — chanzo kikuu.
  2. ROTRULE-001 (zao lilelile) na ROTRULE-002 (familia moja, kutoka
     Crop_Rotation_Family_Master) — hata bila record ya ulinganifu.
  3. Pest_Disease_Break_Rules — mazao yote mawili yakitajwa kwenye kanuni
     hiyo (mf. nyanya baada ya viazi).
  4. Rotation_Sequence_Master ya kanda ya mkulima (AEZ kupitia ulinganisho
     wa MHD-006 → MHD-001) — zao linalofuata kwenye mfuatano.
  5. Soil_Fertility_Rotation_Rules — udongo ukitajwa (MHD-004): kichanga →
     SOILROT-002; mboji/organic matter ndogo → SOILROT-001.
"""
import re

from diagnosis import plain

from .models import (
    AdvisoryRule, CropFamily, ExplainTemplate, RotationCompatibility, RotationRule, RotationSequence,
)

ROT_STEMS = ('mzunguko', 'kubadilisha mazao', 'kubadilishana mazao', 'rotation', 'nipande nini baada',
             'zao gani baada', 'nini baada ya', 'gani baada ya', 'kufuata baada')
RATING_SW = {'low': 'chini', 'medium': 'ya wastani', 'high': 'juu'}
DISCLAIMER = "_Ushauri huu unatokana na taarifa za kitaalamu za Kilimoni AI; si mbadala wa afisa ugani._"
GOOD = 70
# Msamiati tu (majina ya mazao kwa Kiswahili) ili kuyatambua kwenye ujumbe —
# hakuna ushauri unaotokana na orodha hii; ushauri wote unatoka kwenye data.
CROP_WORDS = {'mahindi', 'mpunga', 'maharage', 'njegere', 'viazi', 'nyanya', 'hoho', 'pilipili', 'tumbaku',
              'kabichi', 'mtama', 'ulezi', 'uwele', 'alizeti', 'ufuta', 'mihogo', 'muhogo', 'ndizi', 'karanga',
              'kunde', 'choroko', 'mbaazi', 'ngano', 'shayiri', 'vitunguu', 'karoti', 'tikiti', 'pamba', 'kahawa',
              'chai', 'korosho', 'soya', 'dengu', 'mboga', 'bamia', 'biringanya', 'matango', 'sukuma'}


def _norm(text):
    return ' '.join(re.findall(r"[a-z0-9']+", (text or '').lower()))


def _clean(text):
    return plain.clean(text or '')[0]


def _parts(name):
    """'Maharage/Njegere' → ['maharage', 'njegere']; 'Viazi mviringo au mboga' → [...]."""
    return [p.strip().lower() for p in re.split(r'/| au |,', name or '') if p.strip()]


def lexicon():
    """Majina ya mazao yanayojulikana kwenye data ya mzunguko + Mazao ya mfumo."""
    from crops.models import Crop
    names = set()
    for c in Crop.objects.all():
        names.add(c.crop_name_sw.lower())
    for f in CropFamily.objects.filter(is_active=True):
        names.add(f.crop_name.lower())
    for r in RotationCompatibility.objects.filter(is_active=True):
        names |= {r.previous_name.lower(), r.next_name.lower()}
    for s in RotationSequence.objects.filter(is_active=True):
        for season in s.seasons:
            names |= {p.split()[0] for p in _parts(season)}
    return {n for n in names | CROP_WORDS if len(n) >= 3}


def mentioned(text):
    """Mazao yaliyotajwa, kwa mpangilio wa kuonekana."""
    low = _norm(text)
    found = []
    for name in lexicon():
        m = re.search(r'(?<![a-z])' + re.escape(name) + r'(?![a-z])', low)
        if m:
            found.append((m.start(), name))
    return [n for _, n in sorted(found)]


def parse(text):
    """Rudisha (zao_la_awali, zao_linalofuata)."""
    low = _norm(text)
    crops = mentioned(text)
    prev = nxt = None
    m = re.search(r'baada ya ([a-z]+)', low)
    if m and m.group(1) in crops:
        prev = m.group(1)
    elif crops and re.search(r'(nimevuna|nilipanda|nililima|nimetoka kulima|msimu uliopita)', low):
        prev = crops[0]
    others = [c for c in crops if c != prev]
    if others:
        nxt = others[0]
    elif prev and low.count(prev) >= 2:
        nxt = prev                                  # "mahindi baada ya mahindi"
    return prev, nxt


def wants_rotation(text):
    low = _norm(text)
    if any(s in low for s in ROT_STEMS):
        return True
    m = re.search(r'baada ya ([a-z]+)', low)          # "baada ya mahindi" — si "baada ya mvua"
    return bool(m and m.group(1) in lexicon())


def _family(name):
    return CropFamily.objects.filter(crop_name__iexact=name, is_active=True).first()


def _arule(sid):
    return AdvisoryRule.objects.filter(source_id=sid, is_active=True).first()


def _tpl(key, **values):
    t = ExplainTemplate.objects.filter(module='rotation', is_active=True, situation__iexact=key).first()
    if not t:
        return '', None
    try:
        return _clean(t.template_sw.format(**values)), t.source_id
    except (KeyError, IndexError):
        return '', None


def _break_rules(prev, nxt):
    """Kanuni za kuvunja mzunguko wa magonjwa zinazotaja mazao yote mawili."""
    out = []
    for r in RotationRule.objects.filter(kind='break', is_active=True):
        words = set(_norm(r.farmer_message_sw).split())
        if prev in words and nxt in words:
            out.append(r)
    return out


def _soil_rules(text, state):
    from . import soil as soil_mod
    words = set(_norm(text).split())
    s = soil_mod.identify(text, state) if 'udongo' in words else None
    # "kichanga" = sandy (Soil_Local_Texture_Registry: Sandy soil → Udongo wa kichanga)
    sandy = 'kichanga' in words or (s is not None and 'kichanga' in s.name_sw.lower())
    out = []
    for r in RotationRule.objects.filter(kind='soil', is_active=True):
        cond = r.condition.lower()
        if ('sandy' in cond and sandy) or (s and s.wrb_name and s.wrb_name.lower() in cond):
            out.append(r)
        elif 'organic matter' in cond:
            low_om = re.search(r'(mboji|organic matter|rutuba)\s*(ndogo|kidogo|chache|chini)', _norm(text))
            prop = s.properties.first() if s else None
            if low_om or (prop and prop.organic_matter.lower().startswith('chini')):
                out.append(r)
    return out


def advise(text, loc=None, state=None):
    prev, nxt = parse(text)
    trace = {'mode': 'rotation_advisor', 'previous': prev, 'next': nxt}
    used, lines = [], []

    if not prev and not nxt:
        trace['decision'] = 'need_crop'
        return ("🔄 Sawa, tuangalie mzunguko wa mazao.\n\nNi *zao gani ulilopanda (au kuvuna) msimu uliopita*?\n"
                "_Mfano: baada ya mahindi nipande nini?_"), trace
    if nxt and not prev:
        prev, nxt = nxt, None                      # "mzunguko wa mahindi" → zao la awali
        trace.update({'previous': prev, 'next': None})

    pf = _family(prev)
    title = f"🔄 *Mzunguko: {nxt.capitalize()} baada ya {prev.capitalize()}*" if nxt else \
        f"🔄 *Nipande nini baada ya {prev.capitalize()}?*"
    lines.append(title)
    if pf:
        used.append(pf.source_id)

    decision = None
    if nxt:
        comp = RotationCompatibility.objects.filter(previous_name__iexact=prev, next_name__iexact=nxt,
                                                    is_active=True).first()
        nf = _family(nxt)
        same_crop = prev == nxt
        same_family = bool(pf and nf and pf.botanical_family and pf.botanical_family == nf.botanical_family)
        if comp and comp.score is not None:
            used.append(comp.source_id)
            rating = RATING_SW.get(comp.rating.lower(), comp.rating)
            decision = 'recommended' if comp.score >= GOOD else 'avoid'
            lines += ['', f"*Ulinganifu:* {rating} ({comp.score}/100)" +
                      (f" — {_clean(comp.ai_action).rstrip('.')}" if comp.ai_action else '')]
            if comp.risk_logic and decision == 'avoid':
                lines.append(f"• Hatari: {_clean(comp.risk_logic).rstrip('.')}")
            if comp.benefit_logic and decision == 'recommended':
                lines.append(f"• Faida: {_clean(comp.benefit_logic).rstrip('.')}")
        elif same_crop or same_family or _break_rules(prev, nxt):
            decision = 'avoid'
        else:
            decision = 'no_assessment'
            lines += ['', f"Bado sina tathmini ya *{nxt}* baada ya *{prev}*, kwa hiyo sitakisia."]
        for cond, rid in ((same_crop, 'ROTRULE-001'), (same_family and not same_crop, 'ROTRULE-002')):
            r = _arule(rid) if cond else None
            if r:
                lines.append(f"⚠️ {_clean(r.farmer_message_sw)}")
                used.append(r.source_id)
        if decision == 'avoid' and (same_family or same_crop):
            why, tid = _tpl('Avoid same family', previous_crop=prev, next_crop=nxt,
                            botanical_family=pf.botanical_family if pf else '')
            if why:
                lines += ['', f"*Kwa nini:* {why}"]
                used.append(tid)
        elif decision == 'recommended' and comp:
            why, tid = _tpl('Recommended rotation', previous_crop=prev, next_crop=nxt,
                            benefit_logic=_clean(comp.benefit_logic).rstrip('.'))
            if why:
                lines += ['', f"*Kwa nini:* {why}"]
                used.append(tid)
        for r in _break_rules(prev, nxt):
            lines += ['', f"🦠 {_clean(r.farmer_message_sw)}"]
            used.append(r.source_id)
            decision = 'avoid'

    # Mapendekezo: mfuatano wa kanda + ulinganifu wa juu kutoka zao la awali
    suggestions = []
    seqs = RotationSequence.objects.filter(is_active=True)
    if loc and loc.get('aez_id'):
        seqs = seqs.filter(aez__source_id=loc['aez_id'])
    for sq in seqs:
        parts = [_parts(x) for x in sq.seasons]
        for i, names in enumerate(parts[:-1]):
            if any(n.split()[0] == prev for n in names):
                suggestions.append((sq, sq.seasons[i + 1]))
                break
    good = list(RotationCompatibility.objects.filter(previous_name__iexact=prev, is_active=True,
                                                     score__gte=GOOD).order_by('-score')[:3])
    if suggestions or good:
        lines += ['', '*Mazao yanayopendekezwa kufuata:*']
        for sq, nxt_season in suggestions:
            zone = sq.aez.name_sw if sq.aez else sq.ext_aez_id
            lines.append(f"• *{nxt_season}* — mfuatano wa {zone}: {sq.system}")
            if sq.advisory_sw:
                lines.append(f"  _{_clean(sq.advisory_sw).rstrip('.')}._")
            used.append(sq.source_id)
        for c in good:
            lines.append(f"• *{c.next_name}* — ulinganifu {c.score}/100")
            used.append(c.source_id)
        decision = decision or 'recommended'
    elif not nxt:
        avoid = list(RotationCompatibility.objects.filter(previous_name__iexact=prev, is_active=True)
                     .order_by('score')[:3])
        if avoid:
            lines += ['', '*Epuka kufuatisha:*'] + [f"• {c.next_name} ({c.score}/100)" for c in avoid]
            used += [c.source_id for c in avoid]
        if pf and pf.note:
            lines += ['', f"ℹ️ {pf.crop_name} ni zao la kundi la *{pf.rotation_group}* "
                          f"({_clean(pf.nutrient_role).lower()}). {_clean(pf.note)}"]
        if not loc or not loc.get('aez_id'):
            lines += ['', "📍 Ukitaja wilaya au kata yako, nitakuonyesha mfuatano unaopendekezwa kwa kanda yako."]
        decision = decision or ('avoid_only' if avoid else 'no_assessment')

    for r in _soil_rules(text, state):
        lines += ['', f"🟤 {_clean(r.farmer_message_sw)}"]
        used.append(r.source_id)

    lines += ['', DISCLAIMER]
    trace.update({'decision': decision, 'rules_used': [u for u in dict.fromkeys(used) if u],
                  'aez': loc.get('aez_id') if loc else None})
    if state and state.get('ai'):
        trace['ai'] = state['ai']
    return '\n'.join(lines), trace
