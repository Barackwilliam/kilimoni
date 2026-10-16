import glob
import os

from django.test import TestCase

from crops.models import Crop

from .importer import import_mhd007
from .models import (DEFAULT_SETTINGS, ConfidenceRule, DecisionRule, EngineSetting,
                     FollowupQuestion, Pest, Symptom, Treatment, get_setting)

FIXTURES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'fixtures', 'mhd007', '*.xlsx')))


class EngineSettingTests(TestCase):
    def test_defaults_seeded_by_migration(self):
        self.assertEqual(
            set(EngineSetting.objects.values_list('key', flat=True)),
            set(DEFAULT_SETTINGS))
        self.assertEqual(get_setting('diagnosis_threshold'), 0.75)
        self.assertEqual(get_setting('range_strategy', cast=None), 'mid')

    def test_admin_change_wins(self):
        EngineSetting.objects.filter(key='label_medium').update(value='0.6')
        self.assertEqual(get_setting('label_medium'), 0.6)

    def test_missing_row_falls_back_to_default(self):
        EngineSetting.objects.filter(key='confidence_cap').delete()
        self.assertEqual(get_setting('confidence_cap'), 0.95)


class ImportMHD007Tests(TestCase):
    def setUp(self):
        self.maize = Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize',
                                         crop_group='cereals')

    def test_fixtures_present(self):
        self.assertEqual(len(FIXTURES), 4)

    def test_dry_run_saves_nothing(self):
        report = import_mhd007(FIXTURES, dry_run=True)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.counts['Pest']['created'], 4)
        self.assertFalse(Pest.objects.exists())

    def test_full_import_links_records(self):
        report = import_mhd007(FIXTURES)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

        sym = Symptom.objects.get(source_id='SYM001')
        self.assertEqual(sym.crop, self.maize)
        self.assertEqual(set(sym.likely_pests.values_list('source_id', flat=True)),
                         {'PST001', 'PST003', 'PST010'})

        fu1 = FollowupQuestion.objects.get(source_id='FU0001')
        self.assertEqual((fu1.if_yes_min, fu1.if_yes_max), (0.15, 0.30))
        self.assertEqual((fu1.if_no_min, fu1.if_no_max), (-0.05, -0.20))
        self.assertEqual(fu1.symptom, sym)
        # R0002 (Key Differentiator) inatumia swali la FU0001
        self.assertTrue(fu1.is_key_differentiator)
        self.assertFalse(FollowupQuestion.objects.get(source_id='FU0002').is_key_differentiator)

        r2 = DecisionRule.objects.get(source_id='R0002')
        self.assertEqual((r2.pest.source_id, r2.confidence, r2.followup), ('PST001', 0.85, fu1))

        self.assertEqual(ConfidenceRule.objects.get(source_id='CONF001').condition_code, 'symptom_match')
        self.assertEqual(ConfidenceRule.objects.get(source_id='CONF002').condition_code, 'key_differentiator')

        # Treatment imeunganishwa kwa jina (Linked_Diagnosis)
        self.assertEqual(Treatment.objects.get(source_id='TRT-MZ-001').pest.source_id, 'PST001')
        self.assertEqual(Treatment.objects.get(source_id='TRT-MZ-002').pest.source_id, 'PST002')
        self.assertEqual(Treatment.objects.get(source_id='TRT-MZ-001').steps.count(), 2)

    def test_reimport_updates_and_keeps_admin_edits(self):
        import_mhd007(FIXTURES)
        ConfidenceRule.objects.filter(source_id='CONF001').update(condition_code='other')
        report = import_mhd007(FIXTURES)
        self.assertEqual(report.counts['Pest'], {'created': 0, 'updated': 4})
        self.assertEqual(Pest.objects.count(), 4)
        self.assertEqual(ConfidenceRule.objects.get(source_id='CONF001').condition_code, 'other')

    def test_rollback_when_failures_exceed_limit(self):
        import tempfile
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '03_Safety_Compliance'
        ws.append(['Safety_ID', 'Topic', 'Rule'])
        ws.append(['SAFE001', 'PPE', 'PPE required'])
        ws = wb.create_sheet('02_Treatment_Protocols')
        ws.append(['Protocol_ID', 'Treatment_ID', 'Step_Order', 'Farmer_Action_Kiswahili'])
        ws.append(['PROT-X', 'TRT-HAIPO', 1, 'Kagua shamba'])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'MHD-007E_test.xlsx')
            wb.save(path)
            report = import_mhd007([path])
        self.assertEqual(len(report.errors), 1)
        self.assertTrue(report.rolled_back)
        # Row nzuri (SAFE001) nayo imerudishwa nyuma — batch nzima
        from .models import SafetyRule
        self.assertFalse(SafetyRule.objects.exists())
