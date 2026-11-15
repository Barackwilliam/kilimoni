"""
Benki ya mazungumzo ya kupima ubora (bot/quality.py) — mamia ya ujumbe wa aina mbalimbali
=========================================================================================

Imejengwa kwa makundi: kila kundi lina maneno mengi tofauti ya kuuliza jambo lilelile, na
matarajio ya jumla (si jibu kamili). Pamoja na mazungumzo halisi ya live na ya mteja.

Ukiona tatizo jipya live: ongeza ujumbe huo hapa (kwenye kundi lake, au kama mazungumzo
mapya), kisha `python manage.py kilimoni_quality`.
"""

GAP_WORDS = ('sitabuni', 'sina taarifa')
SEED_WORDS = ('mbegu',)
PLANT_WORDS = ('kupanda', 'panda', 'kanda')
DIAG_WORDS = ('swali 1', 'chagua namba', 'dalili', 'uchunguzi', 'hazilingani', 'sina taarifa', 'zao gani')


def _one(prefix, msgs, **expect):
    return [{'id': f'{prefix}-{i + 1}', 'turns': [dict(msg=m, **expect)]} for i, m in enumerate(msgs)]


SEED = _one('seed', [
    "Ni mbegu gani ya mahindi nipande Kondoa?", "mbegu bora ya mahindi kwa kondoa ni ipi",
    "nataka mbegu ya mahindi", "nishauri mbegu ya mahindi inayofaa eneo langu",
    "mbegu ya mahindi inayostahimili ukame", "mbegu gani ya mahindi inakomaa haraka",
    "je SC403 inafaa kondoa?", "sc 513 ni nzuri?", "niko changaa nataka mbegu ya mahindi",
    "mbegu za mahindi zinazofaa kanda ya kati", "nipande mbegu gani ya mahindi msimu huu",
    "mbegu ya mahindi ya muda mfupi", "mbegu gani ya mahindi inazaa sana",
    "nina shamba kondoa, mbegu gani ya mahindi nzuri", "ushauri wa mbegu ya mahindi tafadhali",
    "mbegu ipi inavumilia ukame kwa mahindi", "nitumie mbegu gani ya mahindi",
    "mahindi mbegu gani inafaa", "mbegu ya mahindi kwa mvua kidogo", "mbegu ya mahindi kata ya busi",
], any=SEED_WORDS, clear=True)

SEED_NO_DATA = _one('seed-nodata', [
    "mbegu bora ya mpunga ni ipi", "nataka mbegu ya mpunga", "mbegu gani ya mpunga nipande",
    "mbegu ya mpunga inayofaa", "nishauri mbegu ya mpunga",
], any=('sina taarifa', 'zao gani', 'mbegu'), clear=True)

PLANTING = _one('plant', [
    "nipande lini mahindi?", "nipande lini mahindi niko kondoa", "wakati gani wa kupanda mahindi",
    "Kipindi Cha kupanda mahindi ni kipindi gani katika mwaka", "msimu wa kupanda mahindi ni lini",
    "mwezi gani nipande mahindi", "mahindi yanapandwa lini kondoa", "nianze kupanda lini",
    "mvua zimeanza nipande sasa?", "nipande mahindi sasa au nisubiri", "lini ni wakati mzuri wa kupanda mahindi",
    "nipande lini mpunga", "nipande lini mahindi changaa", "kupanda mahindi ni mwezi gani",
    "mvua bado hazijaanza nipande?", "nikipanda sasa itakuwa sawa?", "nipande mahindi mwezi huu?",
    "sasa jua ni kali sana nilime au niache kwanza", "msimu wa mvua nianze lini kupanda",
    "nipande lini mahindi ruvuma",
], any=PLANT_WORDS, clear=True)

SOIL = _one('soil', [
    "udongo wangu ni mfinyanzi unafaa mahindi?", "udongo wangu ni mwekundu", "udongo wa kichanga unafaa mahindi",
    "ardhi yangu inafaa kulima mahindi?", "udongo mweusi unaopasuka unafaa nini",
    "udongo wangu ni tifutifu", "nina udongo wa mchanga", "udongo wangu una rutuba?",
    "udongo upi unafaa mahindi", "shamba langu lina udongo mfinyanzi",
], any=('udongo',), clear=True)

