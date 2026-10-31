"""Hatua 6 — Kuunganisha: profile ya shamba (eneo, udongo, zao) + AI router."""
import glob
import os
from unittest.mock import patch

from django.test import TestCase, override_settings

from crops.models import Crop

from .importer import import_files

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


class ProfileBase(TestCase):
    def setUp(self):
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        Crop.objects.create(crop_name_sw='Mpunga', crop_name_en='Rice', crop_group='cereals')
        import_files(sorted(glob.glob(os.path.join(FIXTURES, '*.xlsx'))))

    def say(self, phone, *turns):
        from bot.engine import process_message
        return [process_message(phone, t) for t in turns]

    def user(self, phone):
        from bot.models import User
        return User.objects.get(phone_number=phone)


class ProfileMemoryTests(ProfileBase):
    def test_location_only_is_remembered_and_acknowledged(self):
        r = self.say('255701000001', 'niko changaa')
        self.assertIn('Nimekumbuka eneo la shamba lako', r[0])
        self.assertEqual(self.user('255701000001').aez_code, 'AEZ-003')

    def test_soil_remembered_and_used_by_other_modules(self):
        r = self.say('255701000002', 'udongo wangu ni mwekundu', 'niko changaa',
                     'mbegu gani ya mahindi nipande?', 'udongo wangu unafaa mahindi?',
                     'baada ya mahindi nipande nini?')
        self.assertEqual(self.user('255701000002').soil_code, 'SOL-WRB-001')
        self.assertIn('Udongo wako', r[2])                         # mbegu + ufaafu wa udongo
        self.assertIn('62/100', r[2])
        self.assertIn('Nimetumia udongo uliouniambia awali', r[3])
        self.assertIn('62/100', r[3])
        self.assertIn('mabaki shambani', r[4])                     # SOILROT-001 kwa udongo uliokumbukwa
        from bot.models import Conversation
        seed_trace = Conversation.objects.filter(trace__mode='seed_advisor').latest('created_at').trace
        self.assertIn('SCROP-00001', seed_trace['rules_used'])

    def test_new_soil_replaces_old(self):
        self.say('255701000003', 'udongo wangu ni mwekundu', 'hapana, udongo wangu ni wa kichanga')
        self.assertEqual(self.user('255701000003').soil_code, 'SOL-LOC-001')


@override_settings(GROQ_API_KEY='test-key')
class RouterTests(ProfileBase):
    def test_ai_routes_unusual_wording(self):
        def fake(system, user, max_tokens=900):
            if 'CHAGUO:' in user and 'rotation' in user:
                return {'code': 'rotation'} if 'msimu ujao' in user else {'code': 'other'}
            return None
        with patch('diagnosis.ai_layer._chat', fake):
            r = self.say('255701000004', 'mwaka jana nililima mahindi, msimu ujao niweke nini shambani')
        self.assertIn('Mahindi', r[0])
        from bot.models import Conversation
        t = Conversation.objects.filter(trace__mode='rotation_advisor').latest('created_at').trace
        self.assertEqual(t['previous'], 'mahindi')

    def test_router_other_falls_through(self):
        with patch('diagnosis.ai_layer._chat', return_value={'code': 'other'}):
            r = self.say('255701000005', 'habari za leo ndugu yangu mpendwa')
        from bot.models import Conversation
        self.assertFalse(Conversation.objects.filter(trace__mode__in=['rotation_advisor', 'seed_advisor']).exists())
