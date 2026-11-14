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
        self.assertNotIn('natamani nielewe vizuri', r)

    def test_examples_use_a_place_with_data(self):
        from bot.messages import build_greeting, build_help_message
        self.assertIn('nipande Kondoa?', build_greeting(is_returning=False))
        self.assertNotIn('Singida', build_help_message())

    def test_no_data_place_lists_known_places(self):
        from bot.engine import process_message
        r = process_message('255700000502', 'Mbegu gani ya mahindi nipande singida')
        self.assertIn('Kwa sasa nina taarifa za maeneo haya: Dodoma (Kondoa)', r)


class LiveFeedbackTests(TestCase):
    """Matatizo yaliyoonekana kwa wakulima halisi kwenye WhatsApp (13 Nov 2026)."""

    @classmethod
    def setUpTestData(cls):
        import glob
        import os
        from crops.models import Crop
        from diagnosis.importer import import_mhd007
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        fx = os.path.join(os.path.dirname(__file__), '..', 'diagnosis', 'fixtures', 'mhd007')
        import_mhd007(sorted(glob.glob(os.path.join(fx, '*.xlsx'))))

    def ask(self, phone, *msgs):
        from bot.engine import process_message
        return [process_message(phone, m) for m in msgs]

    def test_typo_answer_is_understood(self):
        from diagnosis.engine import parse_answer
        self.assertEqual(parse_answer('Hqpana'), 'no')
        self.assertEqual(parse_answer('ndoyo'), 'yes')
        self.assertEqual(parse_answer('sijuo'), 'unknown')
        self.assertEqual(parse_answer('panda'), 'unknown')       # si kila neno fupi ni jibu

    def test_photo_request_never_reaches_farmer(self):
        from diagnosis import plain
        out, dropped = plain.clean('Sina uhakika wa kutosha. Tafadhali tuma picha au jibu maswali ya ziada.')
        self.assertNotIn('picha', out)
        self.assertIn('jibu maswali ya ziada', out)
        out, dropped = plain.clean('Tuma picha ya jani lililoathirika.')
        self.assertEqual(out, '')
        self.assertEqual(dropped[0][1], 'unsupported')

    def test_new_question_mid_diagnosis_leaves_diagnosis(self):
        r = self.ask('255700000601', 'mahindi majani yana mistari ya njano', 'Jinsi ya kupanda mahindi chunya')
        self.assertIn('Swali 1', r[0])
        self.assertNotIn('Samahani kama swali halikuwa wazi', r[1])
        self.assertNotIn('Swali 2', r[1])

    def test_complaint_with_question_apologises_and_answers(self):
        from bot.models import Conversation
        r = self.ask('255700000602', 'mahindi majani yana mistari ya njano', 'Nimeuliza hatua za kupanda mahindi')
        self.assertTrue(r[1].startswith('Samahani, nadhani nilikuelewa vibaya'))
        self.assertNotIn('Hakuna shida', r[1])
        self.assertNotIn('Swali 2', r[1])
        last = Conversation.objects.filter(message_direction='outbound').order_by('-id').first()
        self.assertEqual(last.raw_message, r[1])                 # dashboard inaona jibu kamili

    def test_complaint_alone_is_not_off_topic(self):
        r = self.ask('255700000603', 'Mbona sijauliza swali hilo?')
        self.assertIn('nilikuelewa vibaya', r[0])
        self.assertNotIn('silijui', r[0])

    def test_symptoms_before_crop_are_not_asked_again(self):
        r = self.ask('255700000604', 'Majani yamekuwa ya rangi ya kahawia', 'Mahindi')
        self.assertIn('zao gani', r[0])
        self.assertNotIn('nieleze *dalili unazoziona*', r[1])

    def test_answers_still_work_mid_diagnosis(self):
        r = self.ask('255700000605', 'mahindi majani yana mistari ya njano', 'Hqpana')
        self.assertIn('Swali 2', r[1])


