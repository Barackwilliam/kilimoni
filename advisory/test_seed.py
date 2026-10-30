"""Hatua 2 — Mbegu (MHD-003A + eneo la MHD-001)."""
import glob
import os
import re

from django.contrib.auth.models import User as AuthUser
from django.test import TestCase
from django.urls import reverse

from crops.models import Crop

from . import seed
from .importer import import_files
from .location import resolve
from .models import Aez, SeedDecisionRule, VarietyAgronomy, VarietyRegistry

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
NAMES = re.compile(r'\b(SC ?\d{3}|PAN ?53)\b', re.I)


class SeedBase(TestCase):
    def setUp(self):
        self.maize = Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        self.report = import_files(sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx'))))


class SeedImportTests(SeedBase):
    def test_three_releases_in_order(self):
        self.assertFalse(self.report.rolled_back, self.report.errors)
        self.assertEqual(VarietyRegistry.objects.count(), 4)
        sc403 = VarietyAgronomy.objects.get(name='SC 403')
        self.assertEqual((sc403.maturity_days_min, sc403.maturity_days_max), (75, 90))
        self.assertEqual((sc403.altitude_min, sc403.altitude_max), (500, 1400))
        self.assertIn('AEZ-003', sc403.aez_codes)
        self.assertEqual(sc403.variety.name, 'SC 403')
        self.assertIsNone(VarietyAgronomy.objects.get(name='SC 513').altitude_min)   # "MHD-001" si mita
        rule = SeedDecisionRule.objects.get(source_id='MHD003A-AI-001')
        self.assertEqual(rule.priority_varieties, ['SC 403', 'SC 513', 'SC 529'])
        self.assertTrue(any("'SC 719' haina sifa za kilimo" in w for w in self.report.warnings))
        self.assertFalse(any('MHD-001' in w and 'haina sifa' in w for w in self.report.warnings))


class SeedDecisionTests(SeedBase):
    def test_low_rain_zone_uses_decision_rule(self):
        d = seed.decide(self.maize, Aez.objects.get(source_id='AEZ-003'))
        self.assertEqual([p.name for p in d['ranked']], ['SC 403', 'SC 513', 'SC 529'])
        self.assertEqual(d['rule'].source_id, 'MHD003A-AI-001')
        self.assertEqual(d['band'], 'High')

    def test_zone_without_listed_varieties(self):
        d = seed.decide(self.maize, Aez.objects.get(source_id='AEZ-001'))
        self.assertEqual(d['ranked'], [])
        self.assertEqual(len(d['excluded']), 3)

    def test_high_yield_does_not_use_early_rule(self):
        crit = seed.detect_criterion('nataka mavuno mengi')
        self.assertEqual(crit.intent_code, 'high_yield')
        d = seed.decide(self.maize, Aez.objects.get(source_id='AEZ-003'), crit)
        self.assertIsNone(d['rule'])
        self.assertIn('RULE-AGR-002', d['rules_used'])
        self.assertEqual(d['band'], 'Medium')
        self.assertEqual(d['suggested_missing'], ['SC 719', 'SC 627'])


class SeedAdviceTests(SeedBase):
    def test_no_variety_name_before_location(self):
        reply, trace = seed.advise(self.maize, None, 'mbegu gani ya mahindi')
        self.assertEqual(trace['decision'], 'need_location')
        self.assertIsNone(NAMES.search(reply))                     # MHD003A-AI-005

    def test_recommendation_with_location_and_explanation(self):
        text = 'nataka mbegu ya kukomaa mapema niko changaa'
        reply, trace = seed.advise(self.maize, resolve(text), text)
        self.assertEqual(trace['recommended'][0], 'SC 403')
        self.assertIn('EXP-MZ-002', trace['rules_used'])
        self.assertIn('Kwa nini', reply)
        self.assertIn('siku 75–90', reply)

    def test_named_variety(self):
        reply, trace = seed.advise(self.maize, resolve('kikore'), 'sc-403 inafaa?')
        self.assertEqual(trace['decision'], 'variety_fits')
        reply, trace = seed.advise(self.maize, resolve('kikore'), 'je PAN 53?')
        self.assertEqual(trace['decision'], 'variety_no_profile')
        self.assertIn('sitabahatisha', reply)

    def test_region_with_mixed_zones_asks_for_district(self):
        from .models import WardLocation
        WardLocation.objects.create(source_id='LOC-X-9', region_name='Dodoma', district_name='Mpwapwa',
                                    ward_name='Mazae', aez=Aez.objects.get(source_id='AEZ-001'))
        reply, trace = seed.advise(self.maize, resolve('mkoa wa dodoma'), 'mbegu ya mahindi')
        self.assertEqual(trace['decision'], 'need_location')
        self.assertIn('wilaya au kata', reply)


class SeedBotTests(SeedBase):
    def run_turns(self, phone, turns):
        from bot.engine import process_message
        return [process_message(phone, t) for t in turns]

    def test_asks_location_then_recommends_and_remembers(self):
        r = self.run_turns('255711222001', ['mbegu gani ya mahindi nipande?', 'niko changaa'])
        self.assertIn('taja mkoa, wilaya au kata', r[0])
        self.assertIn('SC 403', r[1])
        r = self.run_turns('255711222001', ['nataka mbegu ya mahindi ya kukomaa mapema'])
        self.assertIn('Changaa', r[0])                                 # eneo kutoka profile

    def test_variety_question_infers_crop(self):
        r = self.run_turns('255711222002', ['je sc403 inafaa?', 'nipo kikore'])
        self.assertIn('Nimetambua mbegu', r[0])
        self.assertIn('Ndiyo, *SC 403*', r[1])

    def test_crop_asked_when_missing(self):
        r = self.run_turns('255711222003', ['nataka mbegu ya kukomaa mapema', 'mahindi', 'kondoa'])
        self.assertIn('zao gani', r[0])
        self.assertIn('SC 403', r[2])

    def test_trace_and_dashboard(self):
        from bot.models import Conversation
        self.run_turns('255711222004', ['mbegu ya mahindi kondoa'])
        c = Conversation.objects.filter(trace__mode='seed_advisor', trace__decision='recommended').latest('created_at')
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)
        self.client.login(username='kilimoni', password='x')
        r = self.client.get(reverse('rx_cases'), {'module': 'seed_advisor'})
        self.assertContains(r, 'Mbegu zimependekezwa')
        r = self.client.get(reverse('conversation_detail', args=[c.pk]))
        self.assertContains(r, 'Mantiki ya ushauri wa mbegu')
        self.assertContains(r, 'MHD003A-AI-001')
        r = self.client.get(reverse('rx_seeds'), {'q': 'SC 529 inafaa changaa?'})
        self.assertContains(r, 'Ndiyo, *SC 529*')
