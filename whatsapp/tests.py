"""Majaribio ya bridge mpya (nakala ya JamiiTek): webhook isiyosubiri, kutuma, na ukurasa wa WhatsApp."""
import json
from unittest import mock

from django.contrib.auth.models import User as AuthUser
from django.test import TestCase, override_settings
from django.urls import reverse

from . import bridge

KEY = 'siri-ya-majaribio'
BRIDGE = dict(BRIDGE_URL='http://bridge.test', BRIDGE_API_KEY=KEY, BAILEYS_SESSION='kilimoni', BRIDGE_INLINE=True)


def _post(client, payload, key=KEY):
    return client.post(reverse('bridge_incoming'), data=json.dumps(payload), content_type='application/json',
                       HTTP_X_BRIDGE_KEY=key)


@override_settings(**BRIDGE)
class BridgeWebhookTests(TestCase):
    def setUp(self):
        self.sent = []
        p = mock.patch.object(bridge, 'send_text', side_effect=lambda to, text, jid='': self.sent.append((to, text, jid)) or {'success': True})
        p.start()
        self.addCleanup(p.stop)

    def test_rejects_wrong_key(self):
        self.assertEqual(_post(self.client, {'phone': '255712000001', 'text': 'habari'}, key='mbaya').status_code, 401)
        self.assertEqual(self.sent, [])

    def test_text_goes_through_engine_and_reply_is_sent_to_jid(self):
        with mock.patch('whatsapp.views.process_message', return_value='Jibu la kanuni') as pm:
            r = _post(self.client, {'session': 'kilimoni', 'jid': '158351803576497@lid', 'phone': '158351803576497',
                                    'text': 'mahindi yangu yana matundu', 'message_id': 'M1', 'msg_type': 'text'})
        self.assertEqual(r.json(), {'success': True})
        pm.assert_called_once_with('158351803576497', 'mahindi yangu yana matundu', whatsapp_type='text', message_id='M1')
        self.assertEqual(self.sent, [('158351803576497', 'Jibu la kanuni', '158351803576497@lid')])

    def test_photo_without_caption_gets_polite_reply(self):
        with mock.patch('whatsapp.views.process_message') as pm:
            _post(self.client, {'phone': '255712000002', 'jid': '255712000002@s.whatsapp.net', 'text': '',
                                'message_id': 'M2', 'msg_type': 'image'})
        pm.assert_not_called()
        self.assertIn('siwezi kusoma picha', self.sent[0][1])

    def test_voice_note_asks_to_type(self):
        _post(self.client, {'phone': '255712000003', 'text': '', 'message_id': 'M3', 'msg_type': 'audio'})
        self.assertIn('andika swali lako', self.sent[0][1])

    def test_photo_with_caption_is_treated_as_text(self):
        with mock.patch('whatsapp.views.process_message', return_value='ok') as pm:
            _post(self.client, {'phone': '255712000004', 'text': 'majani yana madoa', 'message_id': 'M4', 'msg_type': 'image'})
        self.assertEqual(pm.call_args.args[1], 'majani yana madoa')

    def test_duplicate_is_ignored(self):
        with mock.patch('whatsapp.views.process_message', return_value='ok') as pm:
            payload = {'phone': '255712000005', 'text': 'habari', 'message_id': 'DUP1'}
            _post(self.client, payload)
            r = _post(self.client, payload)
        self.assertEqual(pm.call_count, 1)
        self.assertEqual(r.json().get('skipped'), 'duplicate')

    def test_unknown_session_rejected(self):
        r = _post(self.client, {'session': 'jamiitek-bot', 'phone': '255712000006', 'text': 'x'})
        self.assertEqual(r.status_code, 404)

    def test_engine_end_to_end(self):
        """Bila mock ya injini: ujumbe halisi unapata jibu na kuandikwa kwenye mazungumzo."""
        from bot.models import Conversation
        _post(self.client, {'phone': '255712000007', 'jid': '255712000007@s.whatsapp.net', 'text': 'habari',
                            'message_id': 'E2E1'})
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.sent[0][1])
        self.assertTrue(Conversation.objects.filter(whatsapp_message_id='E2E1').exists())

    def test_sessions_endpoint(self):
        r = self.client.get(reverse('bridge_sessions'), HTTP_X_BRIDGE_KEY=KEY)
        self.assertEqual(r.json(), {'success': True, 'sessions': ['kilimoni']})
        self.assertEqual(self.client.get(reverse('bridge_sessions')).status_code, 401)