class ExtensionOfficerFlowTests(TestCase):
    """Maoni ya mteja (14 Nov): taarifa zisipotosha, uliza kama afisa ugani; usishauri kuharibu mimea."""

    @classmethod
    def setUpTestData(cls):
        import glob
        import os
        from crops.models import Crop
        from diagnosis.importer import import_mhd007
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        fx = os.path.join(os.path.dirname(__file__), '..', 'diagnosis', 'fixtures', 'mhd007')
        import_mhd007(sorted(glob.glob(os.path.join(fx, '*.xlsx'))))

    def ask(self, phone, *msgs):
        from bot.engine import process_message
        return [process_message(phone, m) for m in msgs]

    TITO = ("Habari Kilimoni. Nina shamba la mahindi, lakini siku hizi mimea yangu haionekani vizuri. "
            "Naomba unisaidie nifanye nini?")

    def test_vague_problem_asks_diagnostic_questions(self):
        r = self.ask('255700000701', self.TITO)[0]
        self.assertIn('kabla ya kukushauri chochote', r)
        self.assertIn('2️⃣ Majani yana mashimo', r)
        self.assertIn('umri', r)
        self.assertNotIn('hazilingani', r)                    # si hitimisho
        self.assertNotIn('ichome', r)

    def test_numbered_answer_with_age_continues_diagnosis(self):
        r = self.ask('255700000702', self.TITO, '2, wiki 6')
        self.assertNotIn('Funza jeshi', r[1])                    # hakuna kisababishi kabla ya maswali
        self.assertIn('Kabla sijakupa jibu lolote', r[1])
        self.assertIn('Swali 1', r[1])

    def test_age_and_choice_parsing(self):
        from diagnosis.engine import parse_intake
        self.assertEqual(parse_intake('2 wiki 6'), ([1], 6))
        self.assertEqual(parse_intake('1 na 3'), ([0, 2], None))
        self.assertEqual(parse_intake('5 6 miezi 2'), ([4, 5], 8))

    def test_insufficient_info_is_not_reported_as_no_knowledge(self):
        r = self.ask('255700000703', 'mahindi hayako sawa', 'sijui', 'sijui kabisa')
        self.assertIn('Bado sijaelewa tatizo vizuri', r[1])
        self.assertIn('Bila kujua dalili', r[2])
        self.assertNotIn('hazilingani', r[2])

    def test_safe_steps_never_destroy_plants(self):
        from diagnosis.engine import SAFE_FIRST_STEPS
        for word in ('ichome', 'izike', 'ng\'oa', 'ondoa mimea'):
            self.assertNotIn(word, SAFE_FIRST_STEPS.lower())

    def test_crop_from_previous_message_is_remembered(self):
        r = self.ask('255700000704', 'nipande lini mahindi', 'majani yana mashimo makubwa')
        self.assertNotIn('zao gani', r[1])
        self.assertIn('Swali 1', r[1])

    def test_weeding_is_a_knowledge_gap_not_misunderstanding(self):
        from bot.models import UnresolvedQuery
        r = self.ask('255700000705', 'Sawa alafu jinsi ya kupalilia pia haielewi')[0]
        self.assertIn('kupalilia', r)
        self.assertIn('sina taarifa za kitaalamu', r)
        self.assertNotIn('natamani nielewe', r)
        self.assertTrue(UnresolvedQuery.objects.exists())       # pengo linaonekana kwenye dashboard

    def test_described_symptoms_without_match_list_known_problems(self):
        r = self.ask('255700000706', 'mahindi yangu mizizi imeoza kabisa')[0]
        self.assertIn('Nimeelewa dalili ulizotaja', r)
        self.assertIn('ninayoweza kuchunguza kwa sasa', r)


