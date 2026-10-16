from django.test import TestCase

from .models import (DEFAULT_SETTINGS, EngineSetting, FollowupQuestion, Pest,
                     Symptom, get_setting)


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


class RelationTests(TestCase):
    def test_symptom_routes(self):
        faw = Pest.objects.create(source_id='PST001', name_en='Fall Armyworm',
                                  name_sw='Funza jeshi vamizi')
        borer = Pest.objects.create(source_id='PST003', name_en='Maize Stem Borer')
        sym = Symptom.objects.create(source_id='SYM001',
                                     farmer_description_sw='Majani yana mashimo',
                                     keywords='mashimo; majani yametobolewa;')
        sym.likely_pests.add(faw, borer)
        fu = FollowupQuestion.objects.create(
            source_id='FU0001', question_sw='Je, kuna kinyesi cheusi?',
            if_yes_min=0.15, if_yes_max=0.30)
        fu.symptoms.add(sym)
        fu.yes_routes_to.add(faw)

        self.assertEqual(sym.keyword_list(), ['mashimo', 'majani yametobolewa'])
        self.assertEqual(list(sym.followups.all()), [fu])
        self.assertEqual(list(faw.followups_yes.all()), [fu])
