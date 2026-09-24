"""
Regression tests za Kilimoni Bot
================================
Inaendesha maswali ya majaribio ya mteja na kukagua kwamba bot:
  - inauliza maswali ya ufafanuzi kabla ya kutoa ushauri
  - haitoi dawa, dosage wala frequency kabla ya taarifa kukamilika
  - inajibu zao moja pekee
  - inarekodi trace ya kila hatua

Matumizi:
    python manage.py kilimoni_regression            # inatumia Groq halisi
    python manage.py kilimoni_regression --offline  # bila Groq (dataset pekee)
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


SCENARIOS = [
    {
        'name': 'T1 — Swali pana: "Naomba msaada kuhusu kilimo"',
        'turns': ['Naomba msaada kuhusu kilimo'],
        'checks': [
            ('Inauliza lengo badala ya kutoa ushauri',
             lambda r: 'msaada gani' in r[-1].lower()),
            ('Haitaji dawa wala dosage', lambda r: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T2 — "Mazao yangu yanaumwa, nifanye nini?"',
        'turns': ['Mazao yangu yanaumwa, nifanye nini?'],
        'checks': [
            ('Inauliza zao kwanza', lambda r: 'zao gani' in r[-1].lower()),
            ('Haitaji ugonjwa, dawa wala dosage', lambda r: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T3 — Uchunguzi kamili wa mahindi (taarifa zote)',
        'turns': [
            'Mazao yangu yanaumwa, nifanye nini?',
            'mahindi',
            'majani yana mashimo makubwa na kinyesi cha kahawia, kuna viwavi ndani ya kamba',
            'niko Kondoa',
            'wiki 4 baada ya kuota',
            'wiki moja iliyopita',
            'nusu ya shamba',
        ],
        'checks': [
            ('Kila swali la kati halina dawa',
             lambda r: all(_no_chemical(x) for x in r[:-1])),
            ('Inakusanya: zao, dalili, eneo, hatua, lini, kiasi',
             lambda r: ('zao gani' in r[0].lower() and 'dalili' in r[1].lower()
                        and 'wapi' in r[2].lower() and 'hatua gani' in r[3].lower()
                        and 'lini' in r[4].lower() and 'kiasi' in r[5].lower())),
            ('Jibu la mwisho linahusu mahindi pekee',
             lambda r: _single_crop(r[-1], 'mahindi')),
            ('Inachagua tatizo mahsusi (si orodha nzima)',
             lambda r: 'fall armyworm' in r[-1].lower() and 'aphids' not in r[-1].lower()),
            ('Jibu linaonyesha kiwango cha uhakika', lambda r: 'uhakika' in r[-1].lower()),
            ('Jibu linaonyesha chanzo cha dataset', lambda r: 'chanzo' in r[-1].lower()),
            ('Dawa ikitajwa, tahadhari ya label ipo',
             lambda r: _no_chemical(r[-1]) or 'label' in r[-1].lower()),
        ],
        'trace': True,
    },
    {
        'name': 'T4 — "Mahindi yangu yana wadudu" (template ipo lakini taarifa hazitoshi)',
        'turns': ['Mahindi yangu yana wadudu'],
        'checks': [
            ('Haitoi template ya dawa mara moja', lambda r: _no_chemical(r[-1])),
            ('Inauliza dalili', lambda r: 'dalili' in r[-1].lower()),
        ],
    },
    {
        'name': 'T5 — Mkulima hajui baadhi ya taarifa (dawa lazima zizuiwe)',
        'turns': [
            'mahindi yangu yana madoa ya kijivu na kahawia kwenye majani',
            'sijui', 'sijui', 'sijui', 'sijui',
        ],
        'checks': [
            ('Haitoi utambuzi taarifa zisipotosha',
             lambda r: 'siwezi kukupa utambuzi' in r[-1].lower()),
            ('Jibu la mwisho halina dawa wala dosage', lambda r: _no_chemical(r[-1])),
            ('Inaelekeza kwa afisa ugani', lambda r: 'afisa ugani' in r[-1].lower()),
        ],
        'trace': True,
    },
    {
        'name': 'T6 — Mkulima anasitisha uchunguzi',
        'turns': ['Mazao yangu yanaumwa', 'acha'],
        'checks': [
            ('Uchunguzi unasitishwa kwa staha', lambda r: 'sitisha' in r[-1].lower()),
        ],
    },
    {
        'name': 'T8 — Zao lisilo kwenye dataset (mtama) halizungushwi',
        'turns': ['Mazao yangu yanaumwa', 'mtama'],
        'checks': [
            ('Inasema wazi haina taarifa za zao hilo', lambda r: 'sina taarifa' in r[-1].lower()),
            ('Haiulizi "zao gani" tena', lambda r: 'zao gani' not in r[-1].lower()),
            ('Haibuni ushauri wa zao hilo', lambda r: _no_chemical(r[-1])),
        ],
    },
    {
        'name': 'T9 — Jibu lisiloeleweka kwa swali la zao halizungushwi',
        'turns': ['Mazao yangu yanaumwa', 'hmm', 'sielewi'],
        'checks': [
            ('Inaacha kuuliza baada ya majaribio 2', lambda r: 'zao gani' not in r[-1].lower()),
        ],
    },
    {
        'name': 'T7 — Bei ya soko inaonya kwamba si bei ya leo',
        'turns': ['bei ya mahindi Dodoma ikoje'],
        'checks': [
            ('Onyo la bei lipo', lambda r: 'thibitisha' in r[-1].lower()),
        ],
    },
]


class Command(BaseCommand):
    help = 'Endesha regression tests za mtiririko wa uchunguzi wa Kilimoni Bot'

    def add_arguments(self, parser):
        parser.add_argument('--offline', action='store_true',
                            help='Usiite Groq — jibu linajengwa kutoka dataset pekee')

    def handle(self, *args, **opts):
        from bot.engine import process_message

        passed = failed = 0
        ctx = patch('bot.groq_ai.get_grounded_response', return_value='') if opts['offline'] else None
        ctx2 = patch('bot.groq_ai.get_groq_response', return_value='') if opts['offline'] else None
        if ctx:
            ctx.start(); ctx2.start()

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
                for label, fn in sc['checks']:
                    try:
                        ok = bool(fn(replies))
                    except Exception:
                        ok = False
                    if ok:
                        passed += 1
                        self.stdout.write(self.style.SUCCESS(f"  ✓ PASS  {label}"))
                    else:
                        failed += 1
                        self.stdout.write(self.style.ERROR(f"  ✗ FAIL  {label}"))

                if sc.get('trace'):
                    last = (Conversation.objects
                            .filter(user__phone_number=phone, message_direction='outbound')
                            .order_by('-created_at').first())
                    if last and last.trace:
                        t = last.trace
                        self.stdout.write('\n  📋 TRACE:')
                        self.stdout.write(f"     chanzo cha jibu : {t.get('source')}")
                        self.stdout.write(f"     uhakika         : {t.get('confidence')}")
                        self.stdout.write(f"     dawa inaruhusiwa: {t.get('chemical_allowed')}")
                        for r in t.get('records_used', []):
                            self.stdout.write(
                                f"     record          : {r['ref']} (score {r['score']}, "
                                f"maneno: {', '.join(r['match_terms'])})")
                        self.stdout.write(f"     ukaguzi         : {t.get('validation')}")

                User.objects.filter(phone_number=phone).delete()
        finally:
            if ctx:
                ctx.stop(); ctx2.stop()

        self.stdout.write('\n' + '═' * 64)
        total = passed + failed
        style = self.style.SUCCESS if failed == 0 else self.style.ERROR
        self.stdout.write(style(f"MATOKEO: {passed}/{total} zimepita"))