@override_settings(**BRIDGE)
class BridgeClientTests(TestCase):
    def test_send_prefers_jid_and_uses_key(self):
        with mock.patch('whatsapp.bridge.requests.request') as req:
            req.return_value.status_code = 200
            req.return_value.json.return_value = {'success': True, 'message_id': 'X'}
            res = bridge.send_text('255712', 'habari', jid='999@lid')
        self.assertTrue(res['success'])
        args, kwargs = req.call_args
        self.assertEqual(args, ('POST', 'http://bridge.test/send'))
        self.assertEqual(kwargs['json'], {'session': 'kilimoni', 'to': '255712', 'text': 'habari', 'jid': '999@lid'})
        self.assertEqual(kwargs['headers']['X-Bridge-Key'], KEY)

    def test_unreachable_bridge_never_raises(self):
        import requests
        with mock.patch('whatsapp.bridge.requests.request', side_effect=requests.ConnectionError()):
            res = bridge.status()
        self.assertFalse(res['success'])
        self.assertIn('haifikiki', res['error'])

    @override_settings(BRIDGE_URL='', BRIDGE_API_KEY='')
    def test_not_configured(self):
        self.assertFalse(bridge.send_text('1', 'x')['success'])


@override_settings(**BRIDGE)
class WhatsAppDashboardTests(TestCase):
    def setUp(self):
        AuthUser.objects.create_user('kilimoni', password='x', is_staff=True)   # mteja, si superuser
        self.client.login(username='kilimoni', password='x')

    def test_connected_page(self):
        st = {'success': True, 'status': 'connected', 'number': '255700111222', 'connected_at': '2026-11-04T01:00:00.000Z'}
        with mock.patch.object(bridge, 'status', return_value=st), \
                mock.patch.object(bridge, 'debug', return_value={'success': True, 'verdict': 'HAI — WhatsApp inaongea nasi'}):
            r = self.client.get(reverse('wa_home'))
        self.assertContains(r, 'Imeunganishwa')
        self.assertContains(r, '255700111222')
        self.assertContains(r, 'HAI')
        self.assertNotContains(r, "fetch(")                      # hakuna QR ya kusasisha

    def test_waiting_qr_page_polls(self):
        with mock.patch.object(bridge, 'status', return_value={'success': True, 'status': 'waiting_qr'}), \
                mock.patch.object(bridge, 'debug', return_value={}):
            r = self.client.get(reverse('wa_home'))
        self.assertContains(r, 'Inasubiri QR')
        self.assertContains(r, 'fetch(')
        with mock.patch.object(bridge, 'qr', return_value={'success': True, 'status': 'waiting_qr', 'qr': 'data:image/png;base64,AAA'}):
            self.assertEqual(self.client.get(reverse('wa_qr')).json()['qr'], 'data:image/png;base64,AAA')

    def test_unreachable_bridge_page(self):
        with mock.patch.object(bridge, 'status', return_value={'success': False, 'error': 'bridge haifikiki: ConnectionError'}):
            r = self.client.get(reverse('wa_home'))
        self.assertContains(r, 'Bridge haifikiki')

    def test_logout_needs_confirmation(self):
        with mock.patch.object(bridge, 'logout', return_value={'success': True}) as lo:
            self.client.post(reverse('wa_action'), {'action': 'logout'})
            lo.assert_not_called()
            self.client.post(reverse('wa_action'), {'action': 'logout', 'confirm': 'TOA'})
            lo.assert_called_once()

    def test_ping_normalizes_local_number(self):
        with mock.patch.object(bridge, 'ping', return_value={'success': True}) as p:
            self.client.post(reverse('wa_action'), {'action': 'ping', 'to': '0712 345 678'})
        p.assert_called_once_with('255712345678')

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('wa_home')).status_code, 302)


