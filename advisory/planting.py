"""
Wakati wa kupanda kwa kanuni (MHD-006 R1–R3, ukitumia eneo la MHD-001 na mbegu za MHD-003A)
==========================================================================================

Rule_Precedence ya dataset:
  0. Taarifa muhimu zikikosekana → uliza kwanza (eneo: PDE-0011/CALRULE-001, zao: CALRULE-002,
     hali ya mvua: fallback_question ya PDE-0001).
  1. Usalama → "usipande" unashinda pendekezo chanya (IRR-002 nje ya msimu bila maji).

Hatua za uamuzi:
  a) Kanda ya mkulima (MHD-001) → msimu wa kanda (MHD-006 R2, kupitia ulinganisho wa AEZ)
     na kalenda ya zao (MHD-006 R1) kama ipo.
  b) Leo iko wapi: kabla ya dirisha / dirisha la mapema / la kawaida / la kuchelewa / limefungwa.
     Bila kalenda ya zao, dirisha la kuanza mvua (onset) na kuisha (cessation) vinatumika.
  c) Hali ya mvua (kutoka kwa mkulima): zimeanza / bado / zilinyesha mara moja zikakata.
  d) Uamuzi: PANDA_SASA, PANDA_KWA_TAHADHARI, SUBIRI, WAIT_OR_EARLY_VARIETY, WAIT,
     ALLOW_IRRIGATION_PLANTING, DO_NOT_PLANT — kila mmoja una kanuni yake ya dataset.
  e) Mbegu: siku zilizobaki hadi mvua kuisha zinalinganishwa na siku za kukomaa za mbegu
     zinazofaa kanda (MHD-003A). Ukichelewa → za mapema tu (VARLOG-002).
  f) Hatari za hali ya hewa na mazao mbadala (Alternative_Crop_Rules) za kanda hiyo.
"""
import datetime
import re

from django.utils import timezone

from diagnosis import plain

from .models import Aez, AezAlias, AdvisoryRule, ClimateRisk, CropCalendar, ExplainTemplate, PlantingRule, SeasonProfile

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'mei': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'ago': 8,
    'sep': 9, 'oct': 10, 'okt': 10, 'nov': 11, 'dec': 12, 'des': 12, 'mac': 3, 'mach': 3,
}
MONTH_SW = ['', 'Januari', 'Februari', 'Machi', 'Aprili', 'Mei', 'Juni', 'Julai', 'Agosti', 'Septemba',
            'Oktoba', 'Novemba', 'Desemba']
PLANT_STEMS = ('nipande lini', 'tupande lini', 'kupanda lini', 'wakati wa kupanda', 'muda wa kupanda',
               'msimu wa kupanda', 'nianze kupanda', 'naweza kupanda', 'niweze kupanda', 'kipindi cha kupanda',
               'mwezi gani', 'tarehe ya kupanda', 'nipande sasa', 'nipande mwezi', 'when to plant')
DISCLAIMER = "_Ushauri huu unatokana na taarifa za kitaalamu za Kilimoni AI; si mbadala wa afisa ugani._"

HEAD = {
    'PANDA_SASA': '✅ *Unaweza kupanda sasa*',
    'PANDA_KWA_TAHADHARI': '⚠️ *Unaweza kupanda, kwa tahadhari*',
    'SUBIRI': '⏳ *Subiri kwanza*',
    'WAIT': '⏳ *Subiri mvua ziendelee*',
    'WAIT_OR_EARLY_VARIETY': '⏳ *Subiri, au tumia mbegu ya muda mfupi*',
    'ALLOW_IRRIGATION_PLANTING': '💧 *Unaweza kupanda kwa umwagiliaji*',
    'DO_NOT_PLANT': '⛔ *Si vyema kupanda sasa*',
    'INFO_ONLY': '🗓️ *Kipindi cha kupanda cha kanda yako*',
}


def _clean(text):
    return plain.clean(text or '')[0]


