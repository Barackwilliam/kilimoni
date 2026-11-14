"""
Kanuni za ubora za kila jibu la bot (kipimo cha kiotomatiki, si screenshot moja moja)
=====================================================================================

INVARIANTS — lazima ziwe 0 kwenye benki nzima kabla ya deploy:
  legacy     — maandishi ya mfumo wa zamani ("nahitaji kidogo zaidi", "Uko mkoa gani?"…)
  invented   — bei, majina ya dawa/makampuni, vipimo vya dawa (ml/gramu)
  repeat     — jibu lilelile mara mbili mfululizo kwenye mazungumzo moja
  empty      — jibu tupu
  crash      — hitilafu ya code
  too_long   — zaidi ya herufi 4,000 (kikomo cha WhatsApp)

UELEWA (kinapimwa, si kizuizi) — kila kesi inaweza kuwa na matarajio:
  any   — jibu lina angalau moja ya maneno haya
  none  — jibu halina neno lolote kati ya haya
  clear — True: jibu lisiwe swali la kufafanua (menyu ya "sijaelewa")
"""
import re

LEGACY_TEXT = (
    'shikamoo',
    'nahitaji kidogo zaidi', 'hilo liko nje ya uwezo', 'hapo umenishinda', 'hilo silijui vizuri',
    'uko mkoa gani', 'sijalitambua hilo eneo', 'jaribu kuandika jina la mkoa', 'ninajua tunaongelea',
    'bei za takriban', 'hutofautiana kulingana na eneo',
)
INVENTED = re.compile(
    r'\b(tzs|tsh|shilingi\s*\d|\d[\d,\.]*\s*(?:/=|tsh))'
    r'|\b(actellic|racumin|azam|bakhresa|duduba|karate|belt|coragen|ampligo|dudu ?all)\b'
    r'|\b\d+\s*(?:ml|mls|mililita)\b(?!.*kibandiko)'
    r'|\bgramu\s*\d+|\b\d+\s*gramu\b', re.I)
CLARIFY_DECISIONS = {'goal_menu', 'single_unknown_word'}


def check_reply(reply, previous, decision):
    """Rudisha list ya makosa ya invariants kwa jibu moja."""
    errs = []
    low = (reply or '').lower()
    if not low.strip():
        errs.append('empty')
    for t in LEGACY_TEXT:
        if t in low:
            errs.append(f'legacy: "{t}"')
    m = INVENTED.search(reply or '')
    if m:
        errs.append(f'invented: "{m.group(0)}"')
    if previous is not None and reply == previous:
        errs.append('repeat')
    if len(reply or '') > 4000:
        errs.append('too_long')
    return errs


def check_expect(turn, reply, decision):
    """Matarajio ya uelewa (si invariant)."""
    low = (reply or '').lower()
    misses = []
    if turn.get('any') and not any(w.lower() in low for w in turn['any']):
        misses.append(f"inakosa mojawapo ya {turn['any']}")
    for w in turn.get('none', ()):
        if w.lower() in low:
            misses.append(f'ina "{w}"')
    if turn.get('clear') and decision in CLARIFY_DECISIONS:
        misses.append(f'imeuliza kufafanua ({decision})')
    return misses


def run(conversations, phone_base='2557990', on_case=None):
    """
    Endesha mazungumzo yote kupitia bot (process_message). Rudisha dict ya matokeo.
    Inaandika kwenye database — iendeshe ndani ya transaction itakayorudishwa nyuma.
    """
    from bot.engine import process_message
    from bot.models import Conversation, User
    stats = {'turns': 0, 'violations': [], 'expect_total': 0, 'expect_ok': 0, 'misses': []}
    for i, conv in enumerate(conversations):
        phone = f"{phone_base}{i:05d}"
        User.objects.filter(phone_number=phone).delete()
        previous = None
        for j, turn in enumerate(conv['turns']):
            stats['turns'] += 1
            try:
                reply = process_message(phone, turn['msg'])
            except Exception as exc:                       # noqa: BLE001 — tunataka kuripoti, si kusimama
                stats['violations'].append((conv['id'], j, turn['msg'], [f'crash: {exc!r}'], ''))
                previous = None
                continue
            user = User.objects.filter(phone_number=phone).first()
            last = (Conversation.objects.filter(user=user, message_direction='outbound').order_by('-id').first()
                    if user else None)
            decision = ((last.trace or {}).get('decision') if last else '') or ''
            errs = check_reply(reply, previous, decision)
            if errs:
                stats['violations'].append((conv['id'], j, turn['msg'], errs, reply))
            if any(k in turn for k in ('any', 'none', 'clear')):
                stats['expect_total'] += 1
                misses = check_expect(turn, reply, decision)
                if misses:
                    stats['misses'].append((conv['id'], j, turn['msg'], misses, reply))
                else:
                    stats['expect_ok'] += 1
            if on_case:
                on_case(conv, j, turn, reply, errs)
            previous = reply
    return stats