class QueueTests(TestCase):
    """Foleni ya kudumu: mpangilio kwa kila mkulima, marudio, kosa halizuii jumbe zinazofuata."""

    def setUp(self):
        self.sent = []
        p = mock.patch.object(bridge, 'send_text', side_effect=lambda to, text, jid='': self.sent.append((to, text)) or {'success': True})
        p.start()
        self.addCleanup(p.stop)

    def test_rows_processed_in_arrival_order(self):
        from . import views
        from .models import IncomingMessage
        for n in range(5):
            IncomingMessage.objects.create(phone='A', message_id=f'q{n}', payload={'phone': 'A', 'text': f'ujumbe {n}', 'message_id': f'q{n}'})
        with mock.patch('whatsapp.views.process_message', side_effect=lambda p, t, **k: f'jibu {t}'):
            views.process_phone('A')
        self.assertEqual([t for _, t in self.sent], [f'jibu ujumbe {n}' for n in range(5)])
        self.assertEqual(set(IncomingMessage.objects.values_list('status', flat=True)), {'done'})

    def test_failure_is_recorded_and_next_message_still_answered(self):
        from . import views
        from .models import IncomingMessage
        IncomingMessage.objects.create(phone='B', message_id='f1', payload={'phone': 'B', 'text': 'mbaya', 'message_id': 'f1'})
        IncomingMessage.objects.create(phone='B', message_id='f2', payload={'phone': 'B', 'text': 'nzuri', 'message_id': 'f2'})

        def engine(p, t, **k):
            if t == 'mbaya':
                raise RuntimeError('injini')
            return 'sawa'
        with mock.patch('whatsapp.views.process_message', side_effect=engine):
            views.process_phone('B')
        self.assertEqual(IncomingMessage.objects.get(message_id='f1').status, 'failed')
        self.assertIn('RuntimeError', IncomingMessage.objects.get(message_id='f1').error)
        self.assertEqual(self.sent, [('B', 'sawa')])

    @override_settings(**BRIDGE)
    def test_duplicate_rejected_by_queue(self):
        from .models import IncomingMessage
        with mock.patch('whatsapp.views.process_message', return_value='ok'):
            for _ in range(3):
                r = _post(self.client, {'phone': 'C', 'text': 'habari', 'message_id': 'same'})
        self.assertEqual(IncomingMessage.objects.filter(message_id='same').count(), 1)
        self.assertEqual(r.json().get('skipped'), 'duplicate')
        self.assertEqual(len(self.sent), 1)


@override_settings(**BRIDGE)
class CrashRecoveryTests(TestCase):
    def test_processed_but_unsent_reply_is_resent_not_recomputed(self):
        """Worker alikufa baada ya injini kuhifadhi jibu lakini kabla ya kutuma."""
        from bot.engine import process_message
        from . import views
        from .models import IncomingMessage
        reply = process_message('255700000201', 'habari', message_id='crash-1')     # injini ilimaliza
        IncomingMessage.objects.create(phone='255700000201', message_id='crash-1',
                                       payload={'phone': '255700000201', 'text': 'habari', 'message_id': 'crash-1'})
        sent = []
        with mock.patch.object(bridge, 'send_text', side_effect=lambda to, text, jid='': sent.append(text) or {'success': True}), \
                mock.patch('whatsapp.views.process_message') as pm:
            views.process_phone('255700000201')
        pm.assert_not_called()
        self.assertEqual(sent, [reply])
        self.assertEqual(IncomingMessage.objects.get(message_id='crash-1').status, 'done')


class HealthzTests(TestCase):
    """/healthz/ — UptimeRobot/Render: wazi (bila login), haitoi siri, inaokota foleni."""

    @override_settings(**BRIDGE)
    def test_reports_bridge(self):
        with mock.patch.object(bridge, 'health', return_value={'success': True}):
            r = self.client.get('/healthz/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'ok': True, 'bridge': True})

    @override_settings(BRIDGE_URL='', BRIDGE_API_KEY='')
    def test_without_bridge(self):
        self.assertEqual(self.client.get('/healthz/').json(), {'ok': True, 'bridge': None})