def _norm(text):
    return ' '.join(re.findall(r"[a-z0-9']+", (text or '').lower()))


def wants_planting(text, intent=None):
    low = _norm(text)
    if any(s in low for s in PLANT_STEMS):
        return True
    return getattr(intent, 'intent_name', '') in ('planting_time', 'weather_planting_decision')


# ─────────────────────────── Tarehe ───────────────────────────

def parse_window(text):
    """'16-Dec–10-Jan' / 'Nov 15–Dec 20' → ((12, 16), (1, 10)); haipatikani → None."""
    pairs = []
    for m in re.finditer(r'(\d{1,2})[\s\-]*([A-Za-z]{3,})|([A-Za-z]{3,})[\s\-]*(\d{1,2})', text or ''):
        day, mon = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        month = MONTHS.get(mon.lower()[:3]) or MONTHS.get(mon.lower()[:4])
        if month:
            pairs.append((month, int(day)))
    return (pairs[0], pairs[1]) if len(pairs) >= 2 else None


def _season_year(today):
    """Msimu wa kilimo unaanza Julai: Okt 2026 → msimu 2026/27."""
    return today.year if today.month >= 7 else today.year - 1


def window_dates(window, today):
    w = parse_window(window) if isinstance(window, str) else window
    if not w:
        return None
    y = _season_year(today)

    def to_date(md):
        m, d = md
        year = y if m >= 7 else y + 1
        try:
            return datetime.date(year, m, d)
        except ValueError:
            return datetime.date(year, m, 28)
    return to_date(w[0]), to_date(w[1])


def fmt_window(window):
    w = parse_window(window)
    if not w:
        return window or ''
    (m1, d1), (m2, d2) = w
    return f"{d1} {MONTH_SW[m1]} – {d2} {MONTH_SW[m2]}"


MONTH_EN = {'jan': 'Januari', 'feb': 'Februari', 'mar': 'Machi', 'apr': 'Aprili', 'may': 'Mei', 'jun': 'Juni',
            'jul': 'Julai', 'aug': 'Agosti', 'sep': 'Septemba', 'oct': 'Oktoba', 'nov': 'Novemba', 'dec': 'Desemba'}
RISK_SW = {'dry spell': 'vipindi vya ukame ndani ya msimu', 'frost': 'baridi kali (barafu)', 'flood': 'mafuriko',
           'heat': 'joto kali', 'waterlogging': 'maji kutuama shambani', 'drought': 'ukame'}
LEVEL_SW = {'high': 'kubwa', 'medium': 'ya wastani', 'low': 'ndogo', 'low to medium': 'ndogo hadi ya wastani',
            'medium to high': 'ya wastani hadi kubwa'}


def months_sw(text):
    """'May–Jul' → 'Mei–Julai'; 'Jun–Aug high altitude pockets' → 'Juni–Agosti high…' (maneno mengine yanabaki)."""
    return re.sub(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b',
                  lambda m: MONTH_EN[m.group(1).lower()], text or '')


def risk_message(r):
    """Ujumbe wa hatari kutoka fields za dataset (si sentensi ya Kiingereza ya farmer_message_sw)."""
    kind = next((sw for en, sw in RISK_SW.items() if en in (r.risk_type or '').lower()), None)
    level = LEVEL_SW.get((r.risk_level or '').strip().lower())
    if not kind or not level:
        return _clean(r.farmer_message_sw)
    window = months_sw(re.sub(r'\b(high altitude pockets?|pockets?)\b', '', r.risk_window or '', flags=re.I)).strip()
    alt = ' (hasa maeneo ya miinuko mikubwa)' if 'altitude' in (r.risk_window or '').lower() else ''
    return f"Hatari ya {kind} ni {level}" + (f" katika kipindi cha {window}" if window else '') + f"{alt}."


def fmt_date(d):
    return f"{d.day} {MONTH_SW[d.month]}"


