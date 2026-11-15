"""Wakala wa AI (bot/agent.py): anaelewa, anatumia dataset kama marejeo, hajibu kwa kubuni."""
import glob
import json
import os
import re
from unittest.mock import patch

from django.test import TestCase, override_settings


class Script:
    """Inaiga AI yenye zana: kila ujumbe wa mkulima una mfululizo wa majibu (zana au maandishi)."""

    def __init__(self, plans):
        self.plans = plans          # {maneno_ya_ujumbe: [hatua, ...]}
        self.calls = []

    def __call__(self, messages, tools, **kw):
        user_msgs = [m for m in messages if m['role'] == 'user' and not m['content'].startswith('[UKAGUZI')]
        last = user_msgs[-1]['content']
        key = next(k for k in self.plans if k in last)
        step = len([m for m in messages if m['role'] in ('assistant',)
                    and messages.index(m) > messages.index(user_msgs[-1])])
        plan = self.plans[key]
        self.calls.append((key, step, messages))
        item = plan[min(step, len(plan) - 1)]
        if callable(item):
            item = item(messages)
        if isinstance(item, dict) and 'tool' in item:
            return {'content': '', 'tool_calls': [{'id': f'c{step}', 'type': 'function', 'function': {
                'name': item['tool'], 'arguments': json.dumps(item.get('args', {}))}}]}
        return {'content': item, 'tool_calls': []}


@override_settings(GROQ_API_KEY='x', AGENT_MODE=True)
class AgentTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from crops.models import Crop
        from diagnosis.importer import import_mhd007
        from advisory.importer import import_files
        base = os.path.dirname(os.path.dirname(__file__))
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        import_mhd007(sorted(glob.glob(os.path.join(base, 'diagnosis', 'fixtures', 'mhd007', '*.xlsx'))))
        import_files(sorted(glob.glob(os.path.join(base, 'advisory', 'fixtures', '*.xlsx'))))

    def ask(self, script, phone, *msgs):
        from bot.engine import process_message
        with patch('diagnosis.ai_layer.chat_tools', script), patch('diagnosis.ai_layer._chat', return_value=None):
            return [process_message(phone, m) for m in msgs]

    def test_meta_question_is_answered_naturally(self):
        s = Script({'Taarifa unatoa wapi': ["Taarifa zangu zinatoka kwenye dataset za kitaalamu zilizoandaliwa na "
                                            "kuthibitishwa na timu ya KILIMONI LABS — kuhusu wadudu na magonjwa, "
                                            "mbegu bora, kalenda za kupanda, udongo na mzunguko wa mazao."]})
        r = self.ask(s, '255700003001', 'Taarifa unatoa wapi wewe')[0]
        self.assertIn('KILIMONI LABS', r)
        self.assertNotIn('Una swali lolote la shamba lako', r)          # si template ya utambulisho

    def test_seed_question_uses_dataset_tool_then_writes(self):
        def write(messages):
            tool = json.loads([m for m in messages if m['role'] == 'tool'][-1]['content'])
            name = re.search(r'SC ?\d+', tool['jibu_la_data']).group(0)
            return f"Kwa Kikore, mbegu ninayokushauri kwanza ni *{name}* kwa sababu inaendana na hali ya kanda yako."
        s = Script({'mbegu itakayonifaa': [{'tool': 'mbegu_bora', 'args': {'zao': 'mahindi', 'eneo': 'kikore'}}, write]})
        r = self.ask(s, '255700003002', 'nisaidie kujua mbegu itakayonifaa huku kikore, mahindi')[0]
        self.assertIn('Kwa Kikore', r)
        from bot.models import Conversation
        t = Conversation.objects.filter(message_direction='outbound').latest('id').trace
        self.assertEqual((t['mode'], t['tools'][0]['name']), ('agent', 'mbegu_bora'))

    def test_missing_data_is_said_plainly(self):
        s = Script({'bei ya mahindi': ["Samahani, bado sina taarifa za bei na masoko kwenye data yangu. Afisa ugani "
                                       "au soko la karibu watakusaidia. Ninaweza kukusaidia kuhusu mbegu, wakati wa "
                                       "kupanda, udongo, mzunguko wa mazao na matatizo ya mazao."]})
        r = self.ask(s, '255700003003', 'unajua bei ya mahindi?')[0]
        self.assertIn('bado sina taarifa za bei', r)

    def test_invented_facts_are_rejected_and_rules_answer_instead(self):
        bad = "Panda SC 403 utapata magunia 30 kwa ekari ukiweka DAP gramu 50 kwa shimo."
        s = Script({'mbegu gani': [bad, bad]})
        r = self.ask(s, '255700003004', 'mbegu gani ya mahindi nipande kondoa')[0]
        self.assertNotIn('magunia 30', r)
        self.assertIn('Mbegu', r)                                         # mfumo wa kanuni umejibu
        self.assertEqual(len(s.calls), 2)                                 # jaribio la pili lilipewa sababu

    def test_symptoms_hand_off_to_rule_based_diagnosis(self):
        s = Script({'mashimo': [{'tool': 'anza_uchunguzi', 'args': {'zao': 'mahindi', 'dalili': 'majani yana mashimo'}}]})
        r = self.ask(s, '255700003005', 'mahindi yangu majani yana mashimo makubwa')[0]
        self.assertTrue('Swali' in r or 'chagua namba' in r.lower() or 'dalili' in r.lower(), r)

    def test_disease_name_without_tool_is_rejected(self):
        from bot import agent
        self.assertIn('jina la tatizo', agent.check("Hii ni Fall Armyworm, nyunyizia mapema.", "mkulima: majani"))

    def test_agent_not_used_while_diagnosis_waits_for_answer(self):
        s = Script({'mashimo': [{'tool': 'anza_uchunguzi', 'args': {'zao': 'mahindi', 'dalili': 'mashimo'}}],
                    'ndiyo': ["SHOULD NOT BE USED"]})
        r = self.ask(s, '255700003006', 'mahindi yangu majani yana mashimo makubwa', 'ndiyo')
        self.assertNotIn('SHOULD NOT', r[1])

    def test_ai_unavailable_falls_back_to_rules(self):
        r = self.ask(lambda *a, **k: None, '255700003007', 'Ni mbegu gani ya mahindi nipande Kondoa?')[0]
        self.assertIn('Mbegu', r)


