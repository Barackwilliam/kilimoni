"""
Jaribu bot kutoka terminal (bila WhatsApp), ukiona zana za dataset ambazo AI ilitumia.

    python manage.py kilimoni_ask "Taarifa unatoa wapi wewe" "nataka mbegu ya mahindi" "niko kikore"

Ujumbe unapita bot nzima kama mazungumzo moja; kila kitu kinarudishwa nyuma (hakuna kinachohifadhiwa).
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class _Rollback(Exception):
    pass


class Command(BaseCommand):
    help = 'Uliza bot maswali (mazungumzo moja) na uone zana za dataset zilizotumika'

    def add_arguments(self, parser):
        parser.add_argument('messages', nargs='+')
        parser.add_argument('--phone', default='255799999999')

    def handle(self, *args, **opts):
        from bot.engine import process_message
        from bot.models import Conversation, User
        try:
            with transaction.atomic():
                User.objects.filter(phone_number=opts['phone']).delete()
                for msg in opts['messages']:
                    reply = process_message(opts['phone'], msg)
                    user = User.objects.get(phone_number=opts['phone'])
                    last = Conversation.objects.filter(user=user, message_direction='outbound').latest('id')
                    t = last.trace or {}
                    self.stdout.write(f"\n👨‍🌾 {msg}")
                    tools = ', '.join(f"{x['name']}({', '.join(f'{k}={v}' for k, v in x.get('args', {}).items())})"
                                      for x in t.get('tools', []))
                    self.stdout.write(f"   [{t.get('mode', '?')}{' · ' + tools if tools else ''}"
                                      f"{' · writer=' + t['writer'] if t.get('writer') else ''}"
                                      f"{' · imekataliwa: ' + t['rejected'][-1]['why'] if t.get('rejected') else ''}]")
                    self.stdout.write(f"🤖 {reply}")
                raise _Rollback()
        except _Rollback:
            pass
