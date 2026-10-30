"""Majaribio ya kurasa za Injini ya Uchunguzi kwenye dashboard."""
import glob
import os

from django.contrib.auth.models import User as AuthUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from crops.models import Crop
from diagnosis.models import EngineSetting, FarmerTerm, Pest

FIXTURES = os.path.join(os.path.dirname(__file__), '..', 'diagnosis', 'fixtures', 'mhd007')


def _upload(name):
    with open(name, 'rb') as fh:
        return SimpleUploadedFile(os.path.basename(name), fh.read(),
                                  content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class RxDashboardTests(TestCase):
    def setUp(self):
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        # Mteja: mtumiaji wa kawaida (si superuser) — lazima aweze kutumia kurasa hizi
        self.user = AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')

    def test_pages_open_for_client(self):
        for name in ('rx_home', 'rx_settings', 'rx_cases'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_preview_saves_nothing_then_confirm_imports(self):
        files = [_upload(p) for p in sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx')))]
        r = self.client.post(reverse('rx_preview'), {'files': files})
        self.assertContains(r, 'Hifadhi data hii')
        self.assertEqual(Pest.objects.count(), 0)                 # hakiki = dry run
        r = self.client.post(reverse('rx_confirm'), follow=True)
        self.assertContains(r, 'Data imehifadhiwa')
        self.assertEqual(Pest.objects.count(), 4)

    def test_non_excel_is_rejected(self):
        bad = SimpleUploadedFile('notes.txt', b'hello')
        r = self.client.post(reverse('rx_preview'), {'files': [bad]})
        self.assertContains(r, 'si faili la .xlsx')
        self.assertNotContains(r, 'Hifadhi data hii')

    def test_settings_validation(self):
        self.client.post(reverse('rx_settings'), {'action': 'settings', 'diagnosis_threshold': '0.8',
                                                  'confidence_cap': '7', 'range_strategy': 'min'})
        vals = dict(EngineSetting.objects.values_list('key', 'value'))
        self.assertEqual(vals['diagnosis_threshold'], '0.8')
        self.assertEqual(vals['range_strategy'], 'min')
        self.assertNotEqual(vals.get('confidence_cap'), '7')      # nje ya 0.5–1: imekataliwa

    def test_glossary_add_and_toggle(self):
        self.client.post(reverse('rx_settings'), {'action': 'term_add', 'term': 'buu', 'plain': 'funza mdogo'})
        t = FarmerTerm.objects.get(term='buu')
        self.client.post(reverse('rx_settings'), {'action': 'term_toggle', 'pk': t.pk})
        t.refresh_from_db()
        self.assertFalse(t.is_active)

    def test_case_trace_page(self):
        from bot.engine import process_message
        from diagnosis.importer import import_mhd007
        import_mhd007(sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx'))))
        phone = '255700000001'
        for text in ['mahindi yangu yana mashimo makubwa kwenye majani', 'ndiyo', 'hapana', 'nusu ya shamba']:
            process_message(phone, text)
        r = self.client.get(reverse('rx_cases'))
        self.assertContains(r, 'Funza jeshi vamizi')
        from bot.models import Conversation
        c = Conversation.objects.filter(trace__decision='diagnosed').latest('created_at')
        r = self.client.get(reverse('conversation_detail', args=[c.pk]))
        self.assertContains(r, 'Ulinganisho wa visababishi')
        self.assertContains(r, 'DR-MZ-0001')
        self.assertContains(r, 'Maelekezo ya mfumo')               # sentensi iliyoondolewa inaonekana hapa


class RxAITraceTests(TestCase):
    """Mazungumzo kamili kupitia bot + AI bandia → trace ya AI inaonekana kwenye dashboard."""

    def setUp(self):
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')

    def test_farmer_words_end_to_end(self):
        from unittest.mock import patch
        from django.test import override_settings
        from bot.engine import process_message
        from bot.models import Conversation
        from diagnosis.importer import import_mhd007
        from diagnosis.test_ai import FakeLLM
        import_mhd007(sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx'))))
        fake = FakeLLM(answers={'nimeona uchafu mweusi kama unga katikati ya mmea': 'yes',
                                'sijawaona hao kabisa shambani': 'no'})
        phone = '255700000077'
        with override_settings(GROQ_API_KEY='x'), patch('diagnosis.ai_layer._chat', fake):
            first = process_message(phone, 'kuna vitu vinakula mahindi yangu, majani yametobolewa vibaya')
            self.assertIn('Swali 1', first)                       # uchunguzi umeanza moja kwa moja
            process_message(phone, 'nimeona uchafu mweusi kama unga katikati ya mmea')
            process_message(phone, 'sijawaona hao kabisa shambani')
            final = process_message(phone, 'nusu ya shamba')
        self.assertIn('Funza jeshi vamizi', final)
        c = Conversation.objects.filter(trace__decision='diagnosed').latest('created_at')
        r = self.client.get(reverse('conversation_detail', args=[c.pk]))
        self.assertContains(r, 'Kazi ya AI')
        self.assertContains(r, 'Imekubaliwa')


class RxLocationDashboardTests(TestCase):
    def setUp(self):
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')

    def test_upload_mhd001_and_try_location(self):
        from advisory.models import WardLocation
        path = glob.glob(os.path.join(os.path.dirname(__file__), '..', 'advisory', 'fixtures', 'MHD-001*.xlsx'))[0]
        r = self.client.post(reverse('rx_preview'), {'files': [_upload(path)]})
        self.assertContains(r, 'Ushauri wa kilimo (MHD-001')
        self.assertContains(r, 'Hifadhi data hii')
        self.assertEqual(WardLocation.objects.count(), 0)
        self.client.post(reverse('rx_confirm'))
        self.assertEqual(WardLocation.objects.count(), 20)
        r = self.client.get(reverse('rx_locations'), {'q': 'niko hondomairo'})
        self.assertContains(r, 'Hondomairo')
        self.assertContains(r, 'AEZ-003')
        r = self.client.get(reverse('rx_home'))
        self.assertContains(r, 'Kata (MHD-001)')

    def test_mixed_upload_routes_to_both_importers(self):
        files = [_upload(p) for p in sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx')))]
        files.append(_upload(glob.glob(os.path.join(os.path.dirname(__file__), '..', 'advisory', 'fixtures', 'MHD-001*.xlsx'))[0]))
        r = self.client.post(reverse('rx_preview'), {'files': files})
        self.assertContains(r, 'Uchunguzi wa matatizo (MHD-007)')
        self.assertContains(r, 'Ushauri wa kilimo (MHD-001')
