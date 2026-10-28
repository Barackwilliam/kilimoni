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
