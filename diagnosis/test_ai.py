"""
Tabaka la AI la lugha — majaribio kwa LLM bandia (hakuna mtandao).

LLM bandia inajibu kama Groq ingejibu kwa kila hatua, ili tuthibitishe:
  - maneno tofauti ya mkulima yanaeleweka na kuingia kwenye kanuni zilezile
  - AI haiwezi kuongeza dalili isiyo kwenye orodha ya dataset
  - jibu la AI linalotaja dawa / tatizo jingine / namba linakataliwa
  - AI ikishindwa, injini inaendelea kwa kanuni kama kawaida
"""
import os
import re
from unittest.mock import patch

from django.test import TestCase, override_settings

from crops.models import Crop

from .importer import import_mhd007

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'mhd007')


class FakeLLM:
    """Inaiga Groq kwa kusoma aina ya prompt."""

    def __init__(self, symptom='mashimo makubwa kwenye majani', answers=None, extent=None,
                 summary='Pole sana. Dalili ulizoeleza zinaonyesha funza jeshi vamizi. Fuata hatua hizi mapema.',
                 symptom_ids=None, fail=False):
        self.symptom, self.answers, self.extent = symptom, answers or {}, extent
        self.summary_text, self.symptom_ids, self.fail = summary, symptom_ids, fail
        self.calls = []

    def __call__(self, system, user, max_tokens=900):
        self.calls.append(user)
        if self.fail:
            return None
        if 'ORODHA YA DALILI' in user:
            if self.symptom_ids is not None:
                return {'matches': self.symptom_ids, 'growth_stage': None, 'extent_pct': None, 'spreading': False}
            ids = [m.group(1) for m in re.finditer(r'^(S\d+): (.+)$', user, re.M)
                   if self.symptom and m.group(2).strip().lower() == self.symptom]
            return {'matches': ids[:1], 'growth_stage': None, 'extent_pct': None, 'spreading': False}
        if 'MASWALI:' in user:
            return {'answers': {}}
        if 'Swali tuliloliuliza' in user:
            reply = re.search(r'Jibu lake: "(.+)"', user).group(1)
            return {'answer': self.answers.get(reply, 'unknown')}
        if 'kiasi gani cha shamba' in user:
            return {'extent_pct': self.extent, 'spreading': False}
        if 'Andika aya FUPI' in user:
            return {'text': self.summary_text}
        return None