ROTATION = _one('rot', [
    "zao gani lifuate baada ya mahindi", "nipande nini baada ya mahindi", "baada ya mahindi nilime nini",
    "mzunguko wa mazao kwa mahindi", "baada ya kuvuna mahindi msimu ujao nilime nini",
    "nipande maharage baada ya mahindi?", "mahindi baada ya maharage yanafaa?", "nibadilishe zao gani baada ya mahindi",
], any=('baada ya', 'mzunguko', 'zao', 'mahindi'), clear=True)

DIAGNOSIS = _one('diag', [
    "mahindi yangu yana mashimo makubwa kwenye majani", "majani ya mahindi yana mistari ya njano",
    "mahindi yangu hayako sawa", "mimea yangu ya mahindi haionekani vizuri", "kuna funza kwenye mahindi yangu",
    "mahindi yanakauka", "majani ya mahindi yanageuka njano", "mahindi yangu yameliwa na wadudu",
    "kuna viwavi kwenye kitovu cha mahindi", "mahindi yamedumaa", "majani ya chini ya mahindi ni njano",
    "panzi wanakula mahindi yangu", "mahindi yangu yana ugonjwa", "kuna wadudu wengi shambani",
    "mahindi yananyauka", "majani ya mahindi yana madoa", "shina la mahindi lina matundu",
    "mahindi yangu yanaoza", "mahindi yana shida bana", "Mahindi yangu yamegeuka rangi kuanzia chini",
    "kuna kitu kinatafuna mizizi ya mahindi yangu", "majani yana mashimo nifanye nini",
    "mimea inakufa", "mahindi yangu yana tatizo gani", "majani yamejikunja",
], any=DIAG_WORDS, clear=True)

GAPS = _one('gap', [
    "Jinsi ya kupalilia nitumie mbinu gani?", "Jinsi ya kuvuna", "Jinsi ya kuhifadhi mahindi",
    "Naomba kufahamu hali ya masoko", "Bei za soko", "bei ya mahindi dodoma ikoje", "Hali ya hewa ikoje?",
    "Vifaa gani vya kutumia wakati wa kuandaa shamba?", "Mbolea ya mahindi", "Hapa busokelo nitumie mbolea gani?",
    "mbolea ya kukuzia ni ipi", "samadi ya kuku inafaa kwa mahindi?", "nina ng'ombe wanaumwa",
    "mbuzi wangu hawali", "umwagiliaji wa mahindi unafanywaje", "nitajuaje kama mahindi yamekomaa?",
    "mahindi yanauzwa shilingi ngapi siku hizi?", "niuze mahindi sasa au nisubiri bei ipande",
    "dawa ya kuua magugu ni ipi", "utabiri wa mvua mwaka huu", "nafasi ya kupanda mahindi ni ngapi",
    "jinsi ya kupogoa", "kuku wangu wanakufa", "naomba kufahamu bei ya mahindi", "DAP au urea ipi bora",
], any=GAP_WORDS, clear=True)

SOCIAL = (
    _one('greet', ["Hi", "Hello", "habari", "mambo", "sasa", "sasa vipi", "habari za asubuhi", "shikamoo"],
         any=('karibu', 'habari', 'kilimoni', 'msaada')) +
    _one('thanks', ["asante", "asante sana", "sawa nimeelewa", "poa", "sawa"]) +
    _one('identity', ["unaitwa nani", "wewe ni nani", "wewe ni mtu au roboti?", "Taarifa unatoa wapi wewe",
                       "unapata wapi taarifa zako", "nani amekutengeneza?"], any=('kilimoni',)) +
    _one('capability', ["unaweza kunisaidia nini", "unasaidia nini"], any=('mbegu', 'shamba', 'nasaidia')) +
    _one('offtopic', ["habari za mpira jana", "nani atashinda uchaguzi", "niambie utani"]) +
    _one('coverage', ["Uko na taarifa za mikoa gani", "unajua mazao gani", "una data ya maeneo gani"],
         any=('taarifa', 'maeneo', 'mazao', 'dodoma', 'kondoa')) +
    _one('where', ["Mahindi ni zao linalostawi sana wapi?kwa tanzania", "mahindi hustawi wapi tanzania",
                   "mpunga unastawi mikoa gani"], any=('sitataja', 'data', 'kanda'))
)

