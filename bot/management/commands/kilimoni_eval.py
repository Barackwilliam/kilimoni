"""
Pima uelewa wa bot dhidi ya ujumbe halisi wa wakulima (bot/eval_bank.py).

    python manage.py kilimoni_eval            # AI ikipatikana (GROQ_API_KEY), vinginevyo kanuni
    python manage.py kilimoni_eval --rules    # kanuni za maneno tu
    python manage.py kilimoni_eval --compare  # kanuni dhidi ya AI, kesi kwa kesi

Inasoma tu (haiandiki database). Iendeshe kwenye Render Shell kupima AI halisi.
"""
from django.core.management.base import BaseCommand

from bot import understand
from bot.eval_bank import CASES, check


class Command(BaseCommand):
    help = 'Pima kuelewa kwa bot dhidi ya benki ya ujumbe halisi wa wakulima'

    def add_arguments(self, parser):
        parser.add_argument('--rules', action='store_true', help='kanuni za maneno tu (bila AI)')
        parser.add_argument('--compare', action='store_true', help='linganisha kanuni na AI')
        parser.add_argument('--only', default='', help='ID za kesi, mf. FAW2,DRY2')

    def _run(self, use_ai):
        results = []
        only = {x.strip() for x in self.only.split(',') if x.strip()}
        for case in CASES:
            if only and case['id'] not in only:
                continue
            turns = [('bot', case['bot'])] if case.get('bot') else []
            if use_ai:
                f = understand.ai_frame(case['msg'], case.get('pending', ''), turns) or None
                if f is None:
                    f = understand.rule_frame(case['msg'], case.get('pending', ''))
                    f['source'] = 'rules (AI haikujibu)'
            else:
                f = understand.rule_frame(case['msg'], case.get('pending', ''))
            results.append((case, f, check(case, f)))
        return results

    def _report(self, title, results):
        ok = sum(1 for _, _, e in results if not e)
        self.stdout.write(f"\n{'═' * 64}\n{title}\n{'═' * 64}")
        for case, f, errors in results:
            mark = self.style.SUCCESS('✓') if not errors else self.style.ERROR('✗')
            line = f"{mark} {case['id']:<7} {f['goal']:<12} [{f['source']}] {case['msg'][:60]}"
            self.stdout.write(line)
            for e in errors:
                self.stdout.write(f"          └ {e}")
        pct = round(100 * ok / len(results)) if results else 0
        self.stdout.write(f"\nMATOKEO: {ok}/{len(results)} ({pct}%)")
        return ok

    def handle(self, *args, **opts):
        from diagnosis import ai_layer
        self.only = opts['only']
        ai_ok = ai_layer.available()
        if opts['compare']:
            if not ai_ok:
                self.stdout.write(self.style.WARNING('AI haipatikani (GROQ_API_KEY) — siwezi kulinganisha.'))
                return
            r = self._report('KANUNI ZA MANENO', self._run(False))
            a = self._report('AI + UTHIBITISHO', self._run(True))
            self.stdout.write(f"\nKanuni: {r}/{len(CASES)}   AI: {a}/{len(CASES)}")
            return
        use_ai = ai_ok and not opts['rules']
        if not use_ai and not opts['rules']:
            self.stdout.write(self.style.WARNING('AI haipatikani — napima kanuni za maneno tu.'))
        self._report('AI + UTHIBITISHO' if use_ai else 'KANUNI ZA MANENO', self._run(use_ai))
