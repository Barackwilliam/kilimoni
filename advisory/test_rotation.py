"""Hatua 5 — Mzunguko wa mazao (MHD-006 R4)."""
import glob
import os

from django.contrib.auth.models import User as AuthUser
from django.test import TestCase
from django.urls import reverse

from crops.models import Crop

from . import rotation
from .importer import import_files
from .location import resolve
from .models import Aez, CropFamily, RotationSequence, WardLocation

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


class RotationBase(TestCase):
    def setUp(self):
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Mpunga', crop_name_en='Rice', crop_group='cereals')
        files = sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx')))
        self.report = import_files(files)


class RotationImportTests(RotationBase):
    def test_import(self):
        self.assertFalse(self.report.rolled_back, self.report.errors)
        self.assertEqual(CropFamily.objects.get(crop_name='Mahindi').botanical_family, 'Poaceae')
        seq = RotationSequence.objects.get(source_id='SEQ-001')
        self.assertEqual(seq.aez.source_id, 'AEZ-001')                    # kupitia ulinganisho wa MHD-006
        self.assertEqual(seq.seasons[1], 'Maharage/Njegere')


class RotationLogicTests(RotationBase):
    def test_parse(self):
        self.assertEqual(rotation.parse('baada ya mahindi nipande nini?'), ('mahindi', None))
        self.assertEqual(rotation.parse('nipande mpunga baada ya mahindi?'), ('mahindi', 'mpunga'))
        self.assertEqual(rotation.parse('mahindi baada ya mahindi?'), ('mahindi', 'mahindi'))

    def test_same_crop_avoided(self):
        reply, t = rotation.advise('nipande mahindi baada ya mahindi?')
        self.assertEqual(t['decision'], 'avoid')
        for rid in ('ROT-COMP-00001', 'ROTRULE-001', 'ROTEXP-002'):
            self.assertIn(rid, t['rules_used'])
        self.assertIn('10/100', reply)
        self.assertNotIn('nutrient mining', reply)                        # kamusi ya lugha rahisi

    def test_same_family_warning(self):
        _, t = rotation.advise('nipande mpunga baada ya mahindi?')
        self.assertIn('ROTRULE-002', t['rules_used'])

    def test_what_next_uses_zone_sequence(self):
        WardLocation.objects.create(source_id='LOC-T-MBY', region_name='Mbeya', district_name='Mbeya',
                                    ward_name='Iyunga', aez=Aez.objects.get(source_id='AEZ-001'))
        reply, t = rotation.advise('baada ya mahindi nipande nini?', resolve('iyunga'))
        self.assertEqual(t['decision'], 'recommended')
        self.assertIn('SEQ-001', t['rules_used'])
        self.assertIn('Maharage/Njegere', reply)
        reply, t = rotation.advise('baada ya mahindi nipande nini?', resolve('kondoa'))   # Kanda ya Kati
        self.assertNotIn('SEQ-001', t['rules_used'])                       # mfuatano wa kanda nyingine haupewi

    def test_break_rule_and_soil(self):
        reply, t = rotation.advise('nipande nyanya baada ya viazi')
        self.assertEqual(t['decision'], 'avoid')
        self.assertIn('BREAK-001', t['rules_used'])
        self.assertNotIn('sitakisia', reply)
        _, t = rotation.advise('baada ya mahindi nipande nini, udongo wangu ni wa kichanga')
        self.assertIn('SOILROT-002', t['rules_used'])

    def test_planting_question_is_not_rotation(self):
        self.assertFalse(rotation.wants_rotation('nipande lini mahindi baada ya mvua kuanza'))
        self.assertTrue(rotation.wants_rotation('nipande nini baada ya mahindi'))

    def test_no_crop_asks(self):
        reply, t = rotation.advise('mzunguko wa mazao')
        self.assertEqual(t['decision'], 'need_crop')


class RotationBotTests(RotationBase):
    def test_conversation(self):
        from bot.engine import process_message
        r1 = process_message('255755000001', 'nataka ushauri wa mzunguko wa mazao')
        r2 = process_message('255755000001', 'mahindi')
        self.assertIn('msimu uliopita', r1)
        self.assertIn('Nipande nini baada ya Mahindi', r2)

    def test_dashboard(self):
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')
        r = self.client.get(reverse('rx_rotation'), {'q': 'nipande mahindi baada ya mahindi?'})
        self.assertContains(r, '10/100')
        self.assertContains(r, 'Mantiki ya mzunguko')
