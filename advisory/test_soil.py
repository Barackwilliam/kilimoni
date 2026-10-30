"""Hatua 4 — Udongo (MHD-004 R1–R3)."""
import glob
import os

from django.contrib.auth.models import User as AuthUser
from django.test import TestCase
from django.urls import reverse

from crops.models import Crop

from . import soil
from .importer import import_files
from .models import SoilRanking, SoilSuitability, SoilType

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


class SoilBase(TestCase):
    def setUp(self):
        self.maize = Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Mpunga', crop_name_en='Rice', crop_group='cereals')
        self.report = import_files(sorted(glob.glob(os.path.join(FIXTURES, 'MHD-004*.xlsx'))))


class SoilImportTests(SoilBase):
    def test_three_releases(self):
        self.assertFalse(self.report.rolled_back, self.report.errors)
        self.assertEqual(SoilType.objects.filter(kind='wrb').count(), 2)
        self.assertEqual(SoilType.objects.filter(kind='local').count(), 2)
        self.assertEqual(SoilSuitability.objects.get(source_id='SCROP-00001').score, 62)
        self.assertIsNone(SoilRanking.objects.get(source_id='RANK-00001').soil)      # Andosols haipo R1
        self.assertTrue(any('Andosols' in w for w in self.report.warnings))


class IdentifyTests(SoilBase):
    def test_farmer_words(self):
        self.assertEqual(soil.identify('udongo wangu ni mwekundu').source_id, 'SOL-WRB-001')
        self.assertEqual(soil.identify('nina udongo wa kichanga').source_id, 'SOL-LOC-001')
        self.assertEqual(soil.identify('ni tifutifu').source_id, 'SOL-LOC-002')
        self.assertEqual(soil.identify('alisols').source_id, 'SOL-WRB-002')
        self.assertIsNone(soil.identify('udongo wangu ni mzuri sana'))


class AdviceTests(SoilBase):
    def test_low_suitability_needs_improvement(self):
        reply, t = soil.advise(self.maize, 'udongo wangu ni mwekundu')
        self.assertEqual(t['decision'], 'not_suitable_without_improvement')
        self.assertIn('62/100', reply)
        self.assertIn('Kabla ya kupanda', reply)
        self.assertIn('CONS-001', t['rules_used'])
        self.assertNotIn('organic matter', reply)                     # kamusi ya lugha rahisi
        self.assertNotIn('Usipendekeze', reply)                       # maelekezo ya mfumo hayaendi kwa mkulima

    def test_no_assessment_shows_best_soils(self):
        reply, t = soil.advise(self.maize, 'alisols')
        self.assertEqual(t['decision'], 'no_assessment')
        self.assertIn('Andosols (85/100)', reply)

    def test_sandy_rules_only_for_sandy(self):
        _, t = soil.advise(None, 'udongo wa kichanga')
        self.assertIn('RULE-SOIL-002', t['rules_used'])
        self.assertIn('CONS-002', t['rules_used'])                    # kichanga ↔ Arenosols (RULE-SOIL-002)
        _, t = soil.advise(None, 'tifutifu wa kichanga')
        self.assertNotIn('RULE-SOIL-002', t['rules_used'])

    def test_unknown_soil_asks(self):
        reply, t = soil.advise(self.maize, 'udongo wangu unafaa?')
        self.assertEqual(t['decision'], 'need_soil')
        self.assertIn('kichanga, tifutifu, mfinyanzi', reply)


class SoilBotTests(SoilBase):
    def test_ask_then_answer(self):
        from bot.engine import process_message
        r1 = process_message('255744000001', 'udongo wangu unafaa mahindi?')
        r2 = process_message('255744000001', 'ni mwekundu')
        self.assertIn('kichanga, tifutifu', r1)
        self.assertIn('62/100', r2)

    def test_dashboard(self):
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')
        r = self.client.get(reverse('rx_soil'), {'q': 'udongo wangu ni mwekundu', 'crop': self.maize.pk})
        self.assertContains(r, '62/100')
        self.assertContains(r, 'Mantiki ya ushauri wa udongo')
