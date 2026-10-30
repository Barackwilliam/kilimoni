"""Hatua 1 — Eneo (MHD-001): import, kutambua kata/wilaya/mkoa, na bot."""
import glob
import os

from django.test import TestCase

from crops.models import Crop, LocationMapping, Zone

from .importer import import_files
from .location import resolve
from .models import Aez, LocationSynonym, WardLocation

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load():
    return import_files(sorted(glob.glob(os.path.join(FIXTURES, 'MHD-001*.xlsx'))))


class ImportTests(TestCase):
    def test_import_and_rerun_is_idempotent(self):
        r = _load()
        self.assertFalse(r.rolled_back)
        self.assertEqual(WardLocation.objects.count(), 20)
        self.assertEqual(Aez.objects.count(), 7)
        self.assertEqual(LocationSynonym.objects.count(), 40)
        self.assertEqual(WardLocation.objects.get(source_id='LOC-WARD-00001').aez.source_id, 'AEZ-003')
        r2 = _load()
        self.assertEqual(WardLocation.objects.count(), 20)
        self.assertEqual(r2.counts['Kata']['updated'], 20)
        # QA: kisawe cha halmashauri kinaelekeza kata nyingi
        self.assertTrue(any('halmashauri ya wilaya ya kondoa' in w for w in r.warnings))

    def test_dry_run_saves_nothing(self):
        r = import_files(sorted(glob.glob(os.path.join(FIXTURES, 'MHD-001*.xlsx'))), dry_run=True)
        self.assertEqual(r.counts['Kata']['created'], 20)
        self.assertEqual(WardLocation.objects.count(), 0)

    def test_aez_links_existing_zone_by_name(self):
        z = Zone.objects.create(zone_name='Kanda ya Kati yenye ukame wa wastani', rain_pattern_simple='chache')
        _load()
        self.assertEqual(Aez.objects.get(source_id='AEZ-003').zone, z)


class ResolveTests(TestCase):
    def setUp(self):
        _load()

    def test_ward_by_name_and_synonym(self):
        r = resolve('mimi niko changaa, mahindi yangu')
        self.assertEqual((r['level'], r['ward'], r['district'], r['aez_id']), ('ward', 'Changaa', 'Kondoa', 'AEZ-003'))
        self.assertEqual(r['planting_window'], 'Novemba-Januari')
        r = resolve('hondomairo kondoa')
        self.assertEqual(r['location_id'], 'LOC-WARD-00002')

    def test_district_and_region(self):
        self.assertEqual(resolve('natoka kondoa')['level'], 'district')
        self.assertEqual(resolve('mkoa wa dodoma')['level'], 'region')

    def test_duplicate_ward_names_are_narrowed_by_district(self):
        other = WardLocation.objects.create(
            source_id='LOC-X-1', region_name='Mbeya', district_name='Mbarali', ward_name='Changaa',
            aez=Aez.objects.get(source_id='AEZ-001'))
        r = resolve('niko changaa')                       # jina moja, mikoa miwili
        self.assertEqual(r['level'], 'ambiguous')
        self.assertEqual(len(r['candidates']), 2)
        self.assertEqual(resolve('changaa kondoa')['location_id'], 'LOC-WARD-00001')
        self.assertEqual(resolve('changaa mbarali')['location_id'], other.source_id)

    def test_common_words_need_context(self):
        WardLocation.objects.create(source_id='LOC-X-2', region_name='Dodoma', district_name='Kondoa',
                                    ward_name='Kati', aez=Aez.objects.get(source_id='AEZ-003'))
        self.assertIsNone(resolve('mahindi yamekauka kati ya shamba'))
        self.assertEqual(resolve('niko kata ya kati')['ward'], 'Kati')

    def test_unknown_place(self):
        self.assertIsNone(resolve('habari za asubuhi'))


class BotIntegrationTests(TestCase):
    def setUp(self):
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        _load()

    def test_farmer_location_is_remembered(self):
        from bot.engine import process_message
        from bot.models import User
        process_message('255700000101', 'mbegu gani ya mahindi nipande changaa')
        u = User.objects.get(phone_number='255700000101')
        self.assertEqual((u.ward, u.district, u.region, u.aez_code), ('Changaa', 'Kondoa', 'Dodoma', 'AEZ-003'))

    def test_ward_maps_to_zone_through_district(self):
        from bot.engine import detect_location, map_location_to_zone
        z = Zone.objects.create(zone_name='Central', rain_pattern_simple='chache')
        LocationMapping.objects.create(region_name='Dodoma', district_name='Kondoa', zone=z)
        loc = detect_location('niko hondomairo')
        self.assertEqual(loc, 'Hondomairo, Kondoa')
        self.assertEqual(map_location_to_zone(loc), z)