class BuiltByTests(TestCase):
    """Aliyejenga mfumo anatajwa TU akiulizwa; chapa ya KILIMONI LABS inabaki ya kwanza."""

    def ask(self, *msgs):
        from bot.engine import process_message
        return [process_message('255700004001', m) for m in msgs]

    def test_named_only_when_asked(self):
        r = self.ask('nani amekutengeneza?', 'wewe ni nani', 'mfumo huu umeundwa na nani')
        self.assertTrue(r[0].startswith('Kilimoni AI ni huduma ya *KILIMONI LABS*'))
        self.assertIn('JamiiTek Digital Agency', r[0])
        self.assertNotIn('JamiiTek', r[1])
        self.assertIn('JamiiTek Digital Agency', r[2])

    @override_settings(BUILT_BY='')
    def test_can_be_switched_off(self):
        self.assertNotIn('JamiiTek', self.ask('nani amekutengeneza?')[0])

    def test_agent_may_not_volunteer_it(self):
        from bot import agent
        self.assertIsNotNone(agent.check_creator("Mimi ni Kilimoni AI, nimejengwa na JamiiTek.", "wewe ni nani"))
        self.assertIsNone(agent.check_creator("Mfumo wangu umejengwa na JamiiTek Digital Agency.", "nani amekuunda"))


class WhatsAppFormatTests(TestCase):
    def test_markdown_bold_becomes_whatsapp_bold(self):
        from bot.messages import whatsapp_format
        self.assertEqual(whatsapp_format("**Kilimoni AI** ni huduma ya **KILIMONI LABS**."),
                         "*Kilimoni AI* ni huduma ya *KILIMONI LABS*.")
        self.assertEqual(whatsapp_format("### Hatua\n- moja"), "*Hatua*\n• moja")
        self.assertEqual(whatsapp_format("• *SC 403* — siku 75"), "• *SC 403* — siku 75")   # WhatsApp sahihi haiguswi

    def test_creator_question_with_typo(self):
        from bot.engine import process_message
        r = process_message('255700004101', 'Umetengenezwa nanani')
        self.assertIn('JamiiTek Digital Agency', r)
        self.assertNotIn('**', r)