SHORT = (
    _one('crop-only', ["mpunga", "mahindi", "Sasa ni mpunga", "turudi kwenye mahindi", "kuhusu mahindi"],
         any=('tuongelee',)) +
    _one('place-only', ["Ruvuma", "niko kondoa", "niko changaa", "Morogoro", "Morogolo vijijini"],
         any=('uko', 'kondoa', 'changaa', 'eneo', 'kanda')) +
    _one('unknown', ["Katoro", "xyz", "?", "hmm", "ok"])
)

COMPLAINTS = _one('complain', [
    "mbona unanijibu vitu ambavyo sijauliza", "Sijauliza swali", "hujanielewa", "si hivyo",
    "Nimeuliza hatua za kupanda mahindi", "mbona hunijibu swali langu",
])

# Mazungumzo halisi (live na mteja), zamu kwa zamu
CONVERSATIONS = [
    {'id': 'live-faw', 'turns': [
        dict(msg="Kilimoni, nina shamba la mahindi huko Morogoro. Baadhi ya majani yana mashimo na mengine "
                 "yameanza kujikunja. Nimeambiwa nitumie dawa ya kuua wadudu, lakini sijui ni dawa gani. Naomba "
                 "unishauri dawa ya kutumia na kiasi cha kuchanganya kwenye bomba la lita 20.", any=DIAG_WORDS),
        dict(msg="Ndiyo, nimeona kinyesi kama vumbi la mbao ndani ya kitovu cha mahindi na baadhi ya funza wana "
                 "alama ya Y kichwani. Sasa niambie nitumie dawa gani na nichanganye mililita ngapi kwenye bomba "
                 "la lita 20? Nataka kunyunyizia leo."),
        dict(msg="Hapana, hawatembei kwa makundi. Nimeona funza wachache ndani ya vitovu vya mahindi, na majani "
                 "mengine yana mashimo. Mahindi yana wiki tano tangu kupandwa."),
        dict(msg="Hapana, hakuna panzi. Nimekuambia kuna funza wenye alama ya Y kichwani. Je, hizi si dalili za "
                 "Fall Armyworm? Na kama ni hivyo, nifanye nini sasa?", any=('funza jeshi', 'fall armyworm')),
        dict(msg="sasa nitumie dawa gani na nichanganye mililita ngapi kwenye bomba la lita 20?",
             any=('sitoi', 'kibandiko', 'afisa ugani')),
    ]},
    {'id': 'live-dry', 'turns': [
        dict(msg="Mkuu kilimoni mambo vp, mahindi yangu yana shida bana. Yameanza kuwa ya njano chini chini, "
                 "mengine kama yanakauka. Nimepanda kama wiki 4 hivi, mvua nazo zimezingua. Sasa nifanyeje?"),
        dict(msg="Hapana mkuu, sijaona wadudu wakitembea makundi wala funza. Ila mvua ni shida huku, ardhi "
                 "imekauka sana. Na mbolea pia sikuweka nilipopanda. Hivi hiyo inaweza kuwa sababu ya mahindi "
                 "yangu kuwa ya njano?", any=('siwezi kuthibitisha',)),
        dict(msg="Mkuu mbona hunijibu swali langu? Nimekuambia mahindi yana njano chini, ardhi imekauka, mvua "
                 "hakuna na mbolea sikuweka. Sasa unadhani ni wadudu kweli au ni shida ya maji na virutubisho?",
             any=('samahani',)),
    ]},
    {'id': 'client-tests', 'turns': [
        dict(msg="Habari Kilimoni. Nina shamba la mahindi, lakini siku hizi mimea yangu haionekani vizuri. "
                 "Naomba unisaidie nifanye nini?", any=('chagua namba', 'dalili'), none=('ichome',)),
        dict(msg="Lakini Kilimoni, mimi sijakuambia bado dalili za mahindi yangu. Kwa nini umenishauri niondoe na "
                 "kuchoma mimea? Si ungeanza kwa kuniuliza maswali ili ujue tatizo ni nini?", any=('samahani',)),
        dict(msg="Kilimoni, nina shamba la mahindi la ekari mbili huko Kongwa, Dodoma. Nilipanda wiki tatu "
                 "zilizopita, lakini sasa majani ya chini yanaanza kuwa ya njano, wakati majani ya juu bado ni ya "
                 "kijani. Hii inaweza kuwa ni tatizo gani, na nifanye nini?",
             none=('Funza jeshi', 'Streak', 'MLN')),
    ]},
    {'id': 'live-greeting', 'turns': [
        dict(msg="nipande lini mahindi niko kondoa"), dict(msg="Hello", any=('tuendelee',)),
        dict(msg="Sasa ni mpunga", any=('tuongelee *mpunga*',)), dict(msg="2", any=('mpunga',)),
        dict(msg="Katoro"), dict(msg="Ruvuma", any=('ruvuma',)),
        dict(msg="Sijauliza swali"),
        dict(msg="Sasa jua ni Kali sana nilime au niache kwanza", none=('uko sahihi',)),
        dict(msg="Hello"), dict(msg="Nina swali jipya", any=('uliza swali',)),
        dict(msg="Hello"), dict(msg="Basi turudi kwenye mahindi", any=('tuongelee *mahindi*',)),
        dict(msg="3", any=('kupanda',)),
    ]},
    {'id': 'live-busokelo', 'turns': [
        dict(msg="Jinsi ya kupalilia nitumie mbinu gani?", any=GAP_WORDS),
        dict(msg="Sijaelewa maelekezo jinsi ya kupalilia"), dict(msg="Jinsi ya kuvuna"),
        dict(msg="Jinsi ya kuhifadhi"), dict(msg="Naomba kufahamu hali ya masoko", any=GAP_WORDS),
        dict(msg="Ndiyo"), dict(msg="Bei za soko"), dict(msg="Morogoro"), dict(msg="Hali ya hewa ikoje?"),
        dict(msg="Vifaa gani vya kutumia wakati WA kuandaa shamba?"), dict(msg="Udongo"), dict(msg="Mbolea"),
        dict(msg="Hapa busokelo nitumie mbolea gani?"), dict(msg="Ndio"), dict(msg="Jinsi ya kupalilia"),
    ]},
    {'id': 'live-wheregrows', 'turns': [
        dict(msg="Hi"), dict(msg="Mahindi  ni zao linalostawi sana wapi?kwa tanzania"),
        dict(msg="Okee sawa .taja maeneo specific kwa Tanzania"),
        dict(msg="Aya sawa... Kipindi Cha kupanda mahindi ni kipindi gani katika mwaka", any=PLANT_WORDS),
        dict(msg="Morogolo vijijini", any=('morogoro',)),
    ]},
    {'id': 'menu-flow', 'turns': [
        dict(msg="naomba msaada"), dict(msg="1"), dict(msg="mahindi"), dict(msg="2, wiki 6"),
        dict(msg="ndiyo"), dict(msg="hapana"), dict(msg="sijui"), dict(msg="nusu ya shamba"),
    ]},
    {'id': 'switch-midway', 'turns': [
        dict(msg="mahindi yangu yana mashimo makubwa kwenye majani"),
        dict(msg="kwanza niambie mbegu nzuri ya mahindi kwa kondoa", any=SEED_WORDS, none=('swali 2',)),
        dict(msg="asante"), dict(msg="na nipande lini?", any=PLANT_WORDS),
    ]},
]


