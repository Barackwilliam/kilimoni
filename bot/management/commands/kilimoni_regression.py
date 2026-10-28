"""
Regression tests za Kilimoni Bot
================================
Inaendesha maswali ya majaribio ya mteja na kukagua kwamba bot:
  - inauliza maswali ya ufafanuzi kabla ya kutoa ushauri
  - haitoi dawa, dosage wala frequency kabla ya taarifa kukamilika
  - inajibu zao moja pekee
  - inarekodi trace ya kila hatua

Matumizi:
    python manage.py kilimoni_regression --offline                   # bila AI ya nje
    python manage.py kilimoni_regression --offline --load-fixtures   # + ingiza MHD-007 kwanza

Majaribio yaliyo na [1]–[6] yanapima vigezo 6 vya mteja vya kukubali injini.
"""
import re
from unittest.mock import patch

from django.core.management.base import BaseCommand

from bot.models import User, Conversation
from bot.diagnostic import CHEMICAL_PATTERN, KNOWN_CROPS


TEST_PHONE_BASE = '255799900'


def _no_chemical(text):
    return not CHEMICAL_PATTERN.search(text or '')


def _single_crop(text, crop):
    low = (text or '').lower()
    from bot.diagnostic import CROP_ALIASES
    own = {crop, *CROP_ALIASES.get(crop, ())}
    others = [c for c in KNOWN_CROPS if c not in own and c not in crop]
    return not any(re.search(r'\b' + re.escape(c) + r'\b', low) for c in others)


JARGON = re.compile(r'\b(frass|whorl|scouting|biopesticides?|mode of action|natural enemies'
                    r'|confidence|dataset|MHD-\d+\w*|DR-MZ|CONF\d+|AI\s+(imechagua|imependekeza|inachagua))\b',
                    re.IGNORECASE)


def _plain(text):
    return not JARGON.search(text or '')


def _questions(replies):
    return [m.group(1).strip() for r in replies for m in re.finditer(r'\*Swali \d+:\* (.+)', r)]


def _traces(phone):
    return [c.trace for c in Conversation.objects
            .filter(user__phone_number=phone, message_direction='outbound')
            .order_by('created_at') if c.trace]


FAW_TURNS = [
    'Mazao yangu yanaumwa, nifanye nini?',
    'mahindi',
    'majani yana mashimo makubwa',
    'ndiyo',        # frass/lava ya Y — ishara kuu ya FAW
    'hapana',       # panzi hawaonekani
]