class ClientTestRound2(TestCase):
    """Tests 1–3 za mteja (14 Nov, mazungumzo moja): kuuliza, kujirekebisha, mipaka ya data."""

    @classmethod
    def setUpTestData(cls):
        import glob
        import os
        from crops.models import Crop
        from diagnosis.importer import import_mhd007
        Crop.objects.create(crop_name_sw='Mahindi', crop_name_en='Maize', crop_group='cereals')
        fx = os.path.join(os.path.dirname(__file__), '..', 'diagnosis', 'fixtures', 'mhd007')
        import_mhd007(sorted(glob.glob(os.path.join(fx, '*.xlsx'))))

    T1 = ("Habari Kilimoni. Nina shamba la mahindi, lakini siku hizi mimea yangu haionekani vizuri. "
          "Naomba unisaidie nifanye nini?")
    T2 = ("Lakini Kilimoni, mimi sijakuambia bado dalili za mahindi yangu. Kwa nini umenishauri niondoe na "
          "kuchoma mimea? Si ungeanza kwa kuniuliza maswali ili ujue tatizo ni nini?")
    T3 = ("Kilimoni, nina shamba la mahindi la ekari mbili huko Kongwa, Dodoma. Nilipanda wiki tatu zilizopita, "
          "lakini sasa majani ya chini yanaanza kuwa ya njano, wakati majani ya juu bado ni ya kijani. "
          "Hii inaweza kuwa ni tatizo gani, na nifanye nini?")

    def ask(self, phone, *msgs):
        from bot.engine import process_message
        return [process_message(phone, m) for m in msgs]

    def test_challenge_to_advice_is_acknowledged_and_restarts_with_questions(self):
        r = self.ask('255700000801', self.T1, self.T2)
        self.assertNotEqual(r[0], r[1])                          # si jibu lilelile
        self.assertIn('Uko sahihi, samahani', r[1])
        self.assertIn('usiufuate', r[1])
        self.assertIn('Chagua namba', r[1])
        self.assertNotIn('ichome', r[1])

    CAUSES = ('MLN', 'Streak', 'Fall Armyworm', 'Stem Borer', 'Funza', 'Kipekecha', 'Ugonjwa', 'Panzi')

    def test_no_cause_is_named_before_questions(self):
        """Agizo la mteja (14 Nov): visababishi ni hatua ya mwisho, baada ya maswali."""
        r = self.ask('255700000802', self.T3)[0]
        for name in self.CAUSES:
            self.assertNotIn(name, r)
        self.assertNotIn('umetaja:', r)
        self.assertIn('Kabla sijakupa jibu lolote', r)
        self.assertIn('Swali 1', r)

    def test_uncertain_end_names_no_unconfirmed_cause(self):
        r = self.ask('255700000804', self.T3, 'sijui', 'sijui', 'sijui', 'sijui', 'sijui', 'sijui')
        ends = [x for x in r if 'sitakisia jina' in x]
        self.assertTrue(ends, r)
        last = ends[0]
        if True:                   # haikuthibitisha → haitaji majina
            for name in self.CAUSES:
                self.assertNotIn(name, last)
            self.assertIn('wadudu na magonjwa', last)             # inasema mipaka ya data
            self.assertIn('afisa ugani', last)

    def test_ai_cannot_add_symptoms_the_farmer_never_said(self):
        """Live 14 Nov: AI iliongeza 'mmea unadumaa', 'mistari ya mashimo' → FAW na Stem Borer,
        na 'umetaja:' ilionyesha maneno ambayo mkulima hakuyasema."""
        from unittest import mock
        picked = {'phrases': [
            'Majani yana mistari ya njano, mmea unadumaa, majani hukauka kuanzia pembeni, na mahindi '
            'yanaweza kushindwa kutoa punje vizuri',
            'mmea unadumaa', 'majani yana mistari ya mashimo',
            'Majani yana mistari myembamba ya njano au meupe inayofuata mishipa ya jani'],
            'growth_stage': None, 'extent_pct': None, 'spreading': False}
        with mock.patch('diagnosis.ai_layer.understand_symptoms', return_value=picked):
            r = self.ask('255700000803', self.T3)[0]
        for name in self.CAUSES:
            self.assertNotIn(name, r)
        self.assertIn('Swali 1', r)
        from bot.models import Conversation  # noqa: F401  (trace inahifadhiwa kwa admin)
        from diagnosis import engine as E
        from crops.models import Crop
        st = E.new_state()
        with mock.patch('diagnosis.ai_layer.understand_symptoms', return_value=picked):
            E.step(st, self.T3, Crop.objects.get(crop_name_en='Maize'))
        self.assertNotIn('PST001', st['candidates'])              # FAW haikuingizwa na AI

    def test_age_in_words(self):
        from diagnosis.engine import parse_age_weeks
        self.assertEqual(parse_age_weeks('nilipanda wiki tatu zilizopita'), 3)
        self.assertEqual(parse_age_weeks('mahindi ya miezi miwili'), None)   # 'miwili' si namba tunayoikisia
        self.assertEqual(parse_age_weeks('miezi 2'), 8)

    def test_full_conversation_in_one_thread(self):
        r = self.ask('255700000803', self.T1, self.T2, self.T3)
        self.assertIn('Chagua namba', r[0])
        self.assertIn('Uko sahihi', r[1])
        self.assertIn('Swali 1', r[2])