# ─────────────────────────── Maneno ya mkulima ───────────────────────────

RAIN_FALSE = re.compile(r'mara moja|ikakata|zikakata|ikaacha|zikaacha|imekata|zimekata|imeacha|zimeacha|ikapotea')
RAIN_NO = re.compile(r'bado mvua|mvua bado|haijanyesha|hazijanyesha|haijaanza|hazijaanza|hakuna mvua|hamna mvua'
                     r'|mvua hakuna|hapana|bado haija|bado hazija|\bbado\b')
RAIN_YES = re.compile(r'(mvua|zi|i)\w* ?(zimeanza|imeanza|imenyesha|zimenyesha|zinanyesha|inanyesha)'
                      r'|zimeanza|imeanza|imenyesha|zimenyesha|zinanyesha|inanyesha|mvua za kutosha|\bndiyo\b|\bndio\b|\byes\b')
IRR_YES = re.compile(r'umwagiliaji|kisima|bwawa|maji ya mto|pampu|pump|nina maji|irrigation')
IRR_NO = re.compile(r'sina maji|hakuna maji|bila umwagiliaji|sina umwagiliaji|hamna maji')


def rain_status(text, state=None):
    low = _norm(text)
    if RAIN_FALSE.search(low):
        return 'false_start'
    if RAIN_NO.search(low):
        return 'not_started'
    if RAIN_YES.search(low):
        return 'confirmed'
    if len(low.split()) >= 4:
        from diagnosis import ai_layer
        code = ai_layer.match_option(text, {
            'confirmed': 'mvua za kuaminika zimeanza kunyesha na udongo una unyevu',
            'not_started': 'mvua bado hazijaanza',
            'false_start': 'mvua ilinyesha mara moja kisha ikakata',
        }, state, step='rain_status')
        return code
    return None


def irrigation(text):
    low = _norm(text)
    if IRR_NO.search(low):
        return False
    if IRR_YES.search(low):
        return True
    return None


# ─────────────────────────── Data ───────────────────────────

def season_for(aez):
    return SeasonProfile.objects.filter(aez=aez, is_active=True).first()


def calendar_for(crop, aez):
    return CropCalendar.objects.filter(crop=crop, aez=aez, is_active=True).first() if crop else None


def _rule(kind, decision=None, aez=None, **filters):
    q = PlantingRule.objects.filter(kind=kind, is_active=True, **filters)
    if decision:
        q = q.filter(decision=decision)
    if aez is not None:
        q = q.filter(aez=aez)
    return q.order_by('priority', 'source_id').first()


def _arule(source_id):
    return AdvisoryRule.objects.filter(source_id=source_id, is_active=True).first()


def phase_for(today, cal, season):
    """Rudisha (phase, maelezo). phase: before, early, normal, late, closed, onset, in_season."""
    if cal:
        e, n, l = (window_dates(cal.early_window, today), window_dates(cal.normal_window, today),
                   window_dates(cal.late_window, today))
        if e and today < e[0]:
            return 'before', e
        for name, w in (('early', e), ('normal', n), ('late', l)):
            if w and w[0] <= today <= w[1]:
                return name, w
        if l and today > l[1]:
            return 'closed', l
    if season:
        o = window_dates(season.onset_window, today)
        c = window_dates(season.cessation_window, today)
        if o and today < o[0]:
            return 'before', o
        if o and o[0] <= today <= o[1]:
            return 'onset', o
        if c and today > c[0]:
            return 'closed', c
        if o:
            return 'in_season', o
    return None, None


def days_left(today, season):
    c = window_dates(season.cessation_window, today) if season else None
    if not c or today > c[1]:
        return None
    return (c[1] - today).days


# ─────────────────────────── Uamuzi ───────────────────────────

