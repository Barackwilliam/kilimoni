from django.test import TestCase


class ProblemDetectionTests(TestCase):
    """Maneno ya kawaida (Kondoa, inafaa, kutumia, umwagiliaji) yasionekane kama tatizo la zao."""
    PROBLEM = ["majani yana madoa", "mahindi yananyauka", "mahindi yanakufa", "mmea umekufa", "wadudu wanakula majani",
     "majani yameliwa", "kuna funza kwenye mahindi", "majani yanageuka njano", "mahindi yanaoza", "mizizi imeoza",
     "mimea imedumaa", "kuna kutu kwenye majani", "majani yana ukungu", "majani yamejikunja", "yana mabaka ya kahawia",
     "mahindi yangu yanaumwa", "majani yamekauka", "majani yameungua", "kuna mashimo kwenye majani",
     "majani yametobolewa", "kuna kinyesi kama vumbi", "majani yana michirizi", "mimea haistawi",
     "matunda yanapukutika", "mahindi yana ugonjwa", "kuna wadudu", "mahindi yana tatizo", "nina shida na mahindi",
     "kiwavi anakula mahindi", "viwavi wameharibu shamba", "majani yana doa jeupe", "mahindi hayakui", "mimea dhaifu",
     "majani yana manjano", "kuna uchafu mweusi kwenye majani", "mahindi yanakufa kwa ukame", "shina limeoza"]
    NOT_PROBLEM = ["niko kondoa", "nipo kondoa dodoma", "je sc403 itakufaa", "mbegu ipi inafaa", "nifanye nini kufanya udongo bora",
     "sina umwagiliaji", "nataka kumwagilia mahindi", "nitumie mbolea gani", "kutumia mbolea ya dap", "nataka kutuma ujumbe",
     "nipande lini mahindi", "bei ya mahindi sokoni", "nivune lini", "mvua imeanza", "kwa ajili ya mavuno mengi",
     "nipo kongwa", "shamba la heka mbili", "namna ya kuhifadhi mahindi", "nimepanda jana", "kutunza mahindi baada ya kuvuna",
     "habari za asubuhi", "asante sana", "nataka mbegu ya muda mfupi", "udongo wangu ni wa kichanga",
     "nipande nini baada ya mahindi", "mbolea ya kukuzia", "nataka kujua zaidi", "nitapanda wiki ijayo"]

    def test_real_problems_are_detected(self):
        from bot.diagnostic import is_problem_message
        self.assertEqual([t for t in self.PROBLEM if not is_problem_message(t)], [])

    def test_ordinary_words_are_not_problems(self):
        from bot.diagnostic import is_problem_message
        self.assertEqual([t for t in self.NOT_PROBLEM if is_problem_message(t)], [])


class PlaceWithoutDataTests(TestCase):
    """Eneo linalojulikana kwa jina lakini halimo kwenye MHD-001: sema ukweli, usiulize tena na tena."""

    @classmethod
    def setUpTestData(cls):
        import glob
        import os
        from advisory.importer import import_files
        from crops.models import Crop
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        fx = os.path.join(os.path.dirname(__file__), '..', 'advisory', 'fixtures')
        import_files(sorted(glob.glob(os.path.join(fx, '*.xlsx'))))

    def ask(self, phone, *msgs):
        from bot.engine import process_message
        return [process_message(phone, m) for m in msgs]

    def test_seed_place_without_data_then_nearby_ward(self):
        r = self.ask('255700000101', 'niko kongwa nataka mbegu ya mahindi', 'niko kondoa')
        self.assertIn('Kongwa', r[0])
        self.assertIn('sina taarifa za kanda', r[0])
        self.assertIn('Mbegu za Mahindi', r[1])                 # inaendelea na eneo jirani

    def test_place_is_remembered_not_asked_again(self):
        r = self.ask('255700000102', 'niko kongwa nataka mbegu ya mahindi', 'asante', 'je sc403 inafaa?')
        self.assertIn('sina taarifa za kanda', r[2])
        self.assertNotIn('Tafadhali taja mkoa', r[2])

    def test_planting_place_without_data(self):
        r = self.ask('255700000103', 'nipande lini mahindi niko kongwa', 'kata ya changaa')
        self.assertIn('kukuambia wakati wa kupanda', r[0])
        self.assertIn('Wakati wa kupanda Mahindi', r[1])

    def test_location_only_message_is_not_a_problem(self):
        r = self.ask('255700000104', 'niko kondoa')
        self.assertNotIn('Pole kwa tatizo', r[0])


class CoverageTests(TestCase):
    """'Uko na taarifa za mikoa gani?' na mifano ya bot vinatoka kwenye data, si maneno ya kudumu."""

    @classmethod
    def setUpTestData(cls):
        import glob
        import os
        from advisory.importer import import_files
        from crops.models import Crop
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        fx = os.path.join(os.path.dirname(__file__), '..', 'advisory', 'fixtures')
        import_files(sorted(glob.glob(os.path.join(fx, '*.xlsx'))))

    def test_detector(self):
        from advisory.coverage import wants_coverage
        for t in ('Uko na taarifa za mikoa gani', 'unajua mazao gani', 'mnahudumia wilaya zipi'):
            self.assertTrue(wants_coverage(t), t)
        for t in ('mazao gani nipande baada ya mahindi', 'mbegu gani ya mahindi nipande singida',
                  'wilaya gani nzuri kwa mahindi'):
            self.assertFalse(wants_coverage(t), t)

    def test_coverage_answer_from_data(self):
        from bot.engine import process_message
        r = process_message('255700000501', 'Uko na taarifa za mikoa gani')
        self.assertIn('Dodoma (Kondoa)', r)
        self.assertIn('*Mahindi* — mbegu, wakati wa kupanda, udongo', r)
        self.assertNotIn('wadudu na magonjwa', r)      # MHD-007 haikuingizwa → haidai
        self.assertNotIn('nje ya uwezo wangu', r)

    def test_examples_use_a_place_with_data(self):
        from bot.messages import build_greeting, build_help_message
        self.assertIn('nipande Kondoa?', build_greeting(is_returning=False))
        self.assertNotIn('Singida', build_help_message())

    def test_no_data_place_lists_known_places(self):
        from bot.engine import process_message
        r = process_message('255700000502', 'Mbegu gani ya mahindi nipande singida')
        self.assertIn('Kwa sasa nina taarifa za maeneo haya: Dodoma (Kondoa)', r)
