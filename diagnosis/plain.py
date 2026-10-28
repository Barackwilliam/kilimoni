"""
Lugha rahisi kwa mkulima
========================

Maandishi ya dataset (MHD-007) yameandikwa na wataalamu: yana maneno ya
kiufundi ("frass", "whorl", "scouting"), maelekezo kwa mfumo ("…confidence
kutoka MHD-007D…") na wakati mwingine sentensi nzima kwa Kiingereza.

Moduli hii inayasafisha KABLA ya kumfikia mkulima, bila AI na bila kubuni:
  1. Sentensi za maelekezo ya mfumo zinaondolewa (zinabaki kwenye trace).
  2. "AI imechagua X kwa sababu Y" → "Y" (mkulima haambiwi kuhusu AI).
  3. Maneno ya kiufundi yanabadilishwa kwa kamusi (FarmerTerm). Kamusi
     inabadilishwa na mteja kwenye dashboard, bila code.
  4. Sentensi iliyobaki kwa Kiingereza inaondolewa na kuandikwa kwenye
     trace, ili timu ya data ijue inahitaji kutafsiriwa.

Kamusi inatumika kwa maneno yote yanayofanana (case-insensitive, mipaka ya
neno), kwa mpangilio wa urefu — kifungu kirefu kwanza ("badilisha mode of
action" kabla ya "mode of action").
"""
import re

# Default za kamusi. Migration 0005 inaziingiza kwenye DB (FarmerTerm);
# DB ikiwa tupu (mf. tests bila migration) hizi ndizo zinatumika.
DEFAULT_TERMS = [
    # Sentensi/vifungu vizima vya dataset vilivyo kwa Kiingereza
    ('volunteer maize and grassy weeds', 'mahindi yaliyoota yenyewe na magugu ya nyasi'),
    ('maintain field hygiene', 'weka shamba safi'),
    ('synchronize planting where possible', 'pandeni kwa wakati mmoja na majirani pale inapowezekana'),
    ('no curative chemical for virus', 'hakuna tiba ya kemikali kwa virusi'),
    ('vector control only when justified and registered products are advised by extension officers',
     'fuata ushauri wa afisa ugani kuhusu kudhibiti wadudu wanaoeneza ugonjwa'),
    ('where registered and label-approved', 'pale tu zimesajiliwa na zimeruhusiwa kwenye kibandiko'),
    ('epuka kupulizia bila diagnosis', 'usipulizie chochote kabla tatizo halijathibitishwa'),
    ('vectors kama thrips/aphids', 'wadudu wanaoeneza ugonjwa (kama vithripi na vidukari)'),
    ('tumia crop rotation na varieties zenye ustahimilivu',
     'badilisha mazao kila msimu, na tumia aina za mbegu zinazostahimili'),
    ('tumia crop rotation', 'badilisha mazao kila msimu'),
    ('dalili kuu za FAW', 'dalili kuu za funza jeshi vamizi'),
    ('lava', 'funza'),
    ('stress', 'hali ngumu ya hewa au udongo (mf. ukame)'),
    ('scouting ya mistari tofauti', 'kagua mimea kwenye mistari tofauti ya shamba'),
    ('badilisha mode of action', 'usitumie aina moja ya dawa kila mara; badilisha aina'),
    ('varieties zenye ustahimilivu', 'aina za mbegu zinazostahimili'),
    ('pest husika', 'mdudu husika'),
    ('dead heart', 'kitovu kilichokauka'),
    # Maneno ya kiufundi
    ('frass', 'kinyesi cha funza (kama vumbi la mbao)'),
    ('whorl', 'kitovu cha mmea'),
    ('scouting', 'ukaguzi wa shamba'),
    ('crop rotation', 'kubadilisha mazao kila msimu'),
    ('natural enemies', 'wadudu rafiki (wanaokula wadudu waharibifu)'),
    ('biopesticides', 'viuatilifu vya asili'),
    ('mode of action', 'aina ya dawa'),
    ('varieties', 'aina za mbegu'),
    ('mosaic', 'michirizi ya rangi mchanganyiko'),
    ('label', 'maelekezo ya kibandiko'),
    ('gloves', 'glavu'),
    ('mask', 'barakoa'),
    ('pests', 'wadudu'),
    ('pest', 'mdudu'),
    ('treatment', 'tiba'),
    ('diagnosis', 'uthibitisho wa tatizo'),
]

