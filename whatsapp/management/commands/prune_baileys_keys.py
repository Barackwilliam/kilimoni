"""
python manage.py prune_baileys_keys [--days 30]

`app-state-sync-key` za Baileys zinaongezeka zenyewe kwenye jedwali la
baileys_auth na hazifutwi. Amri hii inaiomba bridge izifute zilizopita
siku N. Creds na funguo zinazotumika haziguswi.
"""
from django.core.management.base import BaseCommand, CommandError

from whatsapp import bridge


class Command(BaseCommand):
    help = 'Futa app-state-sync-key za zamani za session ya WhatsApp (kupitia bridge)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)

    def handle(self, days, **opts):
        res = bridge.prune(days)
        if not res.get('success'):
            raise CommandError(f"Imeshindwa: {res.get('error')}")
        self.stdout.write(f"Funguo {res.get('removed', 0)} zimefutwa (zaidi ya siku {days}).")