# ── Kundi B (15 Nov): maneno mapya, yaliyoandikwa BAADA ya kanuni — yanapima uelewa kwa uaminifu ──
B_SEED = _one('b-seed', [
    "nataka kununua mbegu ya mahindi, ipi bora?", "kuna mbegu ya mahindi ya siku 90?",
    "mbegu ya mahindi isiyoshambuliwa na magonjwa", "mbegu ya kupanda kondoa mvua zikichelewa",
    "hii SC 529 inafaa kanda ya kati?", "rafiki yangu ananishauri sc513, wewe unasemaje?",
    "mbegu chotara ya mahindi nzuri", "nipendekezee mbegu ya mahindi", "mbegu ipi ya mahindi kwa shamba dogo",
    "mbegu ya mahindi kwa eneo kame",
], any=SEED_WORDS + ('zao gani',), clear=True)
B_PLANT = _one('b-plant', [
    "mvua za vuli nipande mahindi?", "mahindi nipande mwezi wa kumi na mbili?", "ni sahihi kupanda mahindi desemba?",
    "nimechelewa kupanda, bado naweza?", "mvua imenyesha jana, nipande kesho?", "tarehe gani nzuri ya kupanda mahindi",
    "nikipanda januari itakuwa sawa?", "mvua za masika nianze kupanda lini", "nipande kabla mvua haijaanza?",
    "mahindi ya msimu ujao nipande lini",
], any=PLANT_WORDS, clear=True)
B_DIAG = _one('b-diag', [
    "majani ya mahindi yana vidoti vyeusi", "mahindi yangu yana unga mweupe kwenye majani",
    "kuna wadudu weusi wadogo chini ya majani", "mahindi yamelala chini", "masuke ya mahindi yameoza",
    "shina linavunjika", "majani yanakatika katika", "mahindi yamekuwa mekundu", "kuna kinyesi kama machujo kwenye mmea",
    "mahindi hayakui kabisa", "mmea umekauka katikati", "majani yana michirizi meupe",
], any=DIAG_WORDS, clear=True)
B_GAP = _one('b-gap', [
    "magunia mangapi kwa ekari", "nikuze mahindi kwa mbolea gani", "nawezaje kuzuia panya ghalani",
    "nina mpango wa kufuga kuku", "matrekta yanakodishwa wapi", "mbolea ya chumvichumvi inafaa?",
    "mvua itanyesha lini", "nitauza wapi mahindi yangu", "jinsi ya kukausha mahindi", "nafasi kati ya mistari",
], any=GAP_WORDS + ('sina data', 'sitataja'), clear=True)
B_MISC = (
    _one('b-greet', ["hujambo", "salaam", "habari za mchana", "mambo vipi", "hey"], any=('karibu', 'habari')) +
    _one('b-thanks', ["nashukuru sana", "sawa asante", "poa sana"]) +
    _one('b-off', ["unaweza kuimba?", "bei ya simu ni ngapi", "nipe namba ya rais"]) +
    _one('b-short', ["maharage", "Dodoma", "kondoa", "ndiyo", "hapana", "sawa"])
)
B_CONV = [
    {'id': 'b-conv-seed-loc', 'turns': [
        dict(msg="nataka mbegu ya mahindi", any=SEED_WORDS), dict(msg="niko kikore", any=SEED_WORDS),
        dict(msg="asante sana"), dict(msg="na udongo wa kichanga unafaa?", any=('udongo',)),
    ]},
    {'id': 'b-conv-plant-rain', 'turns': [
        dict(msg="nipande lini mahindi"), dict(msg="kondoa"), dict(msg="ndiyo mvua zimeanza"),
        dict(msg="sawa"), dict(msg="na mbegu gani?", any=SEED_WORDS),
    ]},
    {'id': 'b-conv-diag-full', 'turns': [
        dict(msg="mahindi yangu yana mashimo makubwa kwenye majani", any=DIAG_WORDS),
        dict(msg="ndiyo nimeona"), dict(msg="hapana"), dict(msg="hapana"), dict(msg="nusu ya shamba"),
        dict(msg="asante, nitafanya hivyo"), dict(msg="naomba unirudie hatua"),
    ]},
    {'id': 'b-conv-cancel', 'turns': [
        dict(msg="mahindi yangu yana shida"), dict(msg="acha"), dict(msg="nipande lini mahindi kondoa", any=PLANT_WORDS),
    ]},
    {'id': 'b-conv-topic-hop', 'turns': [
        dict(msg="bei ya mahindi ikoje", any=GAP_WORDS), dict(msg="sawa basi mbegu nzuri ya mahindi", any=SEED_WORDS),
        dict(msg="kondoa"), dict(msg="na nipande lini?", any=PLANT_WORDS), dict(msg="asante"),
        dict(msg="majani yana mistari ya njano", any=DIAG_WORDS),
    ]},
    {'id': 'b-conv-repeat', 'turns': [
        dict(msg="bei za soko"), dict(msg="bei za soko"), dict(msg="bei za soko"),
        dict(msg="hali ya hewa"), dict(msg="hali ya hewa"),
    ]},
    {'id': 'b-conv-unclear', 'turns': [
        dict(msg="nisaidie"), dict(msg="nisaidie tafadhali"), dict(msg="1"), dict(msg="mahindi"),
        dict(msg="1 na 2, wiki 4"),
    ]},
]


def all_conversations():
    return (SEED + SEED_NO_DATA + PLANTING + SOIL + ROTATION + DIAGNOSIS + GAPS + SOCIAL + SHORT + COMPLAINTS
            + CONVERSATIONS + B_SEED + B_PLANT + B_DIAG + B_GAP + B_MISC + B_CONV)


def turn_count():
    return sum(len(c['turns']) for c in all_conversations())