def decide(crop, aez, today, rain=None, irrigated=None):
    cal = calendar_for(crop, aez)
    season = season_for(aez)
    phase, window = phase_for(today, cal, season)
    r, decision, ask_rain, rules = None, None, False, []

    if phase is None:
        decision = 'INFO_ONLY'
    elif phase == 'closed':
        # PREC-002: usalama — nje ya msimu bila maji ya uhakika, usipande
        decision = 'ALLOW_IRRIGATION_PLANTING' if irrigated else 'DO_NOT_PLANT'
        r = _rule('irrigation', decision)
    elif phase == 'before':
        decision, r = 'SUBIRI', _arule('SEASRULE-001')
    elif rain is None:
        # PREC-001: taarifa muhimu (mvua) haipo → tahadhari + swali
        decision, ask_rain = 'PANDA_KWA_TAHADHARI', True
        r = _rule('eligibility', 'PANDA_KWA_TAHADHARI')
    elif rain == 'false_start':
        decision, r = 'WAIT', _rule('climate_exception', 'WAIT')
    elif rain == 'not_started':
        if phase in ('normal', 'late', 'in_season'):
            decision, r = 'WAIT_OR_EARLY_VARIETY', _rule('climate_exception', 'WAIT_OR_EARLY_VARIETY')
        else:
            decision, r = 'SUBIRI', _arule('SEASRULE-001')
    elif phase == 'normal':
        decision, r = 'PANDA_SASA', _rule('decision', 'PANDA_SASA')
        rules += [x.source_id for x in (_rule('window', 'PANDA_SASA'), _rule('eligibility', 'PANDA_SASA')) if x]
    elif phase in ('early', 'onset'):
        decision, r = 'PANDA_KWA_TAHADHARI', _rule('window', 'PANDA_KWA_TAHADHARI')
    else:   # late / in_season, mvua zimeanza
        decision, r = 'PANDA_KWA_TAHADHARI', _rule('variety_logic', 'Late planting window')

    msg = ''
    if r:
        rules.insert(0, r.source_id)
        msg = r.farmer_message_sw
    late = phase in ('late', 'in_season', 'closed') or decision == 'WAIT_OR_EARLY_VARIETY'
    if late:
        v = _rule('variety_logic', 'Late planting window')
        if v:
            rules.append(v.source_id)
    return {'calendar': cal, 'season': season, 'phase': phase, 'window': window, 'decision': decision,
            'message': msg, 'rules': list(dict.fromkeys(rules)), 'ask_rain': ask_rain, 'late': late,
            'days_left': days_left(today, season)}


def _varieties(crop, aez, d):
    """Mbegu zinazofaa kanda (MHD-003A) zinazotosha muda uliobaki wa msimu."""
    from . import seed
    if not crop or not seed.has_data(crop):
        return [], []
    ranked = seed.decide(crop, aez)['ranked']
    if d['late'] or d['days_left'] is not None:
        limit = d['days_left']
        fits = [p for p in ranked if p.maturity_days_max and (limit is None or p.maturity_days_max <= limit)]
        too_long = [p for p in ranked if p not in fits]
        if d['late'] and not fits:
            fits = [p for p in ranked if 'mapema' in (p.maturity_class or '').lower()][:1]
        return fits[:2], too_long
    return ranked[:2], []


def _explain(decision, values):
    wanted = {'PANDA_SASA': ('PANDA_SASA', 'plant now', 'normal window'),
              'SUBIRI': ('SUBIRI', 'onset wait'), 'WAIT_OR_EARLY_VARIETY': ('SUBIRI', 'onset wait'),
              'PANDA_KWA_TAHADHARI': ('early window',)}.get(decision, ())
    for key in wanted:
        t = ExplainTemplate.objects.filter(module='planting', is_active=True,
                                           situation__iexact=key).first()
        if t:
            try:
                return _clean(t.template_sw.format(**values)), t.source_id
            except (KeyError, IndexError):
                continue
    return '', None


