"""
python manage.py import_mhd007 <faili.xlsx au folder> [--dry-run]

Mfano:
    python manage.py import_mhd007 diagnosis/fixtures/mhd007 --dry-run
"""
import glob
import os

from django.core.management.base import BaseCommand, CommandError

from diagnosis.importer import import_mhd007


class Command(BaseCommand):
    help = 'Ingiza Excel za MHD-007 (A/C/E/F) kwenye Diagnostic Engine'

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', help='Faili za .xlsx au folder yenye faili hizo')
        parser.add_argument('--dry-run', action='store_true',
                            help='Endesha bila kuhifadhi (ripoti tu)')
        parser.add_argument('--if-empty', action='store_true',
                            help='Ruka kama tayari kuna data (kwa deploy — isifute data ya mteja)')

    def handle(self, paths, dry_run, if_empty=False, **opts):
        from diagnosis.models import Pest
        if if_empty and Pest.objects.exists():
            self.stdout.write('Data ya MHD-007 ipo tayari — import ya sample imerukwa.')
            return
        files = []
        for p in paths:
            if os.path.isdir(p):
                files += sorted(glob.glob(os.path.join(p, 'MHD-007*.xlsx')))
            elif os.path.isfile(p):
                files.append(p)
            else:
                raise CommandError(f"Haipo: {p}")
        if not files:
            raise CommandError('Hakuna faili la MHD-007 lililopatikana')

        report = import_mhd007(files, dry_run=dry_run)
        self.stdout.write(report.as_text())
        if report.rolled_back:
            raise CommandError('Import imerudishwa nyuma kwa sababu ya makosa')
