import glob
import os

from django.test import TestCase

from crops.models import Crop

from .importer import import_mhd007
from .models import (DEFAULT_SETTINGS, ConfidenceBand, ConfidenceRule, DecisionRule,
                     DiagnosisRule, DifferentialDiagnosis, EngineSetting, FollowupQuestion,
                     Pest, Symptom, Treatment, get_setting)

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
        self.assertEqual(len(FIXTURES), 6)

    def test_dry_run_saves_nothing(self):
        report = import_mhd007(FIXTURES, dry_run=True)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.counts['Pest']['created'], 4)
        self.assertFalse(Pest.objects.exists())

    def test_full_import_links_records(self):
        report = import_mhd007(FIXTURES)
        self.assertEqual(report.errors, [])
        # Maonyo haya ni matatizo halisi ya data ya sample (yameripotiwa kwa mteja)
        self.assertEqual(len(report.warnings), 3)
        self.assertTrue(all('DR-MZ-000' in w and '0.97' in w for w in report.warnings[:2]))
        self.assertIn('DD-MZ-0002: maudhui ni sawa kabisa na DD-MZ-0001', report.warnings[2])

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

    def test_disease_and_decision_engine_links(self):
        import_mhd007(FIXTURES)
        rule = DecisionRule.objects.get(source_id='MHD007B-RUL001')
        self.assertEqual((rule.disease.source_id, rule.pest, rule.confidence), ('DIS001', None, 0.82))

        dr = DiagnosisRule.objects.get(source_id='DR-MZ-0001')
        self.assertEqual((dr.cause_id, dr.base_confidence, dr.growth_stage), ('PST001', 0.9, 'Seedling'))
        dd = DifferentialDiagnosis.objects.get(source_id='DD-MZ-0001')
        self.assertEqual((dd.primary_cause_id, dd.alternative_cause_id), ('PST001', 'PST003'))
        self.assertEqual((dd.if_yes_adjustment, dd.if_no_adjustment), (0.10, -0.15))

        band = ConfidenceBand.objects.get(source_id='High')
        self.assertEqual((band.min_score, band.max_score), (0.75, 0.89))

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


class RulesEngineTests(TestCase):
    """Vigezo 6 vya mteja, kwenye data halisi ya sample ya MHD-007."""

    def setUp(self):
        self.maize = Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize',
                                         crop_group='cereals')
        import_mhd007(FIXTURES)

    def run_turns(self, turns):
        from . import engine as E
        st = E.new_state()
        replies, traces = [], []
        for i, text in enumerate(turns):
            reply, trace, done = E.step(st, text, self.maize if i == 0 else None)
            replies.append(reply)
            traces.append(trace)
            if done:
                break
        return replies, traces, st

    def test_faw_full_diagnosis_with_ipm(self):
        replies, traces, st = self.run_turns(
            ['majani yana mashimo makubwa', 'ndiyo', 'hapana', 'nusu ya shamba'])
        final = traces[-1]
        self.assertEqual((final['decision'], final['diagnosis']), ('diagnosed', 'PST001'))
        self.assertLessEqual(final['confidence'], 0.95)            # confidence_cap
        self.assertIn('DR-MZ-0001', final['rules_used'])           # [4] kanuni
        self.assertIn('CONF002', final['rules_used'])
        self.assertTrue(final['gate']['chemical_allowed'])         # REC-MZ-0001
        self.assertIn('Kwa nini si vingine', replies[-1])          # [3]
        self.assertNotIn('emamectin', replies[-1].lower())         # SAFE001: hakuna majina ya bidhaa

    def test_small_extent_blocks_chemical(self):
        from bot.diagnostic import CHEMICAL_PATTERN
        replies, traces, _ = self.run_turns(
            ['majani yana mashimo makubwa', 'ndiyo', 'hapana', 'mimea michache'])
        self.assertFalse(traces[-1]['gate']['chemical_allowed'])   # [5]
        self.assertIsNone(CHEMICAL_PATTERN.search(replies[-1]))

    def test_symptom_words_do_not_count_as_extent(self):
        # "mashimo makubwa" si "sehemu kubwa ya shamba" — lazima aulizwe ukubwa
        replies, traces, _ = self.run_turns(['majani yana mashimo makubwa', 'ndiyo', 'hapana'])
        self.assertEqual(traces[-1]['asked'], 'extent')

    def test_unknown_answers_end_uncertain_without_repeats(self):
        replies, traces, st = self.run_turns(['majani yana mashimo makubwa'] + ['sijui'] * 5)
        self.assertEqual(traces[-1]['decision'], 'uncertain')
        questions = [ev['question'] for ev in st['evidence']]
        self.assertEqual(len(questions), len(set(questions)))      # [1]
        frass = [q for q in questions if 'frass' in q.lower() or 'kinyesi' in q.lower()]
        self.assertEqual(len(frass), 1)                            # dhana moja, swali moja

    def test_farmer_message_answers_question(self):
        # Mkulima ametaja kinyesi na viwavi — swali la frass/lava halisiulizwi
        replies, traces, st = self.run_turns(
            ['majani yana mashimo makubwa na kinyesi, kuna viwavi ndani ya kamba'])
        self.assertEqual(st['evidence'][0]['via'], 'farmer_message')
        self.assertTrue(st['candidates']['PST001']['confirmed'])
        self.assertNotIn('frass', replies[-1].lower())

    def test_critical_disease_escalates_without_chemical(self):
        replies, traces, _ = self.run_turns(
            ['majani yana mistari ya njano na mmea umedumaa', 'ndiyo', 'shamba lote'])
        final = traces[-1]
        self.assertEqual(final['diagnosis'], 'DIS001')
        self.assertIn('ESC-MZ-001', final['gate']['escalations'])
        self.assertFalse(final['gate']['chemical_allowed'])

    def test_unmatched_symptoms_are_not_invented(self):
        replies, traces, _ = self.run_turns(['majani yana madoa ya kijivu'])
        self.assertEqual(traces[-1]['decision'], 'no_rule_matched')   # [6]
