"""
python manage.py import_advisory <faili.xlsx au folder> [--dry-run] [--if-empty]

Ingiza Excel za MHD-001 … MHD-006 (zile zenye importer). --if-empty
inaruka import kama tayari kuna data — inatumika na build.sh ili deploy
isifute marekebisho ambayo mteja amepakia kupitia dashboard.
"""
import glob
import os

from django.core.management.base import BaseCommand, CommandError

from advisory.importer import import_files, workbook_code
from advisory.models import CropCalendar, SeasonProfile, SoilType, VarietyRegistry, WardLocation

# --if-empty inaangaliwa kwa KILA workbook: data ya MHD-001 ikiwepo, sample
# ya MHD-003A bado inaingizwa kama mbegu hazipo (na kinyume chake).
HAS_DATA = {
    'MHD-001': lambda: WardLocation.objects.exists(),
    'MHD-003A': lambda: VarietyRegistry.objects.exists(),
    'MHD-004': lambda: SoilType.objects.exists(),
    'MHD-006': lambda: SeasonProfile.objects.exists() or CropCalendar.objects.exists(),
}


class Command(BaseCommand):
    help = 'Ingiza Excel za MHD-001…MHD-006 kwenye ushauri wa kanuni'

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--if-empty', action='store_true',
                            help='Ruka kama tayari kuna data (kwa deploy)')

    def handle(self, paths, dry_run, if_empty, **opts):
        files = []
        for p in paths:
            if os.path.isdir(p):
                files += sorted(glob.glob(os.path.join(p, 'MHD-00*.xlsx')))
            elif os.path.isfile(p):
                files.append(p)
            else:
                raise CommandError(f"Haipo: {p}")
        if if_empty:
            skipped = [f for f in files if HAS_DATA.get(workbook_code(f), lambda: False)()]
            for f in skipped:
                self.stdout.write(f"{workbook_code(f)}: data ipo tayari — sample imerukwa ({os.path.basename(f)})")
            files = [f for f in files if f not in skipped]
            if not files:
                return
        if not files:
            raise CommandError('Hakuna faili la MHD-001…006')
        report = import_files(files, dry_run=dry_run)
        self.stdout.write(report.as_text())
        if report.rolled_back:
            raise CommandError('Import imerudishwa nyuma kwa sababu ya makosa')