@override_settings(GROQ_API_KEY='test-key')
class AILanguageLayerTests(TestCase):
    def setUp(self):
        self.maize = Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        import_mhd007(sorted(os.path.join(FIXTURES, f) for f in os.listdir(FIXTURES)))

    def run_turns(self, turns, fake):
        from . import engine as E
        st = E.new_state()
        replies, traces = [], []
        with patch('diagnosis.ai_layer._chat', fake):
            for i, text in enumerate(turns):
                reply, trace, done = E.step(st, text, self.maize if i == 0 else None)
                replies.append(reply)
                traces.append(trace)
                if done:
                    break
        return replies, traces, st

    def test_farmer_own_words_reach_the_same_rules(self):
        fake = FakeLLM(answers={
            'nimeona uchafu mweusi kama unga katikati ya mmea': 'yes',
            'sijawaona hao kabisa shambani': 'no',
        }, extent=50)
        replies, traces, st = self.run_turns([
            'kuna vitu vinakula mahindi yangu, majani yametobolewa vibaya',
            'nimeona uchafu mweusi kama unga katikati ya mmea',
            'sijawaona hao kabisa shambani',
            'kama mistari kumi kati ya ishirini hivi',
        ], fake)
        final = traces[-1]
        self.assertEqual((final['decision'], final['diagnosis']), ('diagnosed', 'PST001'))
        self.assertIn('DR-MZ-0001', final['rules_used'])           # kanuni ndizo zimeamua
        self.assertEqual(final['extent'], 50)                       # AI ilielewa ukubwa
        self.assertTrue(final['gate']['chemical_allowed'])
        self.assertIn('Pole sana', replies[-1])                     # muhtasari wa kibinadamu
        steps = [a['step'] for a in final['ai']]
        self.assertEqual(steps[:2], ['symptoms', 'preanswered'])
        self.assertIn('answer', steps)
        self.assertIn('summary', steps)

    def test_without_ai_the_same_words_are_not_understood(self):
        from . import engine as E
        from .models import EngineSetting
        EngineSetting.objects.update_or_create(key='ai_language', defaults={'value': '0'})
        st = E.new_state()
        reply, trace, done = E.step(st, 'kuna vitu vinakula mahindi yangu, majani yametobolewa vibaya', self.maize)
        self.assertEqual(trace['decision'], 'no_rule_matched')

    def test_invented_symptoms_are_rejected(self):
        fake = FakeLLM(symptom_ids=['S999', 'majani yana kutu'])
        replies, traces, st = self.run_turns(['kuna vitu vinakula mahindi yangu sana'], fake)
        self.assertEqual(traces[-1]['decision'], 'no_rule_matched')     # kigezo 6: haibuni
        self.assertFalse(st['ai'][0]['accepted'])
        self.assertEqual(st['ai'][0]['output']['rejected_ids'], ['S999', 'majani yana kutu'])

    def test_clarify_explains_without_counting(self):
        fake = FakeLLM(answers={'hiyo kitovu cha mmea ni nini?': 'clarify'})
        replies, traces, st = self.run_turns(
            ['majani yana mashimo makubwa', 'hiyo kitovu cha mmea ni nini?', 'ndiyo'], fake)
        self.assertIn('Ninachouliza ni', replies[1])
        self.assertTrue(traces[1]['clarify'])
        self.assertEqual(st['evidence'][0]['answer'], 'yes')            # swali lilelile, jibu la pili
        self.assertEqual(len(st['evidence']), 1)

    def test_short_answers_do_not_call_ai(self):
        fake = FakeLLM()
        self.run_turns(['majani yana mashimo makubwa', 'ndiyo', 'hapana'], fake)
        self.assertFalse(any('Swali tuliloliuliza' in c for c in fake.calls))

    def test_unsafe_summary_is_dropped(self):
        for bad in ('Tumia emamectin haraka kuua funza jeshi vamizi.',
                    'Huenda ni panzi au funza jeshi vamizi.',
                    'Uhakika ni 95 kwa mia.',
                    'Mimi ni AI na nimechagua funza jeshi vamizi.'):
            fake = FakeLLM(summary=bad)
            replies, traces, st = self.run_turns(
                ['majani yana mashimo makubwa', 'ndiyo', 'hapana', 'nusu ya shamba'], fake)
            self.assertNotIn(bad, replies[-1], bad)
            self.assertIn('Dalili zinaendana sana', replies[-1])       # ujumbe wa dataset unarudi
            self.assertFalse(next(a for a in st['ai'] if a['step'] == 'summary')['accepted'])

    def test_ai_failure_falls_back_to_rules(self):
        fake = FakeLLM(fail=True)
        replies, traces, st = self.run_turns(
            ['majani yana mashimo makubwa', 'ndiyo', 'hapana', 'nusu ya shamba'], fake)
        self.assertEqual(traces[-1]['diagnosis'], 'PST001')
        self.assertIn('Dalili zinaendana sana', replies[-1])

    def test_validate_summary(self):
        from .ai_layer import validate_summary
        ok = 'Pole sana. Dalili zako zinaonyesha funza jeshi vamizi; anza hatua za udhibiti mapema.'
        self.assertIsNone(validate_summary(ok.replace('udhibiti', 'kuzuia'), ['Funza jeshi vamizi']))
        self.assertIsNotNone(validate_summary('Nyunyizia dawa leo.', ['Funza jeshi vamizi']))
        self.assertIsNotNone(validate_summary('neno ' * 70, ['Funza jeshi vamizi']))


@override_settings(GROQ_API_KEY='test-key')
class GroqCallTests(TestCase):
    def test_retries_without_json_mode_and_parses_fenced_json(self):
        from unittest.mock import MagicMock
        from . import ai_layer
        bad = MagicMock(status_code=400)
        good = MagicMock(status_code=200)
        good.json.return_value = {'choices': [{'message': {'content': 'Hili hapa:\n```json\n{"answer": "yes"}\n```'}}]}
        with patch('requests.post', side_effect=[bad, good]) as post:
            out = ai_layer._chat('s', 'u')
        self.assertEqual(out, {'answer': 'yes'})
        self.assertNotIn('response_format', post.call_args_list[1].kwargs['json'])

    def test_network_error_returns_none(self):
        from . import ai_layer
        with patch('requests.post', side_effect=OSError('down')):
            self.assertIsNone(ai_layer._chat('s', 'u'))
