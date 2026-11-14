"""Kipimo cha ubora: benki nzima ya mazungumzo (bot/quality_bank.py) kupitia bot, bila AI."""
import glob
import os
from unittest.mock import patch

from django.test import TestCase

from bot import quality
from bot.quality_bank import all_conversations, turn_count


class QualityGateTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from crops.models import Crop
        from diagnosis.importer import import_mhd007
        from advisory.importer import import_files
        base = os.path.dirname(os.path.dirname(__file__))
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Mpunga', crop_name_en='Rice', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Maharage', crop_name_en='Beans', crop_group='legumes')
        import_mhd007(sorted(glob.glob(os.path.join(base, 'diagnosis', 'fixtures', 'mhd007', '*.xlsx'))))
        import_files(sorted(glob.glob(os.path.join(base, 'advisory', 'fixtures', '*.xlsx'))))

    def test_bank_is_large_enough(self):
        self.assertGreaterEqual(turn_count(), 300)

    def test_no_invariant_violations_and_understanding_floor(self):
        with patch('diagnosis.ai_layer._chat', return_value=None):
            stats = quality.run(all_conversations())
        msg = '\n'.join(f"{c} #{j + 1} {m!r}: {e} → {r[:120]!r}" for c, j, m, e, r in stats['violations'])
        self.assertEqual(stats['violations'], [], msg)
        rate = stats['expect_ok'] / stats['expect_total']
        self.assertGreaterEqual(rate, 0.90, f"uelewa {stats['expect_ok']}/{stats['expect_total']}")

    def test_checks_catch_known_bad_replies(self):
        bad = [
            ("Ninajua tunaongelea *Mahindi*, lakini nahitaji kidogo zaidi ili nikupe jibu sahihi.", 'legacy'),
            ("Bei za Takriban (2024): Singida TZS 350-600/kg", 'invented'),
            ("Nyunyiza dawa ya kuhifadhi (Actellic Super)", 'invented'),
            ("DAP – gramu 50-70 kwa shimo", 'invented'),
            ("Uko mkoa gani?", 'legacy'),
        ]
        for text, kind in bad:
            self.assertTrue(any(e.startswith(kind) for e in quality.check_reply(text, None, '')), text)
        self.assertIn('repeat', quality.check_reply('abc', 'abc', ''))
