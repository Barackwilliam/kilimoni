"""
Pima uelewa wa bot dhidi ya ujumbe halisi wa wakulima (bot/eval_bank.py).

    python manage.py kilimoni_eval            # AI ikipatikana (GROQ_API_KEY), vinginevyo kanuni
    python manage.py kilimoni_eval --rules    # kanuni za maneno tu
    python manage.py kilimoni_eval --compare  # kanuni dhidi ya AI, kesi kwa kesi
    python manage.py kilimoni_eval --delay 4  # sekunde kati ya maombi ya AI (vikomo vya maombi)

Inasoma tu (haiandiki database). Kesi ambazo AI haikujibu (mf. kikomo cha maombi, 429)
hazihesabiwi kama matokeo ya AI — zinaonyeshwa kando ili namba zisidanganye.
"""
import time

from django.core.management.base import BaseCommand

from bot import understand
from bot.eval_bank import CASES, check


class Command(BaseCommand):
    help = 'Pima kuelewa kwa bot dhidi ya benki ya ujumbe halisi wa wakulima'

    def add_arguments(self, parser):
        parser.add_argument('--rules', action='store_true', help='kanuni za maneno tu (bila AI)')
        parser.add_argument('--compare', action='store_true', help='linganisha kanuni na AI')
        parser.add_argument('--only', default='', help='ID za kesi, mf. FAW2,DRY2')
        parser.add_argument('--delay', type=float, default=3.0,
                            help='sekunde kati ya maombi ya AI (default 3)')

    def _ai(self, case, turns):
        from diagnosis import ai_layer
        for attempt in range(3):
            if ai_layer.rate_limited(self.primary):
                wait = max(1.0, ai_layer.cooldown_left(self.primary))
                self.stdout.write(f"   … kikomo cha maombi — nasubiri sekunde {wait:.0f}")
                time.sleep(wait + 1)
            f = understand.ai_frame(case['msg'], case.get('pending', ''), turns)
            if f is not None:
                return f
            if not ai_layer.rate_limited(self.primary):
                return None                       # AI ilijibu vibaya (si kikomo) — hesabu kama imeshindwa
        return None

    def _run(self, use_ai):
        results = []
        only = {x.strip() for x in self.only.split(',') if x.strip()}
        for case in CASES:
            if only and case['id'] not in only:
                continue
            turns = [('bot', case['bot'])] if case.get('bot') else []
            if use_ai:
                f = self._ai(case, turns)
                if f is None:
                    f = understand.rule_frame(case['msg'], case.get('pending', ''))
                    f['source'] = 'AI haikujibu'
                time.sleep(self.delay)
            else:
                f = understand.rule_frame(case['msg'], case.get('pending', ''))
            results.append((case, f, check(case, f)))
        return results

    def _report(self, title, results):
        self.stdout.write(f"\n{'═' * 64}\n{title}\n{'═' * 64}")
        for case, f, errors in results:
            mark = self.style.SUCCESS('✓') if not errors else self.style.ERROR('✗')
            if f['source'] == 'AI haikujibu':
                mark = self.style.WARNING('?')
            self.stdout.write(f"{mark} {case['id']:<7} {f['goal']:<12} [{f['source']}] {case['msg'][:60]}")
            for e in errors:
                self.stdout.write(f"          └ {e}")
        scored = [r for r in results if r[1]['source'] != 'AI haikujibu']
        missed = len(results) - len(scored)
        ok = sum(1 for _, _, e in scored if not e)
        pct = round(100 * ok / len(scored)) if scored else 0
        self.stdout.write(f"\nMATOKEO: {ok}/{len(scored)} ({pct}%)"
                          + (f"  — kesi {missed} AI haikujibu (hazijahesabiwa)" if missed else ''))
        return ok, len(scored)

    def handle(self, *args, **opts):
        from diagnosis import ai_layer
        from django.conf import settings
        self.only, self.delay = opts['only'], opts['delay']
        self.primary = getattr(settings, 'GROQ_UNDERSTAND_MODEL', '') or None
        self.stdout.write(f"Model (kwa mpangilio): {', '.join(ai_layer.model_chain(self.primary))}")
        ai_ok = ai_layer.available()
        if opts['compare']:
            if not ai_ok:
                self.stdout.write(self.style.WARNING('AI haipatikani (GROQ_API_KEY) — siwezi kulinganisha.'))
                return
            r, rn = self._report('KANUNI ZA MANENO', self._run(False))
            self.stdout.write(f"\nAI: maombi {len(CASES)}, sekunde {self.delay} kati ya kila moja "
                              f"(takriban dakika {round(len(CASES) * (self.delay + 2) / 60)})…")
            a, an = self._report('AI + UTHIBITISHO', self._run(True))
            self.stdout.write(f"\nKanuni: {r}/{rn}   AI: {a}/{an}")
            return
        use_ai = ai_ok and not opts['rules']
        if not use_ai and not opts['rules']:
            self.stdout.write(self.style.WARNING('AI haipatikani — napima kanuni za maneno tu.'))
        self._report('AI + UTHIBITISHO' if use_ai else 'KANUNI ZA MANENO', self._run(use_ai))
