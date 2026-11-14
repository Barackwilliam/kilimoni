"""
Kipimo cha ubora kabla ya deploy: benki ya mazungumzo (bot/quality_bank.py) kupitia bot nzima.

    python manage.py kilimoni_quality              # benki nzima, ndani ya transaction (hairekodi kitu)
    python manage.py kilimoni_quality --show-misses
    python manage.py kilimoni_quality --only live-faw,live-dry

Kanuni (invariants) lazima ziwe 0 — amri inarudisha exit code 1 vinginevyo (inafaa CI/deploy).
Uelewa unaripotiwa kwa asilimia.
"""
import sys

from django.core.management.base import BaseCommand
from django.db import transaction

from bot import quality
from bot.quality_bank import all_conversations


class _Rollback(Exception):
    pass


class Command(BaseCommand):
    help = 'Pima ubora wa majibu ya bot kwenye benki ya mazungumzo (invariants + uelewa)'

    def add_arguments(self, parser):
        parser.add_argument('--only', default='', help='ID za mazungumzo, mf. live-faw,seed-3')
        parser.add_argument('--show-misses', action='store_true', help='onyesha matarajio yaliyokosekana')
        parser.add_argument('--no-ai', action='store_true', help='zima AI (kanuni za maneno tu)')

    def handle(self, *args, **opts):
        from unittest.mock import patch
        convs = all_conversations()
        only = {x.strip() for x in opts['only'].split(',') if x.strip()}
        if only:
            convs = [c for c in convs if c['id'] in only]
        ctx = patch('diagnosis.ai_layer._chat', return_value=None) if opts['no_ai'] else None
        if ctx:
            ctx.start()
        stats = None
        try:
            with transaction.atomic():
                stats = quality.run(convs)
                raise _Rollback()
        except _Rollback:
            pass
        finally:
            if ctx:
                ctx.stop()

        self.stdout.write(f"\nMazungumzo: {len(convs)}   Zamu (ujumbe): {stats['turns']}")
        v = stats['violations']
        if v:
            self.stdout.write(self.style.ERROR(f"\n✗ UKIUKAJI WA KANUNI: {len(v)}"))
            for cid, j, msg, errs, reply in v:
                self.stdout.write(f"  {cid} #{j + 1}: {msg[:60]!r}")
                for e in errs:
                    self.stdout.write(f"     └ {e}")
                self.stdout.write(f"     ⮑ {reply[:160]!r}")
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Kanuni zote zimetimizwa (0 ukiukaji)"))
        tot, ok = stats['expect_total'], stats['expect_ok']
        pct = round(100 * ok / tot) if tot else 0
        self.stdout.write(f"\nUelewa (matarajio): {ok}/{tot} ({pct}%)")
        if opts['show_misses']:
            for cid, j, msg, misses, reply in stats['misses']:
                self.stdout.write(f"  ✗ {cid} #{j + 1}: {msg[:60]!r} — {'; '.join(misses)}")
                self.stdout.write(f"     ⮑ {reply[:160]!r}")
        if v:
            sys.exit(1)
