"""Kuelewa kwanza (bot/understand.py): fomu ya AI inathibitishwa, kisha inaongoza moduli."""
import glob
import os
import re
from unittest.mock import patch

from django.test import TestCase, override_settings

from bot import understand
from bot.eval_bank import CASES, check


class FrameLLM:
    """Inaiga AI ya kuelewa: inarudisha fomu iliyopangwa kwa kila ujumbe."""

    def __init__(self, frames):
        self.frames = frames
        self.calls = 0

    def __call__(self, system, user, max_tokens=900):
        if system != understand.SYSTEM:
            return None                       # hatua nyingine za AI hazipo → kanuni
        self.calls += 1
        msg = re.search(r'UJUMBE MPYA WA MKULIMA: "(.*)"\n', user).group(1)
        return self.frames.get(msg)


def fr(goal, **kw):
    base = {'goal': goal, 'topic': None, 'crop': None, 'place': None, 'answer': None,
            'affirmed': [], 'denied': [], 'question': None}
    base.update(kw)
    return base


@override_settings(GROQ_API_KEY='x')
class UnderstandTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from crops.models import Crop
        from diagnosis.importer import import_mhd007
        from advisory.importer import import_files
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        base = os.path.dirname(os.path.dirname(__file__))
        import_mhd007(sorted(glob.glob(os.path.join(base, 'diagnosis', 'fixtures', 'mhd007', '*.xlsx'))))
        import_files(sorted(glob.glob(os.path.join(base, 'advisory', 'fixtures', '*.xlsx'))))

    def ask(self, llm, phone, *msgs):
        from bot.engine import process_message
        with patch('diagnosis.ai_layer._chat', llm):
            return [process_message(phone, m) for m in msgs]

    # ── Uthibitisho wa fomu ──
    def test_invalid_goal_falls_back_to_rules(self):
        with patch('diagnosis.ai_layer._chat', FrameLLM({'Jinsi ya kuvuna': {'goal': 'tengeneza_jibu'}})):
            f = understand.understand('Jinsi ya kuvuna', None, pending='')
        self.assertEqual((f['source'], f['goal'], f['topic']), ('rules', 'gap', 'kuvuna'))

    def test_unknown_crop_and_ungrounded_symptoms_are_dropped(self):
        msg = 'majani yana mashimo'
        llm = FrameLLM({msg: fr('diagnosis', crop='Kahawa ya Brazil', affirmed=['majani yana mashimo', 'mmea umedumaa'])})
        with patch('diagnosis.ai_layer._chat', llm):
            f = understand.understand(msg, None, pending='')
        self.assertEqual(f['source'], 'ai')
        self.assertIsNone(f['crop'])
        self.assertEqual(f['affirmed'], ['majani yana mashimo'])          # "umedumaa" hakulisema

    def test_gap_without_valid_topic_is_not_trusted(self):
        with patch('diagnosis.ai_layer._chat', FrameLLM({'xyz': fr('gap', topic='siasa')})):
            f = understand.understand('xyz', None, pending='')
        self.assertNotEqual(f['goal'], 'gap')

    # ── Uelekezaji ──
    def test_new_phrasing_reaches_the_right_module(self):
        llm = FrameLLM({
            'nataka kujua kama ardhi yangu inafaa kulima mahindi': fr('soil', crop='Mahindi'),
            'nitajuaje kama mahindi yamekomaa?': fr('gap', topic='kuvuna', crop='Mahindi'),
            'mahindi yamekauka kwa jua kali, mvua hakuna kabisa. ni ukame tu au?': fr('abiotic', crop='Mahindi'),
        })
        r = self.ask(llm, '255700001001', 'nataka kujua kama ardhi yangu inafaa kulima mahindi',
                     'nitajuaje kama mahindi yamekomaa?',
                     'mahindi yamekauka kwa jua kali, mvua hakuna kabisa. ni ukame tu au?')
        self.assertIn('udongo', r[0].lower())                              # moduli ya udongo (MHD-004)
        self.assertIn('siku', r[1])                                        # muda wa kukomaa (MHD-003A)
        self.assertIn('siwezi kuthibitisha', r[2])                         # jibu la ukweli
        self.assertEqual(llm.calls, 3)

    def test_complaint_with_real_question_is_answered_with_apology(self):
        msg = 'mbona unanijibu vitu ambavyo sijauliza, mimi nimeuliza bei ya mahindi'
        llm = FrameLLM({msg: fr('complaint', question='bei ya mahindi ikoje'),
                        'bei ya mahindi ikoje': fr('gap', topic='bei na masoko', crop='Mahindi')})
        r = self.ask(llm, '255700001002', msg)[0]
        self.assertTrue(r.startswith('Samahani'))
        self.assertIn('bei na masoko', r)

    def test_ai_answer_is_used_inside_diagnosis(self):
        first = 'mahindi yangu yana mashimo makubwa kwenye majani'
        reply = 'aah nimewaona kidogo tu ndani ya kitovu'
        llm = FrameLLM({first: fr('diagnosis', crop='Mahindi'),
                        reply: fr('answer', answer='yes')})
        r = self.ask(llm, '255700001003', first, reply)
        self.assertIn('Swali 1', r[0])
        self.assertNotIn('Swali 1', r[1])                                  # jibu limekubaliwa, imeendelea

    def test_module_question_ends_pending_diagnosis(self):
        first = 'mahindi yangu yana mashimo makubwa kwenye majani'
        switch = 'kwanza niambie mbegu nzuri ya mahindi kwa kondoa'
        llm = FrameLLM({first: fr('diagnosis', crop='Mahindi'), switch: fr('seed', crop='Mahindi', place='Kondoa')})
        r = self.ask(llm, '255700001004', first, switch)
        self.assertNotIn('Swali', r[1])
        from bot.models import User
        from diagnosis import engine as rx
        self.assertIsNone(rx.get_state(User.objects.get(phone_number='255700001004').session_state))

    def test_ai_failure_keeps_old_path_working(self):
        r = self.ask(FrameLLM({}), '255700001005', 'Jinsi ya kuvuna mahindi')[0]
        self.assertIn('siku', r)

    @override_settings(UNDERSTAND_FIRST=False)
    def test_switch_off(self):
        from bot.engine import understanding_enabled
        self.assertFalse(understanding_enabled())