def advise(crop, loc, text, state=None, today=None, rain=None, irrigated=None):
    """
    Rudisha (jibu, trace). trace['decision'] ni mojawapo ya maamuzi ya dataset, au
    'need_location' / 'need_crop'. trace['ask_rain'] = True ikiwa jibu linauliza hali ya mvua.
    """
    today = today or timezone.localdate()
    trace = {'mode': 'planting_advisor', 'crop': crop.crop_name_sw if crop else '', 'today': today.isoformat()}
    if not loc or not loc.get('aez_id'):
        r = _rule('decision', 'ULIZA_LOCATION') or None
        cr = _arule('CALRULE-001')
        msg = _clean(r.farmer_message_sw if r else (cr.farmer_message_sw if cr else
                     'Tafadhali taja mkoa, wilaya au kata yako ili nijue msimu wa eneo lako.'))
        if loc and loc.get('level') == 'region':
            msg = (f"Mkoa wa *{loc['region']}* una kanda za kilimo zaidi ya moja, kwa hiyo misimu inatofautiana. "
                   "Tafadhali taja *wilaya au kata* yako.")
        trace.update({'decision': 'need_location', 'rules_used': [x.source_id for x in (r, cr) if x]})
        return f"🗓️ Sawa, nitakusaidia kujua wakati wa kupanda.\n\n{msg}\n_Mfano: Kondoa, au kata ya Changaa_", trace
    if crop is None:
        cr = _arule('CALRULE-002')
        trace.update({'decision': 'need_crop', 'rules_used': ['CALRULE-002'] if cr else []})
        return (f"🗓️ {_clean(cr.farmer_message_sw) if cr else 'Unataka kulima zao gani?'}\n_Mfano: mahindi_"), trace

    aez = Aez.objects.get(source_id=loc['aez_id'])
    if rain is None:
        rain = rain_status(text, state)
    if irrigated is None:
        irrigated = irrigation(text)
    d = decide(crop, aez, today, rain, irrigated)
    cal, season = d['calendar'], d['season']
    place = loc.get('ward') and f"{loc['ward']}, {loc['district']}" or loc.get('district') or loc.get('region')
    trace.update({'location': place, 'aez': aez.source_id, 'phase': d['phase'], 'decision': d['decision'],
                  'rain': rain, 'irrigation': irrigated, 'days_left': d['days_left'],
                  'calendar': cal.source_id if cal else None, 'season': season.source_id if season else None,
                  'rules_used': list(d['rules']), 'ask_rain': d['ask_rain']})
    if state and state.get('ai'):
        trace['ai'] = state['ai']

    lines = [f"🗓️ *Wakati wa kupanda {crop.crop_name_sw} — {place}*",
             f"_{aez.name_sw} · leo: {fmt_date(today)}_", '']

    if d['decision'] == 'INFO_ONLY':
        lines.append(HEAD['INFO_ONLY'])
        if aez.planting_window_sw:
            lines.append(f"Kwa ujumla, kanda yako hupanda *{aez.planting_window_sw}* na kuvuna "
                         f"*{aez.harvest_window_sw}*.")
        lines.append(f"Bado sina kalenda ya kina ya {crop.crop_name_sw} wala ya msimu wa mvua kwa kanda hii, "
                     "kwa hiyo siwezi kukuambia kwa uhakika kama upande sasa.")
        lines += ['', "📞 Thibitisha na afisa ugani wa kata yako kabla ya kupanda.", '', DISCLAIMER]
        trace['rules_used'].append(f"{aez.source_id}:planting_window")
        return '\n'.join(lines), trace

    lines.append(HEAD.get(d['decision'], d['decision']))
    if d['message']:
        lines.append(_clean(d['message']))

    facts = []
    if cal:
        for label, w in (('Dirisha la mapema', cal.early_window), ('Dirisha la kawaida (bora)', cal.normal_window),
                         ('Dirisha la kuchelewa', cal.late_window)):
            if w:
                facts.append(f"• {label}: {fmt_window(w)}")
        if cal.harvest_window:
            facts.append(f"• Mavuno kawaida: {months_sw(cal.harvest_window)}")
        trace['rules_used'].append(cal.source_id)
    if season:
        if season.onset_window:
            facts.append(f"• Mvua za kuaminika kawaida huanza: {fmt_window(season.onset_window)}")
        if season.cessation_window:
            facts.append(f"• Mvua kawaida huisha: {fmt_window(season.cessation_window)}")
        if season.lgp_min and season.lgp_max:
            facts.append(f"• Urefu wa msimu wa kukua: siku {season.lgp_min}–{season.lgp_max}")
        trace['rules_used'].append(season.source_id)
    if d['days_left'] is not None and d['phase'] not in ('before',):
        facts.append(f"• Zimebaki takriban *siku {d['days_left']}* hadi mvua kuisha")
    if facts:
        lines += [''] + facts

    values = {'location': place, 'aez': aez.name_sw, 'crop': crop.crop_name_sw,
              'normal_window': fmt_window(cal.normal_window) if cal else '',
              'planting_window': fmt_window(cal.normal_window) if cal else fmt_window(season.onset_window if season else ''),
              'onset_window': fmt_window(season.onset_window) if season else '',
              'early_window': fmt_window(cal.early_window) if cal else '', 'rainfall_status': rain or '',
              'rainfall_trigger': '', 'current_month': MONTH_SW[today.month]}
    why, tpl = _explain(d['decision'], values)
    if why:
        lines += ['', f"*Kwa nini:* {why}"]
        trace['rules_used'].append(tpl)

    fits, too_long = _varieties(crop, aez, d)
    if fits and d['decision'] not in ('DO_NOT_PLANT',):
        label = 'Mbegu zinazotosha muda uliobaki' if d['late'] else 'Mbegu zinazofaa kanda yako'
        lines += ['', f"*{label}:*"] + [f"• {p.name} — {p.days_text}" for p in fits]
        if too_long and d['days_left'] is not None:
            lines.append(f"_(Epuka {', '.join(p.name for p in too_long)} — zinahitaji siku nyingi kuliko "
                         "zilizobaki.)_")
        trace['varieties'] = [p.name for p in fits]

    if d['late'] or d['decision'] in ('DO_NOT_PLANT', 'WAIT_OR_EARLY_VARIETY'):
        alt = PlantingRule.objects.filter(kind='alternative', aez=aez, is_active=True).first()
        if alt and alt.farmer_message_sw:
            lines += ['', f"💡 {_clean(alt.farmer_message_sw)}"]
            trace['rules_used'].append(alt.source_id)

    risks = [r for r in ClimateRisk.objects.filter(aez=aez, is_active=True)
             if (r.risk_level or '').lower().startswith(('high', 'medium'))]
    for r in risks[:2]:
        msg = risk_message(r)
        if msg:
            lines += ['', f"⚠️ {msg}"]
            trace['rules_used'].append(r.source_id)
    if season and season.dry_spell_risk.lower().startswith('high'):
        lines += ['', "⚠️ Kwa mujibu wa taarifa za msimu, kanda yako ina hatari kubwa ya vipindi vya ukame "
                      "ndani ya msimu."]
        trace['rules_used'].append(f"{season.source_id}:dry_spell_risk")

    if d['ask_rain']:
        pde = _rule('decision', 'PANDA_SASA')
        q = (pde.extra.get('fallback_question') if pde else '') or \
            'Je, mvua za kuaminika zimeanza kunyesha eneo lako?'
        lines += ['', f"❓ *{_clean(q).rstrip('.')}*", "_Jibu: ndiyo / bado / ilinyesha mara moja ikakata_"]
    lines += ['', DISCLAIMER]
    trace['rules_used'] = [r for r in dict.fromkeys(trace['rules_used']) if r]
    return '\n'.join(lines), trace
