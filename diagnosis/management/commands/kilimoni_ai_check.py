"""
python manage.py kilimoni_ai_check

Inajaribu tabaka la AI na Groq HALISI (si mock) kwa maneno ya wakulima
yaliyoandikwa kwa njia tofauti, na inaonyesha AI ilielewa nini. Iendeshe
kwenye Render Shell baada ya deploy (inahitaji GROQ_API_KEY na data ya
MHD-007). Haihifadhi chochote kwenye database.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from crops.models import Crop
from diagnosis import ai_layer

SYMPTOM_CASES = [
    # (maneno ya mkulima, dalili ya dataset inayotarajiwa — sehemu ya maandishi)
    ('kuna vitu vinakula mahindi yangu, majani yametobolewa vibaya', 'mashimo'),
    ('mahindi yangu majani yana matundu makubwa makubwa', 'mashimo'),
    ('maize leaves have big holes', 'mashimo'),
    ('mahindi yamedumaa na majani yana michirizi ya manjano', 'njano'),
    ('kuna viwavi wengi sana wanatembea kwa makundi wanakula kila kitu', 'makundi'),
    ('mmea wa katikati umekauka na shina lina vitundu', 'kauka'),
    ('nina swali kuhusu bei ya mbolea', None),        # si dalili — orodha iwe tupu
]
ANSWER_CASES = [
    ('Je, kuna kinyesi cha funza ndani ya kitovu cha mmea?', 'nimeona uchafu mweusi kama unga ndani', 'yes'),
    ('Je, kuna kinyesi cha funza ndani ya kitovu cha mmea?', 'hamna kitu kama hicho nimeangalia', 'no'),
    ('Je, kuna kinyesi cha funza ndani ya kitovu cha mmea?', 'sina uhakika kwa kweli', 'unknown'),
    ('Je, kuna kinyesi cha funza ndani ya kitovu cha mmea?', 'kitovu ndo nini tena?', 'clarify'),
    ('Je, unaona panzi wakiruka shambani?', 'wapo wachache wanarukaruka', 'yes'),
]
EXTENT_CASES = [('karibu robo tatu ya shamba', 75), ('ekari moja kati ya mbili', 50), ('mimea kama mitano tu', 5)]


class Command(BaseCommand):
    help = 'Jaribu tabaka la AI (Groq halisi) kwa maneno tofauti ya wakulima'

    def handle(self, *args, **opts):
        if not getattr(settings, 'GROQ_API_KEY', ''):
            self.stdout.write(self.style.ERROR('GROQ_API_KEY haijawekwa.'))
            return
        if not ai_layer.available():
            self.stdout.write(self.style.ERROR('ai_language imezimwa kwenye Mipangilio.'))
            return
        crop = Crop.objects.filter(crop_name_sw__iexact='mahindi').first()
        if not crop or not ai_layer.symptom_catalog(crop):
            self.stdout.write(self.style.ERROR('Hakuna Mahindi au data ya MHD-007.'))
            return
        ok = total = 0

        def mark(good, line):
            nonlocal ok, total
            total += 1
            ok += good
            self.stdout.write((self.style.SUCCESS('  ✓ ') if good else self.style.ERROR('  ✗ ')) + line)

        self.stdout.write(self.style.MIGRATE_HEADING('\n1. Kuelewa dalili'))
        for text, expect in SYMPTOM_CASES:
            got = ai_layer.understand_symptoms(crop, text) or {'phrases': []}
            phrases = got['phrases']
            good = (not phrases) if expect is None else any(expect in p.lower() for p in phrases)
            mark(good, f'"{text}" → {phrases or "hakuna"}')

        self.stdout.write(self.style.MIGRATE_HEADING('\n2. Kuelewa majibu'))
        for q, reply, expect in ANSWER_CASES:
            got = ai_layer.interpret_answer(q, reply)
            mark(got == expect, f'"{reply}" → {got} (tarajio: {expect})')

        self.stdout.write(self.style.MIGRATE_HEADING('\n3. Kuelewa ukubwa wa tatizo'))
        for reply, expect in EXTENT_CASES:
            got = ai_layer.interpret_extent(reply)
            pct = got[0] if got else None
            mark(pct is not None and abs(pct - expect) <= 15, f'"{reply}" → {pct}% (tarajio: ~{expect}%)')

        self.stdout.write(self.style.MIGRATE_HEADING('\n4. Kuchagua moduli (AI router)'))
        from advisory.profile import route
        for text, expect in [('mwaka jana nililima mahindi, msimu ujao niweke nini shambani', 'rotation'),
                             ('ardhi yangu ni nyekundu na ngumu, mahindi yatastawi?', 'soil'),
                             ('wiki hii mvua imenyesha mara tatu, niingie shambani nipande?', 'planting'),
                             ('nimeambiwa nitafute aina inayowahi kukomaa, ipi bora kwa kwetu', 'seed'),
                             ('bei ya mbolea ya DAP ni ngapi siku hizi', None)]:
            got = route(text)
            mark(got == expect, f'"{text}" → {got} (tarajio: {expect})')

        self.stdout.write(self.style.MIGRATE_HEADING('\n5. Muhtasari (na ukaguzi wake)'))
        facts = {'zao': 'Mahindi', 'tatizo': 'Funza jeshi vamizi', 'tatizo_en': 'Fall Armyworm',
                 'aina': 'mdudu', 'kiwango_cha_uhakika': 'juu sana',
                 'dalili_alizotaja_mkulima': 'majani yametobolewa',
                 'alichothibitisha': ['kuna kinyesi cha funza ndani ya kitovu cha mmea'],
                 'ukubwa_wa_tatizo': 'kubwa', 'linaenea_haraka': False,
                 'ni_hatari_wasiliana_na_afisa_ugani_haraka': False, 'kemikali_inaruhusiwa': True}
        state = {}
        text = ai_layer.summary(facts, state)
        note = (state.get('ai') or [{}])[-1].get('note', '')
        mark(bool(text), f'{text or "imekataliwa: " + note}')

        self.stdout.write(f'\nMATOKEO: {ok}/{total}')