class LiveRound3Tests(ClientTestRound2):
    """Mazungumzo mawili ya live (14 Nov): FAW iliyothibitishwa, na mkulima anayeuliza kuhusu maji/mbolea."""

    C1 = ["Kilimoni, nina shamba la mahindi huko Morogoro. Baadhi ya majani yana mashimo na mengine yameanza kujikunja. Nimeambiwa nitumie dawa ya kuua wadudu, lakini sijui ni dawa gani. Naomba unishauri dawa ya kutumia na kiasi cha kuchanganya kwenye bomba la lita 20.",
     "Ndiyo, nimeona kinyesi kama vumbi la mbao ndani ya kitovu cha mahindi na baadhi ya funza wana alama ya Y kichwani. Sasa niambie nitumie dawa gani na nichanganye mililita ngapi kwenye bomba la lita 20? Nataka kunyunyizia leo.",
     "Hapana, hawatembei kwa makundi. Nimeona funza wachache ndani ya vitovu vya mahindi, na majani mengine yana mashimo. Mahindi yana wiki tano tangu kupandwa. Je, sasa unaweza kuniambia tatizo linaweza kuwa nini na nifanye nini?",
     "Hapana, hakuna panzi. Nimekuambia kuna funza wenye alama ya Y kichwani, kinyesi ndani ya kitovu na mashimo kwenye majani. Je, hizi si dalili za Fall Armyworm? Na kama ni hivyo, nifanye nini sasa?",
     "nusu ya shamba"]
    C2 = ["Mkuu kilimoni mambo vp, mahindi yangu yana shida bana. Yameanza kuwa ya njano chini chini, mengine kama yanakauka. Nimepanda kama wiki 4 hivi, mvua nazo zimezingua. Sasa nifanyeje?",
     "Hapana mkuu, sijaona wadudu wakitembea makundi wala funza. Ila mvua ni shida huku, ardhi imekauka sana. Na mbolea pia sikuweka nilipopanda. Hivi hiyo inaweza kuwa sababu ya mahindi yangu kuwa ya njano?",
     "Mkuu mbona hunijibu swali langu? Nimekuambia mahindi yana njano chini, ardhi imekauka, mvua hakuna na mbolea sikuweka. Hakuna mistari wala madoa kwenye majani. Sasa unadhani ni wadudu kweli au ni shida ya maji na virutubisho?"]

    def test_first_answer_word_decides(self):
        from diagnosis.engine import parse_answer
        self.assertEqual(parse_answer(self.C1[1]), 'yes')            # 'la' ya "vumbi la mbao" si "hapana"
        self.assertEqual(parse_answer('Hapana, hakuna panzi'), 'no')
        self.assertEqual(parse_answer('la'), 'no')
        self.assertEqual(parse_answer('sijui kama ndiyo'), 'unknown')

    def test_confirmed_faw_is_diagnosed_and_followup_is_answered(self):
        r = self.ask('255700000901', *self.C1[:4])
        self.assertIn('Matokeo ya uchunguzi', r[2])
        self.assertIn('Funza jeshi vamizi', r[2])
        self.assertIn('Ndiyo. Kwa majibu uliyonipa', r[3])            # si uchunguzi mpya wala "hazilingani"
        self.assertIn('Hatua za kuchukua', r[3])
        d = self.ask('255700000901', 'sasa nitumie dawa gani na nichanganye mililita ngapi kwenye bomba la lita 20?')[0]
        self.assertIn('sitoi jina la dawa wala kipimo', d)

    def test_negated_clause_is_not_a_symptom(self):
        from diagnosis.engine import strip_negated
        self.assertNotIn('funza', strip_negated('Hapana mkuu, sijaona wadudu wakitembea makundi wala funza. Ila mvua ni shida'))
        self.assertIn('mvua', strip_negated('sijaona wadudu wala funza. Ila mvua ni shida'))

    def test_water_and_fertilizer_question_is_answered_honestly_without_repeating(self):
        r = self.ask('255700000902', *self.C2)
        self.assertIn('siwezi kuthibitisha', r[1])
        self.assertNotIn('*Swali', r[1])                               # haiendelei na maswali ya wadudu
        self.assertNotEqual(r[1], r[2])
        self.assertIn('Samahani kama jibu langu halikuwa wazi', r[2])
        self.assertNotIn('mbegu', r[2].lower())                         # si mfano wa mbegu tena
