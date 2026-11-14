"""
Benki ya majaribio — ujumbe HALISI wa wakulima (live, majaribio ya mteja, screenshots)
=====================================================================================

Kila kesi: ujumbe, bot ilikuwa inasubiri nini ('pending'), na uelewa sahihi unaotarajiwa.
`python manage.py kilimoni_eval` inapima fomu ya kuelewa (bot/understand.py) dhidi ya kila kesi.

Tatizo jipya likionekana live: ongeza kesi hapa (ujumbe + uelewa sahihi), kisha rekebisha
mpaka ipite — bila kuvunja kesi nyingine.

'goal' inaweza kuwa tuple ya majibu yanayokubalika.
"""

CASES = [
    # ── Majaribio ya mteja (Tito), 13–14 Nov ──
    dict(id='T1', src='mteja Test 1',
         msg="Habari Kilimoni. Nina shamba la mahindi, lakini siku hizi mimea yangu haionekani vizuri. Naomba unisaidie nifanye nini?",
         goal='diagnosis', crop='Mahindi'),
    dict(id='T2', src='mteja Test 2', pending='intake',
         bot="Ondoa mimea iliyoathirika sana, ichome au izike mbali na shamba…",
         msg="Lakini Kilimoni, mimi sijakuambia bado dalili za mahindi yangu. Kwa nini umenishauri niondoe na kuchoma mimea? Si ungeanza kwa kuniuliza maswali ili ujue tatizo ni nini?",
         goal='challenge'),
    dict(id='T3', src='mteja Test 3',
         msg="Kilimoni, nina shamba la mahindi la ekari mbili huko Kongwa, Dodoma. Nilipanda wiki tatu zilizopita, lakini sasa majani ya chini yanaanza kuwa ya njano, wakati majani ya juu bado ni ya kijani. Hii inaweza kuwa ni tatizo gani, na nifanye nini?",
         goal='diagnosis', crop='Mahindi', place='Kongwa'),

    # ── Live: Fall Armyworm (Morogoro) ──
    dict(id='FAW1', src='live 14 Nov',
         msg="Kilimoni, nina shamba la mahindi huko Morogoro. Baadhi ya majani yana mashimo na mengine yameanza kujikunja. Nimeambiwa nitumie dawa ya kuua wadudu, lakini sijui ni dawa gani. Naomba unishauri dawa ya kutumia na kiasi cha kuchanganya kwenye bomba la lita 20.",
         goal='diagnosis', crop='Mahindi', place='Morogoro'),
    dict(id='FAW2', src='live 14 Nov', pending='question',
         bot="Swali 1: Je, kuna kinyesi cha funza (kama vumbi la mbao) ndani ya kitovu cha mmea au funza mwenye alama ya Y kichwani?",
         msg="Ndiyo, nimeona kinyesi kama vumbi la mbao ndani ya kitovu cha mahindi na baadhi ya funza wana alama ya Y kichwani. Sasa niambie nitumie dawa gani na nichanganye mililita ngapi kwenye bomba la lita 20? Nataka kunyunyizia leo.",
         goal='answer', answer='yes'),
    dict(id='FAW3', src='live 14 Nov', pending='question',
         bot="Swali 2: Je, wadudu wako wengi na wanatembea kwa makundi?",
         msg="Hapana, hawatembei kwa makundi. Nimeona funza wachache ndani ya vitovu vya mahindi, na majani mengine yana mashimo. Mahindi yana wiki tano tangu kupandwa. Je, sasa unaweza kuniambia tatizo linaweza kuwa nini na nifanye nini?",
         goal='answer', answer='no'),
    dict(id='FAW4', src='live 14 Nov', pending='question',
         bot="Swali 3: Je, unaona panzi wakiruka au kutembea kwenye shamba?",
         msg="Hapana, hakuna panzi. Nimekuambia kuna funza wenye alama ya Y kichwani, kinyesi ndani ya kitovu na mashimo kwenye majani. Je, hizi si dalili za Fall Armyworm? Na kama ni hivyo, nifanye nini sasa?",
         goal='answer', answer='no'),
    dict(id='FAW5', src='live 14 Nov', pending='after_diagnosis',
         bot="Matokeo ya uchunguzi — Tatizo linalowezekana zaidi: Funza jeshi vamizi (Fall Armyworm)",
         msg="Je, hizi si dalili za Fall Armyworm? Na kama ni hivyo, nifanye nini sasa?",
         goal='followup'),
    dict(id='FAW6', src='live 14 Nov', pending='after_diagnosis',
         bot="Matokeo ya uchunguzi — Funza jeshi vamizi",
         msg="sasa nitumie dawa gani na nichanganye mililita ngapi kwenye bomba la lita 20?",
         goal='followup'),

    # ── Live: njano + ukame + mbolea ──
    dict(id='DRY1', src='live 14 Nov',
         msg="Mkuu kilimoni mambo vp, mahindi yangu yana shida bana. Yameanza kuwa ya njano chini chini, mengine kama yanakauka. Nimepanda kama wiki 4 hivi, mvua nazo zimezingua. Sasa nifanyeje?",
         goal='diagnosis', crop='Mahindi'),
    dict(id='DRY2', src='live 14 Nov', pending='question',
         bot="Swali 1: Je, wadudu wako wengi na wanatembea kwa makundi?",
         msg="Hapana mkuu, sijaona wadudu wakitembea makundi wala funza. Ila mvua ni shida huku, ardhi imekauka sana. Na mbolea pia sikuweka nilipopanda. Hivi hiyo inaweza kuwa sababu ya mahindi yangu kuwa ya njano?",
         goal='abiotic', answer='no'),
    dict(id='DRY3', src='live 14 Nov', pending='question',
         bot="Swali 2: Je, majani yana mistari/madoa ya njano kama michirizi…?",
         msg="Mkuu mbona hunijibu swali langu? Nimekuambia mahindi yana njano chini, ardhi imekauka, mvua hakuna na mbolea sikuweka. Hakuna mistari wala madoa kwenye majani. Sasa unadhani ni wadudu kweli au ni shida ya maji na virutubisho?",
         goal=('abiotic', 'complaint')),

    # ── Live: hustawi wapi / kupanda / Morogolo ──
    dict(id='WG1', src='live 13 Nov', msg="Mahindi  ni zao linalostawi sana wapi?kwa tanzania",
         goal='where_grows', crop='Mahindi'),
    dict(id='WG2', src='live 13 Nov', bot="Bado sina data inayolinganisha mikoa yote… Mahindi",
         msg="Okee sawa .taja maeneo specific kwa Tanzania", goal='where_grows'),
    dict(id='PL1', src='live 13 Nov', msg="Aya sawa... Kipindi Cha kupanda mahindi ni kipindi gani katika mwaka",
         goal='planting', crop='Mahindi'),
    dict(id='PL2', src='live 13 Nov', pending='location', bot="Tafadhali taja mkoa, wilaya au kata yako",
         msg="Morogolo vijijini", goal='answer', place='Morogoro'),

    # ── Live: maswali ya Busokelo/Bariadi (majibu ya demo yalibuni) ──
    dict(id='GAP1', src='live 13 Nov', msg="Jinsi ya kupalilia nitumie mbinu gani?", goal='gap',
         topic='kupalilia na kudhibiti magugu'),
    dict(id='GAP2', src='live 13 Nov', bot="Kupalilia: tumia maji ya baridi…",
         msg="Sijaelewa maelekezo jinsi ya kupalilia", goal=('gap', 'complaint')),
    dict(id='GAP3', src='live 13 Nov', msg="Jinsi ya kuvuna", goal='gap', topic='kuvuna'),
    dict(id='GAP4', src='live 13 Nov', msg="Jinsi ya kuhifadhi", goal='gap', topic='kuhifadhi mazao'),
    dict(id='GAP5', src='live 13 Nov', msg="Naomba kufahamu hali ya masoko", goal='gap', topic='bei na masoko'),
    dict(id='GAP6', src='live 13 Nov', msg="Bei za soko", goal='gap', topic='bei na masoko'),
    dict(id='GAP7', src='live 13 Nov', msg="Hali ya hewa ikoje?", goal='gap', topic='hali ya hewa'),
    dict(id='GAP8', src='live 13 Nov', msg="Vifaa gani vya kutumia wakati WA kuandaa shamba?", goal='gap',
         topic='maandalizi ya shamba na zana'),
    dict(id='GAP9', src='live 13 Nov', bot="Udongo wako unaonekana zaidi kama kichanga, tifutifu…?",
         msg="Mbolea", goal='gap', topic='mbolea'),
    dict(id='GAP10', src='live 13 Nov', msg="Hapa busokelo nitumie mbolea gani?", goal='gap', topic='mbolea',
         place='Busokelo'),
    dict(id='SOIL1', src='live 13 Nov', bot="Unahitaji maelezo zaidi juu ya mbolea au udongo?", msg="Udongo",
         goal=('soil', 'answer')),
    dict(id='LOC1', src='live 13 Nov', pending='location', bot="Bei hutofautiana kati ya mkoa na mkoa. Uko mkoa gani?",
         msg="Morogoro", goal='answer', place='Morogoro'),
    dict(id='HI1', src='live 13 Nov', msg="Hi", goal='greeting'),

    # ── Live: zamani (PR #15–#18) ──
    dict(id='COV1', src='live', msg="Uko na taarifa za mikoa gani", goal='coverage'),
    dict(id='OLD1', src='live', pending='question', bot="Swali 1: …",
         msg="Jinsi ya kupanda mahindi chunya", goal=('planting', 'gap')),
    dict(id='OLD2', src='live', pending='question', bot="Swali 2: …",
         msg="Nimeuliza hatua za kupanda mahindi", goal='complaint'),
    dict(id='OLD3', src='live', msg="mahindi hayako sawa", goal='diagnosis', crop='Mahindi'),
    dict(id='OLD4', src='live', pending='question', bot="Swali 1: …", msg="Hqpana", goal='answer', answer='no'),
    dict(id='OLD5', src='live', msg="niko kongwa nataka mbegu ya mahindi", goal='seed', crop='Mahindi', place='Kongwa'),

    # ── Majibu mafupi kwa swali la bot ──
    dict(id='ANS1', src='regression', pending='question', bot="Swali 1: …", msg="sijui", goal='answer', answer='unknown'),
    dict(id='ANS2', src='regression', pending='extent', bot="ni kiasi gani cha shamba kimeathirika?",
         msg="nusu ya shamba", goal='answer'),
    dict(id='ANS3', src='mteja', pending='intake', bot="Chagua namba ya dalili… na umri wa mimea", msg="2, wiki 6",
         goal='answer'),
    dict(id='ANS4', src='live 13 Nov', pending='question', bot="Unahitaji ushauri juu ya ratiba ya matumizi?",
         msg="Ndio", goal='answer', answer='yes'),

    # ── Moduli za data ──
    dict(id='MOD1', src='regression', msg="Ni mbegu gani ya mahindi nipande Kondoa?", goal='seed', crop='Mahindi',
         place='Kondoa'),
    dict(id='MOD2', src='regression', msg="nipande lini mahindi niko kongwa", goal='planting', crop='Mahindi'),
    dict(id='MOD3', src='regression', msg="zao gani lifuate baada ya mahindi", goal='rotation'),
    dict(id='MOD4', src='regression', msg="udongo wangu ni mfinyanzi unafaa mahindi?", goal='soil'),
    dict(id='MOD5', src='regression', msg="je sc403 inafaa?", goal='seed'),
    dict(id='MOD6', src='regression', msg="mahindi yangu yana mashimo makubwa kwenye majani", goal='diagnosis',
         crop='Mahindi'),
    dict(id='MOD7', src='regression', msg="Kipindi gani nipande mpunga Mbeya", goal='planting'),

    # ── Mitego ya maneno (sababu za marekebisho ya leo) ──
    dict(id='TRAP1', src='kufa≠kufahamu', msg="naomba kufahamu bei ya mahindi", goal='gap', topic='bei na masoko'),
    dict(id='TRAP2', src='kufa≠itakufaa', msg="itakufaa mbegu gani kondoa", goal='seed'),
    dict(id='TRAP3', src='umwa≠umwagiliaji', msg="umwagiliaji wa mahindi unafanywaje", goal='gap', topic='umwagiliaji'),
    dict(id='TRAP4', src='ukame≠abiotic', msg="mbegu gani ya mahindi inastahimili ukame dodoma", goal='seed'),
    dict(id='TRAP5', src='mifugo', msg="nina ng'ombe wanaumwa", goal='gap', topic='mifugo'),
    dict(id='TRAP6', src='challenge', msg="kwa nini umenishauri kuchoma mimea", goal='challenge'),

    # ── Mazungumzo ya kawaida ──
    dict(id='CH1', src='regression', msg="asante", goal='thanks'),
    dict(id='CH2', src='regression', msg="unaitwa nani", goal='identity'),
    dict(id='CH3', src='regression', msg="unaweza kunisaidia nini", goal=('capability', 'identity')),
    dict(id='CH4', src='regression', msg="habari za mpira jana", goal='offtopic'),

    # ── Maneno mapya (hayakutumika kuandika kanuni) — yanapima kama mfumo unaelewa,
    #    si kama unakumbuka. Kanuni za maneno zinatarajiwa kushindwa baadhi; AI izipite. ──
    dict(id='NEW1', src='variant', msg="Mahindi yangu yamegeuka rangi kuanzia chini, sielewi kwa nini",
         goal='diagnosis', crop='Mahindi'),
    dict(id='NEW2', src='variant', msg="nikipanda maharage sasa hivi itakuwa sawa?", goal='planting'),
    dict(id='NEW3', src='variant', msg="nataka kujua kama ardhi yangu inafaa kulima mahindi", goal='soil'),
    dict(id='NEW4', src='variant', msg="baada ya kuvuna mahindi msimu ujao nilime nini?", goal='rotation'),
    dict(id='NEW5', src='variant', msg="mvua zimechelewa huku Kondoa, nipande au nisubiri?", goal='planting'),
    dict(id='NEW6', src='variant', msg="nisaidie kuchagua mahindi mazuri ya kupanda sehemu yenye mvua kidogo",
         goal='seed'),
    dict(id='NEW7', src='variant', pending='question', bot="Swali 1: Je, kuna funza ndani ya kitovu?",
         msg="nimewaona kidogo tu", goal='answer', answer='yes'),
    dict(id='NEW8', src='variant', pending='question', bot="Swali 2: Je, kuna mistari ya njano?",
         msg="aah sijawahi kuona kitu kama hicho", goal='answer', answer='no'),
    dict(id='NEW9', src='variant', msg="mbona unanijibu vitu ambavyo sijauliza", goal='complaint'),
    dict(id='NEW10', src='variant', msg="wewe ni mtu au roboti?", goal='identity'),
    dict(id='NEW11', src='variant', msg="mahindi yanauzwa shilingi ngapi Dodoma siku hizi?", goal='gap',
         topic='bei na masoko'),
    dict(id='NEW12', src='variant', msg="kuna kitu kinatafuna mizizi ya mahindi yangu", goal='diagnosis'),
    dict(id='NEW13', src='variant', msg="nitajuaje kama mahindi yamekomaa?", goal='gap', topic='kuvuna'),
    dict(id='NEW14', src='variant',
         msg="mahindi yamekauka kwa jua kali, mvua hakuna kabisa wiki tatu sasa. ni ukame tu au kuna kingine?",
         goal='abiotic'),
    dict(id='NEW15', src='variant', pending='after_diagnosis', bot="Matokeo ya uchunguzi — Funza jeshi vamizi",
         msg="sawa nitafanya hivyo, asante sana", goal='thanks'),
    dict(id='NEW16', src='variant', pending='after_diagnosis', bot="Matokeo ya uchunguzi — Funza jeshi vamizi",
         msg="naomba unirudie hatua za kufanya", goal='followup'),
    dict(id='NEW17', src='variant', msg="samadi ya kuku inafaa kwa mahindi?", goal='gap', topic='mbolea'),
    dict(id='NEW18', src='variant', pending='location', bot="Tafadhali taja wilaya au kata yako",
         msg="kijiji cha pahi huko kondoa", goal='answer'),

    # ── Live 15 Nov 01:29 ──
    dict(id='L5-1', src='live 15 Nov', bot="Samahani, nadhani nilikuelewa vibaya…",
         msg="Sasa jua ni Kali sana nilime au niache kwanza", goal='planting'),
    dict(id='L5-2', src='live 15 Nov', msg="Ruvuma", goal=('unclear', 'answer')),

    # ── Kundi la pili la maneno mapya (15 Nov): yaliongezwa BAADA ya kurekebisha kanuni kwa
    #    kundi la kwanza, ili kupima tena kwa uaminifu. Usirekebishe kanuni kwa ajili ya haya —
    #    yapime, kisha ongeza kundi jipya. ──
    dict(id='V2-1', src='variant2', msg="majani ya mahindi yamejaa vidoti vyeusi, ni ugonjwa gani huu?",
         goal='diagnosis', crop='Mahindi'),
    dict(id='V2-2', src='variant2', msg="msimu wa mvua za vuli nianze lini kupanda mahindi huku kondoa",
         goal='planting'),
    dict(id='V2-3', src='variant2', msg="mbegu ya muda mfupi ya mahindi ipi nzuri?", goal='seed'),
    dict(id='V2-4', src='variant2', msg="shamba langu ni la mchanga mtupu, nipande nini?", goal=('soil', 'seed')),
    dict(id='V2-5', src='variant2', pending='question', bot="Swali 1: Je, kuna funza ndani ya kitovu?",
         msg="kwa kweli sijaangalia vizuri", goal='answer', answer='unknown'),
    dict(id='V2-6', src='variant2', pending='question', bot="Swali 2: Je, majani yana mistari ya njano?",
         msg="yapo machache sana", goal='answer', answer='yes'),
    dict(id='V2-7', src='variant2', msg="dawa ya kuua magugu kwenye mahindi ni ipi", goal='gap',
         topic='kupalilia na kudhibiti magugu'),
    dict(id='V2-8', src='variant2', msg="niuze mahindi yangu sasa au nisubiri bei ipande?", goal='gap',
         topic='bei na masoko'),
    dict(id='V2-9', src='variant2', msg="nimeanza kulima mwaka huu, naomba ushauri nianze na nini",
         goal=('unclear', 'capability')),
    dict(id='V2-10', src='variant2', msg="kuna wadudu weusi wadogo wamejaa chini ya majani", goal='diagnosis'),
    dict(id='V2-11', src='variant2', pending='after_diagnosis', bot="Matokeo ya uchunguzi — Funza jeshi vamizi",
         msg="hivyo ni kweli umehakikisha au unakisia tu?", goal=('followup', 'challenge')),
    dict(id='V2-12', src='variant2', msg="mahindi yaliyopandwa baada ya maharage huwa yanastawi?",
         goal='rotation'),
]


def check(case, frame):
    """Rudisha list ya makosa (tupu = imepita)."""
    errors = []
    goals = case['goal'] if isinstance(case['goal'], tuple) else (case['goal'],)
    if frame['goal'] not in goals:
        errors.append(f"goal: {frame['goal']} (tarajio {'/'.join(goals)})")
    if case.get('topic') and frame['goal'] == 'gap' and frame.get('topic') != case['topic']:
        errors.append(f"topic: {frame.get('topic')} (tarajio {case['topic']})")
    if case.get('crop'):
        got = frame['crop'].crop_name_sw if frame.get('crop') else None
        if got != case['crop']:
            errors.append(f"crop: {got} (tarajio {case['crop']})")
    if case.get('place') and (frame.get('place') or '').lower() != case['place'].lower():
        errors.append(f"place: {frame.get('place')!r} (tarajio {case['place']})")
    if case.get('answer') and frame.get('answer') != case['answer']:
        errors.append(f"answer: {frame.get('answer')} (tarajio {case['answer']})")
    return errors