class EvalBankTests(TestCase):
    """Benki ya ujumbe halisi: ni sahihi kimuundo, na kanuni za maneno (akiba) hazirudi nyuma."""

    @classmethod
    def setUpTestData(cls):
        from crops.models import Crop
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Mpunga', crop_name_en='Rice', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Maharage', crop_name_en='Beans', crop_group='legumes')

    def test_cases_are_well_formed(self):
        ids = [c['id'] for c in CASES]
        self.assertEqual(len(ids), len(set(ids)))
        for c in CASES:
            goals = c['goal'] if isinstance(c['goal'], tuple) else (c['goal'],)
            for g in goals:
                self.assertIn(g, understand.GOALS, c['id'])
            if c.get('topic'):
                self.assertIn(c['topic'], understand.TOPICS, c['id'])

    def test_rule_fallback_floor(self):
        """Kanuni ni akiba tu; zisishuke chini ya kiwango cha leo kwenye kesi za live."""
        live = [c for c in CASES if c['src'] != 'variant']
        passed = sum(1 for c in live if not check(c, understand.rule_frame(c['msg'], c.get('pending', ''))))
        self.assertGreaterEqual(passed, 45, f'{passed}/{len(live)}')


@override_settings(GROQ_API_KEY='x')
class RateLimitTests(TestCase):
    """Live: 429 Too Many Requests. AI ikikataa, tusiendelee kuiomba — kanuni zichukue nafasi mara moja."""

    def tearDown(self):
        from diagnosis import ai_layer
        ai_layer._COOLDOWN.clear()

    @override_settings(GROQ_MODEL='m1', GROQ_FALLBACK_MODELS='m2,m3')
    def test_429_moves_to_next_model(self):
        from unittest.mock import MagicMock
        from diagnosis import ai_layer
        limited = MagicMock(status_code=429, headers={'retry-after': '30'})
        ok = MagicMock(status_code=200, headers={})
        ok.json.return_value = {'choices': [{'message': {'content': '{"goal": "seed"}'}}]}
        ok.raise_for_status.return_value = None
        with patch('requests.post', side_effect=[limited, ok]) as post:
            self.assertEqual(ai_layer._chat('s', 'u'), {'goal': 'seed'})
        self.assertEqual([c.kwargs['json']['model'] for c in post.call_args_list], ['m1', 'm2'])
        self.assertNotIn('reasoning_effort', post.call_args_list[1].kwargs['json'])
        self.assertFalse(ai_layer.rate_limited())                    # m2, m3 bado zinapatikana

    @override_settings(GROQ_MODEL='m1', GROQ_FALLBACK_MODELS='m2')
    def test_all_models_limited_skips_calls(self):
        from unittest.mock import MagicMock
        from diagnosis import ai_layer
        limited = MagicMock(status_code=429, headers={'retry-after': '30'})
        with patch('requests.post', return_value=limited) as post:
            self.assertIsNone(ai_layer._chat('s', 'u'))
            self.assertTrue(ai_layer.rate_limited())
            self.assertIsNone(ai_layer._chat('s', 'u'))
        self.assertEqual(post.call_count, 2)                         # hakuna ombi la ziada

    @override_settings(GROQ_MODEL='old', GROQ_FALLBACK_MODELS='m2')
    def test_decommissioned_model_is_skipped(self):
        from unittest.mock import MagicMock
        from diagnosis import ai_layer
        gone = MagicMock(status_code=404, headers={})
        ok = MagicMock(status_code=200, headers={})
        ok.json.return_value = {'choices': [{'message': {'content': '{"goal": "seed"}'}}]}
        ok.raise_for_status.return_value = None
        with patch('requests.post', side_effect=[gone, ok, ok]) as post:
            ai_layer._chat('s', 'u')
            ai_layer._chat('s', 'u')
        self.assertEqual([c.kwargs['json']['model'] for c in post.call_args_list], ['old', 'm2', 'm2'])

    def test_understanding_falls_back_to_rules_while_limited(self):
        import time
        from diagnosis import ai_layer
        for m in ai_layer.model_chain():
            ai_layer._COOLDOWN[m] = time.time() + 60
        f = understand.understand('Jinsi ya kuvuna', None, pending='')
        self.assertEqual((f['source'], f['goal']), ('rules', 'gap'))