# Ishara za sentensi iliyoandikwa kwa ajili ya mfumo, si mkulima
SYSTEM_NOTE = re.compile(
    r'MHD-\d|\bconfidence\b|\bdataset\b|\brecords?\b|\bCMS\b|\bmfumo utahitaji\b'
    r'|\bplant part\b|\bgrowth stage\b|\bfollow-?up\b',
    re.IGNORECASE,
)
# "AI imechagua FAW kwa sababu ..." → "..."
AI_BECAUSE = re.compile(
    r'^\s*AI\s+\w+\s+.{0,80}?\bkwa sababu\s+', re.IGNORECASE)
AI_START = re.compile(r'^\s*AI\s+\w+', re.IGNORECASE)

ENGLISH_WORDS = {
    'the', 'and', 'of', 'for', 'only', 'when', 'are', 'by', 'with', 'where',
    'is', 'to', 'if', 'or', 'not', 'use', 'remove', 'maintain', 'possible',
    'registered', 'advised', 'should', 'plant', 'plants', 'field',
}
BAND_SW = {'very high': 'juu sana', 'high': 'juu', 'medium': 'wastani', 'low': 'chini'}


def band_sw(label):
    return BAND_SW.get((label or '').strip().lower(), label)


def _terms():
    try:
        from .models import FarmerTerm
        rows = list(FarmerTerm.objects.filter(is_active=True).values_list('term', 'plain'))
    except Exception:
        rows = []
    rows = rows or DEFAULT_TERMS
    return sorted(rows, key=lambda r: -len(r[0]))


def _apply_terms(text, terms):
    for term, plain in terms:
        pattern = r'(?<![\w-])' + re.escape(term) + r'(?![\w-])'
        text = re.sub(pattern, plain.replace('\\', r'\\'), text, flags=re.IGNORECASE)
    return text


def _is_english(sentence):
    words = re.findall(r"[a-z']+", sentence.lower())
    if len(words) < 3:
        return False
    eng = sum(1 for w in words if w in ENGLISH_WORDS)
    return eng >= 2 and eng / len(words) >= 0.2


def _cap_first(s):
    return s[:1].upper() + s[1:] if s else s


def clean_sentence(sentence, terms=None):
    """Rudisha (sentensi safi au None, sababu ya kuondolewa au None)."""
    s = sentence.strip()
    if not s:
        return None, None
    if AI_BECAUSE.search(s):
        s = _cap_first(AI_BECAUSE.sub('', s))
    elif AI_START.search(s):
        return None, 'system_note'
    if SYSTEM_NOTE.search(s):
        return None, 'system_note'
    s = _apply_terms(s, terms if terms is not None else _terms())
    if _is_english(s):
        return None, 'english'
    return s, None


def clean(text, terms=None):
    """
    Safisha kipande cha maandishi chenye sentensi moja au zaidi (zilizotengwa
    kwa ';' au '.'). Rudisha (maandishi safi, [(sentensi, sababu), ...]).
    """
    terms = terms if terms is not None else _terms()
    kept, dropped = [], []
    for part in re.split(r'(?<=[.;])\s+', (text or '').strip()):
        core = part.rstrip(' .;')
        if not core:
            continue
        sub_kept = []
        for clause in core.split(';'):
            out, why = clean_sentence(clause, terms)
            if out:
                sub_kept.append(out)
            elif why:
                dropped.append((clause.strip(), why))
        if sub_kept:
            kept.append('; '.join(_cap_first(x) if i == 0 else x for i, x in enumerate(sub_kept)) + '.')
    return ' '.join(kept), dropped


def as_statement(question):
    """'Je, kuna kinyesi …?' → 'kuna kinyesi …' (kwa orodha ya ushahidi)."""
    q = re.sub(r'^\s*je\s*,?\s*', '', question or '', flags=re.IGNORECASE)
    return q.strip().rstrip('?').strip()