SCENARIOS = [
    {
        'name': 'T1 — Swali pana: "Naomba msaada kuhusu kilimo"',
        'turns': ['Naomba msaada kuhusu kilimo'],
        'checks': [
            ('Inauliza lengo badala ya kutoa ushauri',
             lambda r, t: 'msaada gani' in r[-1].lower()),
            ('Haitaji dawa wala dosage', lambda r, t: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T2 — "Mazao yangu yanaumwa, nifanye nini?"',
        'turns': ['Mazao yangu yanaumwa, nifanye nini?'],
        'checks': [
            ('Inauliza zao kwanza', lambda r, t: 'zao gani' in r[-1].lower()),
            ('Haitaji ugonjwa, dawa wala dosage', lambda r, t: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T3 — Uchunguzi kamili wa mahindi: FAW, nusu ya shamba',
        'turns': FAW_TURNS + ['nusu ya shamba'],
        'checks': [
            ('Kila swali la kati halina dawa', lambda r, t: all(_no_chemical(x) for x in r[:-1])),
            ('[1] Hakuna swali linalojirudia',
             lambda r, t: len(_questions(r)) == len(set(_questions(r))) and len(_questions(r)) >= 1),
            ('[2] Kila swali la kufuatilia linatoka kwenye kanuni za dalili hizi',
             lambda r, t: all(x.get('sources') for x in t if x.get('asked') not in (None, 'crop', 'symptoms', 'extent'))),
            ('[3] Inalinganisha visababishi (orodha + "kwa nini si vingine")',
             lambda r, t: 'kusababishwa na' in r[2].lower() and 'kwa nini si vingine' in r[-1].lower()),
            ('[4] Uhakika unatokana na kanuni (zimeandikwa kwenye trace)',
             lambda r, t: any(x.startswith('DR-') for x in t[-1].get('rules_used', []))
             and 'DR-' in t[-1].get('rules_text', '') and '%' in r[-1]),
            ('[5] Kemikali kwa category tu, kwa REC rule + tahadhari ya label',
             lambda r, t: t[-1]['gate']['recommendation'] and 'kibandiko' in r[-1].lower()),
            ('[6] Jibu linataja kwamba ushauri unatoka taarifa za kitaalamu',
             lambda r, t: 'taarifa za kitaalamu' in r[-1].lower()),
            ('Lugha rahisi: hakuna maneno ya kiufundi wala maelekezo ya mfumo',
             lambda r, t: all(_plain(x) for x in r)),
            ('Inachagua tatizo mahsusi', lambda r, t: 'fall armyworm' in r[-1].lower()),
            ('Jibu linahusu mahindi pekee', lambda r, t: _single_crop(r[-1], 'mahindi')),
        ],
        'trace': True,
    },
    {
        'name': 'T3b — FAW imethibitishwa lakini mimea michache tu (kigezo 5)',
        'turns': FAW_TURNS + ['mimea michache tu'],
        'checks': [
            ('[5] Hakuna dawa: severity ndogo haitimizi REC rule',
             lambda r, t: _no_chemical(r[-1]) and not t[-1]['gate']['chemical_allowed']),
            ('Bado inatoa utambuzi na hatua za IPM', lambda r, t: 'fall armyworm' in r[-1].lower()),
        ],
    },
    {
        'name': 'T4 — "Mahindi yangu yana wadudu" (taarifa hazitoshi)',
        'turns': ['Mahindi yangu yana wadudu'],
        'checks': [
            ('Haitoi dawa mara moja', lambda r, t: _no_chemical(r[-1])),
            ('Inauliza dalili', lambda r, t: 'dalili' in r[-1].lower()),
        ],
    },
    {
        'name': 'T5 — Mkulima hajui majibu ya maswali (dawa lazima zizuiwe)',
        'turns': ['mahindi yangu yana mashimo makubwa kwenye majani', 'sijui', 'sijui', 'sijui'],
        'checks': [
            ('Haitoi utambuzi ushahidi usipotosha',
             lambda r, t: any('siwezi kukupa utambuzi' in x.lower() for x in r)),
            ('Hakuna jibu lenye dawa wala dosage', lambda r, t: all(_no_chemical(x) for x in r)),
            ('Inaelekeza kwa afisa ugani', lambda r, t: any('afisa ugani' in x.lower() for x in r)),
            ('Haionyeshi asilimia ikiwa haina uhakika',
             lambda r, t: '%' not in r[-1]),
            ('[1] Haiulizi dhana moja mara mbili (frass/kinyesi)',
             lambda r, t: sum('frass' in q.lower() or 'kinyesi' in q.lower() for q in _questions(r)) == 1),
        ],
        'trace': True,
    },
    {
        'name': 'T5b — Dalili zisizo kwenye kanuni (kigezo 6: haibuni)',
        'turns': ['mahindi yangu yana madoa ya kijivu na kahawia kwenye majani'],
        'checks': [
            ('Inasema wazi haina utambuzi', lambda r, t: 'siwezi kukupa utambuzi' in r[-1].lower()),
            ('Haibuni dawa', lambda r, t: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T6 — Mkulima anasitisha uchunguzi',
        'turns': ['Mazao yangu yanaumwa', 'acha'],
        'checks': [
            ('Uchunguzi unasitishwa kwa staha', lambda r, t: 'sitisha' in r[-1].lower()),
        ],
    },
    {
        'name': 'T8 — Zao lisilo kwenye dataset (mtama) halizungushwi',
        'turns': ['Mazao yangu yanaumwa', 'mtama'],
        'checks': [
            ('Inasema wazi haina taarifa za zao hilo', lambda r, t: 'sina taarifa' in r[-1].lower()),
            ('Haiulizi "zao gani" tena', lambda r, t: 'zao gani' not in r[-1].lower()),
            ('Haibuni ushauri wa zao hilo', lambda r, t: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T9 — Jibu lisiloeleweka kwa swali la zao halizungushwi',
        'turns': ['Mazao yangu yanaumwa', 'hmm', 'sielewi'],
        'checks': [
            ('Inaacha kuuliza baada ya majaribio 2', lambda r, t: 'zao gani' not in r[-1].lower()),
        ],
    },
    {
        'name': 'T10 — Ugonjwa hatari (MLN): hakuna dawa, afisa ugani (ESC-MZ-001)',
        'turns': ['mahindi yana mistari ya njano na mmea umedumaa', 'ndiyo', 'shamba lote'],
        'checks': [
            ('Inatambua MLN baada ya ishara kuu', lambda r, t: 'mln' in r[-1].lower()),
            ('Hakuna dawa (escalation inazuia)', lambda r, t: not t[-1]['gate']['chemical_allowed']),
            ('Inaelekeza kwa afisa ugani', lambda r, t: 'afisa ugani' in r[-1].lower()),
            ('Lugha rahisi kwenye jibu la ugonjwa', lambda r, t: all(_plain(x) for x in r)),
            ('Hakuna sentensi ya Kiingereza kwenye jibu', lambda r, t: 'maintain' not in r[-1].lower()
             and 'registered products' not in r[-1].lower()),
        ],
    },
    {
        'name': 'T11 — Zao lisilo na kanuni za uchunguzi (maharage): haibuni',
        'turns': ['maharage yangu yana mashimo kwenye majani'],
        'checks': [
            ('Inasema wazi haina kanuni', lambda r, t: 'sitabuni' in r[-1].lower()),
            ('Haitaji dawa', lambda r, t: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T7 — Bei ya soko inaonya kwamba si bei ya leo',
        'turns': ['bei ya mahindi Dodoma ikoje'],
        'checks': [
            ('Onyo la bei lipo', lambda r, t: 'thibitisha' in r[-1].lower()),
        ],
    },
]


class Command(BaseCommand):
    help = 'Endesha regression tests za mtiririko wa uchunguzi wa Kilimoni Bot'

    def add_arguments(self, parser):
        parser.add_argument('--offline', action='store_true',
                            help='Usiite AI ya nje — majibu kutoka dataset pekee')
        parser.add_argument('--load-fixtures', action='store_true',
                            help='Ingiza kwanza Excel za MHD-007 za diagnosis/fixtures/mhd007')

    def handle(self, *args, **opts):
        from bot.engine import process_message
        from diagnosis.models import Pest

        if opts['load_fixtures']:
            import glob, os
            from diagnosis.importer import import_mhd007
            folder = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'diagnosis', 'fixtures', 'mhd007')
            self.stdout.write(import_mhd007(sorted(glob.glob(os.path.join(folder, '*.xlsx')))).as_text())
        if not Pest.objects.exists():
            self.stdout.write(self.style.WARNING(
                'Hakuna data ya MHD-007 kwenye database — endesha kwa --load-fixtures '
                'au import_mhd007 kwanza.'))

        passed = failed = 0
        ctx = patch('bot.groq_ai.get_groq_response', return_value='') if opts['offline'] else None
        if ctx:
            ctx.start()

        try:
            for i, sc in enumerate(SCENARIOS):
                phone = f"{TEST_PHONE_BASE}{i:03d}"
                User.objects.filter(phone_number=phone).delete()

                self.stdout.write('\n' + '═' * 64)
                self.stdout.write(self.style.MIGRATE_HEADING(sc['name']))
                self.stdout.write('═' * 64)

                replies = []
                for turn in sc['turns']:
                    reply = process_message(phone, turn)
                    replies.append(reply)
                    self.stdout.write(f"\n👨‍🌾 {turn}")
                    self.stdout.write(f"🤖 {reply}")

                self.stdout.write('')
                traces = _traces(phone)
                for label, fn in sc['checks']:
                    try:
                        ok = bool(fn(replies, traces))
                    except Exception:
                        ok = False
                    if ok:
                        passed += 1
                        self.stdout.write(self.style.SUCCESS(f"  ✓ PASS  {label}"))
                    else:
                        failed += 1
                        self.stdout.write(self.style.ERROR(f"  ✗ FAIL  {label}"))

                if sc.get('trace') and traces:
                    t = traces[-1]
                    self.stdout.write('\n  📋 TRACE:')
                    self.stdout.write(f"     uamuzi          : {t.get('decision')} {t.get('diagnosis') or ''}")
                    self.stdout.write(f"     scores          : {t.get('scores')}")
                    self.stdout.write(f"     kanuni          : {', '.join(t.get('rules_used', []))}")
                    for ev in t.get('evidence', []):
                        self.stdout.write(f"     ushahidi        : {ev['answer']:<7} {ev['question'][:55]} "
                                          f"{ev['deltas']} ({', '.join(ev['sources'])})")
                    if t.get('gate'):
                        self.stdout.write(f"     safety gate     : {t['gate']}")

                User.objects.filter(phone_number=phone).delete()
        finally:
            if ctx:
                ctx.stop()

        self.stdout.write('\n' + '═' * 64)
        total = passed + failed
        style = self.style.SUCCESS if failed == 0 else self.style.ERROR
        self.stdout.write(style(f"MATOKEO: {passed}/{total} zimepita"))
