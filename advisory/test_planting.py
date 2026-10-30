"""Hatua 3 — Wakati wa kupanda (MHD-006 R1–R3 + eneo + mbegu)."""
import datetime
import glob
import os
from unittest.mock import patch

from django.contrib.auth.models import User as AuthUser
from django.test import TestCase
from django.urls import reverse

from crops.models import Crop

from . import planting
from .importer import import_files
from .location import resolve
from .models import Aez, AezAlias, SeasonProfile, WardLocation

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
D = datetime.date


class PlantingBase(TestCase):
    def setUp(self):
        self.maize = Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Mpunga', crop_name_en='Rice', crop_group='cereals')
        self.report = import_files(sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx'))))
        self.changaa = resolve('changaa')
        WardLocation.objects.create(source_id='LOC-T-MBY', region_name='Mbeya', district_name='Mbeya',
                                    ward_name='Iyunga', aez=Aez.objects.get(source_id='AEZ-001'))
        self.mbeya = resolve('iyunga')

    def ask(self, loc, text, day, **kw):
        return planting.advise(self.maize, loc, text, today=day, **kw)


class AezMappingTests(PlantingBase):
    def test_mhd006_zones_mapped_by_name_not_number(self):
        get = lambda e: AezAlias.objects.get(dataset='MHD-006', external_id=e).aez
        self.assertEqual(get('AEZ-002').source_id, 'AEZ-003')     # Kanda ya Kati
        self.assertEqual(get('AEZ-003').source_id, 'AEZ-002')     # Kanda ya Ziwa
        self.assertEqual(get('AEZ-001').source_id, 'AEZ-001')
        self.assertIsNone(get('AEZ-007'))                          # Zanzibar — haipo MHD-001
        self.assertTrue(any('≠ MHD-001 AEZ-002' in w for w in self.report.warnings))
        self.assertEqual(SeasonProfile.objects.get(ext_aez_id='AEZ-002').aez.source_id, 'AEZ-003')

    def test_manual_mapping_survives_reimport_and_updates_records(self):
        from .importer import apply_alias
        alias = AezAlias.objects.get(dataset='MHD-006', external_id='AEZ-002')
        alias.aez, alias.auto_matched = Aez.objects.get(source_id='AEZ-006'), False
        alias.save()
        apply_alias(alias)
        self.assertEqual(SeasonProfile.objects.get(ext_aez_id='AEZ-002').aez.source_id, 'AEZ-006')
        import_files(sorted(glob.glob(os.path.join(FIXTURES, 'MHD-006*.xlsx'))))
        self.assertEqual(SeasonProfile.objects.get(ext_aez_id='AEZ-002').aez.source_id, 'AEZ-006')


class DateTests(TestCase):
    def test_windows(self):
        self.assertEqual(planting.parse_window('16-Dec–10-Jan'), ((12, 16), (1, 10)))
        self.assertEqual(planting.parse_window('Nov 15–Dec 20'), ((11, 15), (12, 20)))
        self.assertEqual(planting.window_dates('16-Dec–10-Jan', D(2027, 1, 5)), (D(2026, 12, 16), D(2027, 1, 10)))
        self.assertEqual(planting.fmt_window('Mar 30–Apr 30'), '30 Machi – 30 Aprili')


class SeasonOnlyTests(PlantingBase):
    """Changaa (Kanda ya Kati): hakuna kalenda ya mahindi, msimu wa kanda unatumika."""

    def test_before_onset_wait(self):
        reply, t = self.ask(self.changaa, 'nipande lini', D(2026, 10, 30))
        self.assertEqual((t['decision'], t['phase']), ('SUBIRI', 'before'))
        self.assertIn('SEASRULE-001', t['rules_used'])
        self.assertIn('15 Novemba – 20 Desemba', reply)

    def test_in_onset_window_asks_about_rain(self):
        reply, t = self.ask(self.changaa, 'nipande lini', D(2026, 11, 25))
        self.assertTrue(t['ask_rain'])
        self.assertIn('ELIG-002', t['rules_used'])
        self.assertIn('mara 2–3', reply)
        reply, t = self.ask(self.changaa, 'mvua zimeanza', D(2026, 11, 25))
        self.assertEqual(t['decision'], 'PANDA_KWA_TAHADHARI')
        self.assertFalse(t['ask_rain'])

    def test_late_without_rain_suggests_early_variety_only(self):
        reply, t = self.ask(self.changaa, 'mvua bado hazijaanza', D(2027, 1, 20))
        self.assertEqual(t['decision'], 'WAIT_OR_EARLY_VARIETY')
        self.assertEqual(t['varieties'], ['SC 403'])                 # siku 90 ≤ siku 100 zilizobaki
        self.assertIn('Epuka SC 513', reply)
        self.assertIn('ALT-001', t['rules_used'])

    def test_false_start(self):
        _, t = self.ask(self.changaa, 'ilinyesha mara moja ikakata', D(2026, 12, 1))
        self.assertEqual(t['decision'], 'WAIT')

    def test_after_season_safety_first(self):
        _, t = self.ask(self.changaa, 'nipande sasa?', D(2027, 5, 10))
        self.assertEqual(t['decision'], 'DO_NOT_PLANT')                # PREC-002
        _, t = self.ask(self.changaa, 'nina kisima, nipande?', D(2027, 5, 10))
        self.assertEqual(t['decision'], 'ALLOW_IRRIGATION_PLANTING')


class CalendarTests(PlantingBase):
    """Mbeya (Nyanda za Juu Kusini): kalenda ya mahindi CAL-000001 ipo."""

    def test_normal_window_with_rain_plant_now(self):
        reply, t = self.ask(self.mbeya, 'mvua zimeanza, nipande?', D(2026, 11, 20))
        self.assertEqual((t['decision'], t['phase']), ('PANDA_SASA', 'normal'))
        for rid in ('PDE-0001', 'WIN-002', 'ELIG-001', 'CAL-000001'):
            self.assertIn(rid, t['rules_used'])
        self.assertIn('16 Novemba – 15 Desemba', reply)

    def test_late_window(self):
        _, t = self.ask(self.mbeya, 'mvua zimeanza', D(2026, 12, 28))
        self.assertEqual((t['decision'], t['phase']), ('PANDA_KWA_TAHADHARI', 'late'))
        self.assertIn('VARLOG-002', t['rules_used'])

    def test_no_location_asks(self):
        reply, t = self.ask(None, 'nipande lini', D(2026, 11, 20))
        self.assertEqual(t['decision'], 'need_location')
        self.assertIn('PDE-0011', t['rules_used'])


class PlantingBotTests(PlantingBase):
    def test_conversation_with_rain_question(self):
        from bot.engine import process_message
        with patch('advisory.planting.timezone.localdate', return_value=D(2026, 11, 25)):
            r1 = process_message('255733000001', 'nipande lini mahindi?')
            r2 = process_message('255733000001', 'niko changaa')
            r3 = process_message('255733000001', 'ndiyo zimeanza')
        self.assertIn('taja mkoa, wilaya au kata', r1)
        self.assertIn('mara 2–3', r2)
        self.assertIn('Unaweza kupanda, kwa tahadhari', r3)
        self.assertNotIn('❓', r3)

    def test_dashboard(self):
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')
        r = self.client.get(reverse('rx_planting'), {'q': 'niko iyunga', 'date': '2026-11-20', 'rain': 'confirmed'})
        self.assertContains(r, 'Unaweza kupanda sasa')
        self.assertContains(r, 'PDE-0001')
        r = self.client.get(reverse('rx_locations'))
        self.assertContains(r, 'Ulinganisho wa AEZ')
        alias = AezAlias.objects.get(dataset='MHD-006', external_id='AEZ-005')
        self.client.post(reverse('rx_locations'), {'alias': alias.pk, 'aez': Aez.objects.get(source_id='AEZ-005').pk})
        alias.refresh_from_db()
        self.assertEqual((alias.aez.source_id, alias.auto_matched), ('AEZ-005', False))
