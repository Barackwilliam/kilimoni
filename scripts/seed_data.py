"""
Seed Data – MVP ya Mahindi
Run kutoka root ya project: python manage.py shell < scripts/seed_data.py
AU: python manage.py runscript seed_data (kama unatumia django-extensions)
AU: python scripts/seed_data.py (script inashughulikia path yenyewe)
"""
import os
import sys
import django

# Ongeza root ya project kwenye Python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mkulima_ai.settings')
django.setup()

from crops.models import (
    Zone, LocationMapping, Crop, CropProfile,
    SeedVariety, Intent, FarmerQuestion, Synonym, AnswerTemplate
)
from django.contrib.auth.models import User as DjangoUser
from analytics.models import AdminUser

print("⏳ Kuongeza data ya mwanzo...")

# ─── Zones ────────────────────────────────────────
zones_data = [
    {"zone_name": "Central Zone", "rain_pattern_simple": "chache", "rainfall_band_mm": "400-700mm", "altitude_band_m": "900-1500m", "risk_factors": "Ukame, mvua kuchelewa, udongo kupoteza unyevu"},
    {"zone_name": "Lake Zone", "rain_pattern_simple": "bimodal", "rainfall_band_mm": "700-1200mm", "altitude_band_m": "1100-1800m", "risk_factors": "Unyevu mwingi, ukungu, Fall Armyworm"},
    {"zone_name": "Northern Zone", "rain_pattern_simple": "bimodal", "rainfall_band_mm": "500-900mm", "altitude_band_m": "700-2000m", "risk_factors": "Mvua zisizo za uhakika, udongo tofauti"},
    {"zone_name": "Southern Highlands", "rain_pattern_simple": "wastani", "rainfall_band_mm": "900-1400mm", "altitude_band_m": "1500-2500m", "risk_factors": "Baridi, msimu mfupi"},
    {"zone_name": "Eastern Zone", "rain_pattern_simple": "bimodal", "rainfall_band_mm": "600-1000mm", "altitude_band_m": "0-600m", "risk_factors": "Joto kali, ukame wa mara kwa mara"},
    {"zone_name": "Morogoro Corridor", "rain_pattern_simple": "wastani", "rainfall_band_mm": "700-1200mm", "altitude_band_m": "200-1000m", "risk_factors": "Wadudu, magonjwa ya unyevu"},
    {"zone_name": "Western Zone", "rain_pattern_simple": "wastani", "rainfall_band_mm": "700-1100mm", "altitude_band_m": "800-1500m", "risk_factors": "Mvua zisizo za uhakika"},
]

zones = {}
for zd in zones_data:
    z, _ = Zone.objects.get_or_create(zone_name=zd['zone_name'], defaults=zd)
    zones[zd['zone_name']] = z
print(f"  ✅ Zones: {len(zones)}")

# ─── Location Mappings ────────────────────────────
locations_data = [
    ("Singida", "", "Central Zone"), ("Dodoma", "", "Central Zone"),
    ("Mwanza", "", "Lake Zone"), ("Kagera", "", "Lake Zone"),
    ("Geita", "", "Lake Zone"), ("Mara", "", "Lake Zone"),
    ("Shinyanga", "", "Lake Zone"), ("Simiyu", "", "Lake Zone"),
    ("Arusha", "", "Northern Zone"), ("Kilimanjaro", "", "Northern Zone"),
    ("Manyara", "", "Northern Zone"), ("Tanga", "", "Northern Zone"),
    ("Mbeya", "", "Southern Highlands"), ("Iringa", "", "Southern Highlands"),
    ("Njombe", "", "Southern Highlands"), ("Ruvuma", "", "Southern Highlands"),
    ("Songwe", "", "Southern Highlands"),
    ("Dar es Salaam", "", "Eastern Zone"), ("Pwani", "", "Eastern Zone"),
    ("Lindi", "", "Eastern Zone"),
    ("Morogoro", "", "Morogoro Corridor"),
    ("Tabora", "", "Western Zone"), ("Kigoma", "", "Western Zone"),
    ("Rukwa", "", "Western Zone"), ("Katavi", "", "Western Zone"),
]

for region, district, zone_name in locations_data:
    LocationMapping.objects.get_or_create(
        region_name=region, district_name=district,
        defaults={'zone': zones[zone_name]}
    )
print(f"  ✅ Location Mappings: {len(locations_data)}")

# ─── Crops ───────────────────────────────────────
mahindi, _ = Crop.objects.get_or_create(
    crop_name_sw="Mahindi",
    defaults={'crop_name_en': 'Maize', 'crop_group': 'cereals', 'priority_level': 1, 'active_status': 'active'}
)
Crop.objects.get_or_create(
    crop_name_sw="Maharage",
    defaults={'crop_name_en': 'Beans', 'crop_group': 'legumes', 'priority_level': 2, 'active_status': 'active'}
)
Crop.objects.get_or_create(
    crop_name_sw="Mpunga",
    defaults={'crop_name_en': 'Rice', 'crop_group': 'cereals', 'priority_level': 3, 'active_status': 'active'}
)
print("  ✅ Mazao: Mahindi, Maharage, Mpunga")

# ─── Seed Varieties ───────────────────────────────
varieties = [
    {"variety_name": "PAN 23", "recommended_zone": zones["Central Zone"], "maturity_class": "early", "maturity_days_min": 85, "maturity_days_max": 95, "drought_tolerance": "High", "seed_source": "Pannar", "verification_status": "verified"},
    {"variety_name": "SC 403", "recommended_zone": zones["Central Zone"], "maturity_class": "early", "maturity_days_min": 90, "maturity_days_max": 100, "drought_tolerance": "High", "seed_source": "SeedCo", "verification_status": "verified"},
    {"variety_name": "DK 8051", "recommended_zone": zones["Central Zone"], "maturity_class": "medium", "maturity_days_min": 95, "maturity_days_max": 110, "drought_tolerance": "Medium", "seed_source": "Dekalb", "verification_status": "verified"},
    {"variety_name": "WS 505", "recommended_zone": zones["Lake Zone"], "maturity_class": "medium", "maturity_days_min": 100, "maturity_days_max": 115, "drought_tolerance": "Low", "seed_source": "SeedCo", "verification_status": "verified"},
    {"variety_name": "H614D", "recommended_zone": zones["Lake Zone"], "maturity_class": "medium", "maturity_days_min": 105, "maturity_days_max": 120, "drought_tolerance": "Low", "seed_source": "KARI", "verification_status": "verified"},
    {"variety_name": "TMV 1", "recommended_zone": zones["Northern Zone"], "maturity_class": "medium", "maturity_days_min": 100, "maturity_days_max": 120, "drought_tolerance": "Medium", "seed_source": "TARI", "verification_status": "verified"},
    {"variety_name": "SC 627", "recommended_zone": zones["Southern Highlands"], "maturity_class": "late", "maturity_days_min": 120, "maturity_days_max": 135, "drought_tolerance": "Low", "seed_source": "SeedCo", "verification_status": "verified"},
    {"variety_name": "Longe 10H", "recommended_zone": zones["Southern Highlands"], "maturity_class": "late", "maturity_days_min": 125, "maturity_days_max": 140, "drought_tolerance": "Low", "seed_source": "Uganda Seeds", "verification_status": "verified"},
]
for vd in varieties:
    SeedVariety.objects.get_or_create(crop=mahindi, variety_name=vd['variety_name'], defaults=vd)
print(f"  ✅ Aina za Mbegu: {len(varieties)}")

# ─── Crop Profiles ────────────────────────────────
profiles = [
    {
        "zone": zones["Central Zone"],
        "recommended_varieties": "PAN 23, SC 403, DK 8051",
        "maturity_days_min": 85, "maturity_days_max": 110,
        "planting_window_simple": "Novemba - Desemba (mvua za masika)",
        "spacing": "75cm x 25cm (mmea mmoja) au 90cm x 30cm (mimea miwili)",
        "planting_method": "Panda kwa kina cha cm 5-7. Tumia mbegu 1-2 kwa shimo.",
        "fertilizer_planting": "DAP au CAN: gramu 50-70 kwa shimo. Weka upande wa mbegu, si moja kwa moja.",
        "fertilizer_top_dressing": "Urea au CAN: gramu 50-70 kwa mmea. Wiki 4-6 baada ya kupanda.",
        "common_pests": "Fall Armyworm (viwavi wa majani), Stalk Borer (nondo wa shina), Aphids",
        "common_diseases": "Gray Leaf Spot, Northern Leaf Blight, Maize Streak Virus",
        "common_symptoms": "Majani ya njano = ukosefu wa Urea au ugonjwa. Mashimo kwenye shina = nondo.",
        "harvest_window": "Siku 85-110 baada ya kupanda. Maganda ya kahawia = tayari kuvuna.",
        "storage_notes": "Kausha hadi unyevu 13.5%. Tumia gunia za PICS. Ghala safi na baridi.",
        "market_notes": "Bei TZS 400-700/kg. Bei hupanda Agosti-Novemba. Wasiliana na NFRA.",
        "caution_note": "Wasiliana na Afisa Ugani wa Wilaya yako kwa ushauri zaidi.",
    },
    {
        "zone": zones["Lake Zone"],
        "recommended_varieties": "WS 505, H614D",
        "maturity_days_min": 100, "maturity_days_max": 120,
        "planting_window_simple": "Machi - Aprili (masika) na Oktoba - Novemba (vuli)",
        "spacing": "75cm x 25cm",
        "planting_method": "Panda kwa kina cha cm 4-6.",
        "fertilizer_planting": "DAP gramu 60-80 kwa shimo.",
        "fertilizer_top_dressing": "Urea gramu 60 kwa mmea wiki 5-6 baada ya kupanda.",
        "common_pests": "Fall Armyworm, Thrips, Aphids",
        "common_diseases": "Gray Leaf Spot, Maize Streak Virus",
        "common_symptoms": "Majani ya njano au madoa meupe yanaweza kuwa ugonjwa au ukosefu wa lishe.",
        "harvest_window": "Siku 100-120 baada ya kupanda.",
        "storage_notes": "Hewa ya Lake Zone ina unyevu - kausha vizuri kabla ya kuhifadhi.",
        "market_notes": "Soko kubwa ni Mwanza na Kagera. Wasiliana na Cooperative Society za eneo.",
        "caution_note": "Angalia Fall Armyworm mapema - dawa za msingi ni Emamectin Benzoate.",
    },
    {
        "zone": zones["Southern Highlands"],
        "recommended_varieties": "SC 627, Longe 10H",
        "maturity_days_min": 120, "maturity_days_max": 140,
        "planting_window_simple": "Novemba - Januari (mvua za masika)",
        "spacing": "75cm x 30cm",
        "planting_method": "Panda kwa kina cha cm 5.",
        "fertilizer_planting": "DAP gramu 70-100 kwa shimo.",
        "fertilizer_top_dressing": "Urea gramu 70-80 kwa mmea wiki 5-7 baada ya kupanda.",
        "common_pests": "Aphids, Stalk Borer",
        "common_diseases": "Rust, Gray Leaf Spot",
        "common_symptoms": "Madoa ya rangi ya machungwa kwenye majani = Rust.",
        "harvest_window": "Siku 120-140 baada ya kupanda.",
        "storage_notes": "Hewa ya baridi ya Nyanda za Juu husaidia uhifadhi - hakikisha ghala ni kavu.",
        "market_notes": "Mbeya na Iringa ni vituo vya biashara. NFRA wana ghala Mbeya.",
        "caution_note": "Mahindi ya hapa hukomaa polepole - usivune kabla wakati haujafika.",
    },
]
for pd in profiles:
    CropProfile.objects.get_or_create(crop=mahindi, zone=pd['zone'], defaults=pd)
print(f"  ✅ Crop Profiles: {len(profiles)}")

# ─── Intents ─────────────────────────────────────
intents_data = [
    ("seed_selection", "Mkulima anauliza kuhusu uchaguzi wa mbegu", "crop, location"),
    ("variety_by_location", "Mkulima anauliza mbegu zinazofaa eneo lake", "crop, location, zone"),
    ("planting_time", "Mkulima anauliza wakati wa kupanda", "crop, location"),
    ("spacing", "Mkulima anauliza nafasi ya kupanda", "crop"),
    ("fertilizer_planting", "Mkulima anauliza mbolea ya kupandia", "crop, zone"),
    ("fertilizer_top_dressing", "Mkulima anauliza mbolea ya juu", "crop"),
    ("fertilizer_amount", "Mkulima anauliza kiasi cha mbolea", "crop"),
    ("pest_identification", "Mkulima anauliza kuhusu wadudu", "crop"),
    ("disease_identification", "Mkulima anauliza kuhusu magonjwa", "crop"),
    ("symptom_analysis", "Mkulima anaelezea dalili za zao lake", "crop"),
    ("harvest_time", "Mkulima anauliza wakati wa kuvuna", "crop"),
    ("storage_advice", "Mkulima anauliza jinsi ya kuhifadhi mazao", "crop"),
    ("market_question", "Mkulima anauliza kuhusu soko na bei", "crop, location"),
    ("weather_planting_decision", "Mkulima anauliza kuhusu hali ya hewa na upandaji", "location"),
]
intents = {}
for name, desc, entities in intents_data:
    intent, _ = Intent.objects.get_or_create(
        intent_name=name,
        defaults={'description_sw': desc, 'required_entities': entities}
    )
    intents[name] = intent
print(f"  ✅ Intents: {len(intents)}")

# ─── Synonyms ─────────────────────────────────────
synonyms_data = [
    ("mahindi", "mahind", "crop"), ("mahindi", "maize", "crop"),
    ("mahindi", "corn", "crop"), ("mahindi", "mahidi", "crop"),
    ("maharage", "maharagwe", "crop"), ("maharage", "beans", "crop"),
    ("mpunga", "mchele", "crop"), ("mpunga", "rice", "crop"),
    ("mbolea", "mbole", "input"), ("mbolea", "fertilizer", "input"),
    ("mbegu", "seed", "general"), ("mbegu", "mbeu", "general"),
    ("wadudu", "pest", "general"), ("ugonjwa", "disease", "general"),
    ("ugonjwa", "maradhi", "general"), ("kuvuna", "harvest", "general"),
    ("kupanda", "plant", "general"), ("singida", "sngida", "location"),
    ("dodoma", "dodma", "location"), ("mbeya", "mbya", "location"),
]
for main, var, cat in synonyms_data:
    Synonym.objects.get_or_create(main_word=main, variation=var, defaults={'category': cat})
print(f"  ✅ Synonyms: {len(synonyms_data)}")

# ─── Answer Templates ──────────────────────────────
templates_data = [
    {
        "answer_reference": "maize_central_zone_varieties",
        "intent": intents["variety_by_location"], "crop": mahindi, "zone": zones["Central Zone"],
        "answer_text_sw": "Kwa maeneo ya *Singida, Dodoma na Ukanda wa Kati*, inapendekezwa kutumia mbegu zinazostahimili ukame na kukomaa mapema.\n\n*Mbegu Zinazopendekezwa:*\n• *PAN 23* – Mapema sana (siku 85-95), stahimili ukame vizuri\n• *SC 403* – Mapema (siku 90-100), tija nzuri\n• *DK 8051* – Wastani (siku 95-110), uzalishaji mkubwa\n\nMbegu hizi zinapatikana kwa mawakala wa pembejeo na AGSS.",
        "follow_up_question": "Unataka pia ratiba ya kupanda na mbolea inayofaa?",
        "caution_note": "Wasiliana na Afisa Ugani wako kwa ushauri kulingana na hali ya shamba lako.",
    },
    {
        "answer_reference": "maize_lake_zone_varieties",
        "intent": intents["variety_by_location"], "crop": mahindi, "zone": zones["Lake Zone"],
        "answer_text_sw": "Kwa maeneo ya *Mwanza, Kagera, Geita, Mara na Ukanda wa Ziwa*, mbegu nzuri ni:\n\n• *WS 505* – Wastani (siku 100-115), uzalishaji mzuri\n• *H614D* – Wastani hadi marehemu (siku 105-120), tija kubwa\n\nMbegu hizi zinafanya vizuri katika maeneo yenye mvua za kutosha.",
        "follow_up_question": "Unataka kujua kuhusu udhibiti wa Fall Armyworm katika eneo lako?",
    },
    {
        "answer_reference": "maize_southern_highlands_varieties",
        "intent": intents["variety_by_location"], "crop": mahindi, "zone": zones["Southern Highlands"],
        "answer_text_sw": "Kwa maeneo ya *Mbeya, Iringa, Njombe na Nyanda za Juu Kusini*, mbegu zinazofaa:\n\n• *SC 627* – Marehemu (siku 120-135), uzalishaji mkubwa\n• *Longe 10H* – Marehemu (siku 125-140), inastahimili baridi\n\nNyanda za Juu zina msimu mrefu wa mvua - mbegu za marehemu zinafanya vizuri.",
        "follow_up_question": "Unataka kujua wakati sahihi wa kupanda?",
    },
    {
        "answer_reference": "maize_planting_time_central",
        "intent": intents["planting_time"], "crop": mahindi, "zone": zones["Central Zone"],
        "answer_text_sw": "Katika *Ukanda wa Kati* (Singida, Dodoma), wakati bora wa kupanda mahindi:\n\n📅 *Msimu wa Masika:* Novemba hadi Desemba\n\n*Kanuni ya Kupanda:*\n✓ Panda baada ya mvua ya kwanza ya kutosha (mm 20+ kwa siku 2-3)\n✓ Usipande wakati ardhi ikiwa kavu sana\n✓ Tumia mbegu za mapema (early maturing) kwa ukanda huu\n\n⚠️ Mvua za Singida na Dodoma hazina uhakika - kuwa tayari kupanda haraka mvua ikinyesha.",
        "follow_up_question": "Unataka kujua nafasi ya kupanda na idadi ya mbegu?",
    },
    {
        "answer_reference": "maize_spacing_general",
        "intent": intents["spacing"], "crop": mahindi,
        "answer_text_sw": "Nafasi ya kupanda mahindi:\n\n📏 *Nafasi ya Kawaida:*\n• Safu hadi safu: *75cm*\n• Shimo hadi shimo: *25-30cm*\n• Mimea 1-2 kwa shimo\n\n📏 *Kwa Mbegu za Tija Kubwa:*\n• Safu hadi safu: *90cm*\n• Shimo hadi shimo: *30cm*\n\n*Idadi ya Mimea:* Lengo ni mimea 44,000-53,000 kwa hekta.",
        "follow_up_question": "Unataka pia habari za mbolea ya kupandia?",
    },
    {
        "answer_reference": "maize_fertilizer_planting",
        "intent": intents["fertilizer_planting"], "crop": mahindi,
        "answer_text_sw": "Mbolea ya kupandia mahindi:\n\n🧪 *Mbolea ya Kupandia (Basal Fertilizer):*\n• *DAP:* gramu 50-70 kwa shimo\n• *au CAN:* gramu 60-80 kwa shimo\n\n📋 *Jinsi ya Kutumia:*\n1. Chimba shimo\n2. Weka mbolea upande wa mbegu (si moja kwa moja)\n3. Funika kidogo kwa udongo\n4. Panda mbegu juu\n5. Funika shimo\n\n⚠️ Usiguse mbolea na mbegu moja kwa moja - inaweza kuua mbegu.",
        "follow_up_question": "Unataka pia kujua mbolea ya juu (top dressing)?",
    },
    {
        "answer_reference": "maize_fertilizer_top_dressing",
        "intent": intents["fertilizer_top_dressing"], "crop": mahindi,
        "answer_text_sw": "Mbolea ya juu (top dressing) kwa mahindi:\n\n🧪 *Mbolea ya Juu:*\n• *Urea (46% N):* gramu 50-70 kwa mmea\n• *au CAN:* gramu 60-80 kwa mmea\n\n📅 *Wakati wa Kutumia:*\n• Wiki *4-6* baada ya kupanda\n• Mahindi yanapofikia urefu wa *30-50cm*\n• Kabla ya kutoa maua (tasseling)\n\n📋 *Jinsi ya Kutumia:*\n• Weka kando ya mmea (si juu ya majani)\n• Umbali wa cm 10-15 kutoka shina\n• Funika kwa udongo kidogo",
        "caution_note": "Usitumie Urea wakati wa jua kali - mbolea inaweza kupotea. Asubuhi au jioni ni bora.",
    },
    {
        "answer_reference": "maize_pest_identification",
        "intent": intents["pest_identification"], "crop": mahindi,
        "answer_text_sw": "*Wadudu Wakuu wa Mahindi Tanzania:*\n\n🐛 *1. Fall Armyworm (Viwavi wa Majani)*\n• Dalili: Mashimo makubwa kwenye majani, kinyesi cha kijani-kahawia\n• Udhibiti: Emamectin Benzoate au Spinosad\n• Piga dawa asubuhi au jioni\n\n🐛 *2. Stalk Borer (Nondo wa Shina)*\n• Dalili: Mashimo kwenye shina, mmea kukauka katikati\n• Udhibiti: Piga dawa mapema\n\n🪲 *3. Aphids (Chawa)*\n• Dalili: Wadudu wadogo wa kijani/njano kwenye majani\n• Udhibiti: Dawa za kuua wadudu laini au Neem extract",
        "follow_up_question": "Unataka kujua jinsi ya kutambua magonjwa ya mahindi?",
    },
    {
        "answer_reference": "maize_disease_identification",
        "intent": intents["disease_identification"], "crop": mahindi,
        "answer_text_sw": "*Magonjwa Makuu ya Mahindi:*\n\n🦠 *1. Gray Leaf Spot*\n• Dalili: Madoa ya kijivu/kahawia kwenye majani\n• Udhibiti: Mancozeb au Propiconazole\n\n🦠 *2. Northern Leaf Blight*\n• Dalili: Madoa makubwa ya manjano-kahawia yanayoenea kufuata mshipa\n• Udhibiti: Fungicides, roteshea mazao\n\n🦠 *3. Maize Streak Virus (MSV)*\n• Dalili: Mistari ya manjano kwenye majani\n• Udhibiti: Mbegu zinazostahimili MSV, piga dawa thrips mapema\n\n🦠 *4. Smut (Ugonjwa wa Maputo)*\n• Dalili: Mivimbe meusi kwenye mahindi\n• Udhibiti: Mbegu safi, epuka kukwaruza mimea",
        "follow_up_question": "Je, una dalili fulani maalum kwenye mazao yako?",
    },
    {
        "answer_reference": "maize_harvest_time",
        "intent": intents["harvest_time"], "crop": mahindi,
        "answer_text_sw": "Dalili mahindi yako yako tayari kuvuna:\n\n🌽 *Viashiria vya Ukomavu:*\n✓ Maganda (husks) yamekuwa ya kahawia\n✓ Nywele za mahindi (silks) zimekauka - rangi ya kahawia nyeusi\n✓ Punje ni ngumu na hazipigiki kwa ukucha\n✓ Punje zinaonyesha doa jeusi (black layer) chini\n\n📅 *Muda wa Kuvuna:*\n• Mbegu za mapema: Siku 85-100\n• Mbegu za wastani: Siku 100-120\n• Mbegu za marehemu: Siku 120-140\n\n💡 Vuna wakati unyevu wa punje ni kati ya 20-25%, kisha kaushwa hadi 13.5% kabla ya kuhifadhi.",
        "follow_up_question": "Unataka kujua jinsi ya kuhifadhi mahindi baada ya kuvuna?",
    },
    {
        "answer_reference": "maize_storage",
        "intent": intents["storage_advice"], "crop": mahindi,
        "answer_text_sw": "Uhifadhi mzuri wa mahindi:\n\n🏠 *Hatua za Kuhifadhi:*\n1. *Kausha vizuri* - Unyevu usizidi 13.5%\n2. *Pura* au hifadhi kwa makanda yaliyosafishwa\n3. *Tumia magunia ya PICS* - zinazuia wadudu bila kemikali\n4. *Nyunyiza dawa ya kuhifadhi* (Actellic Super) kama huhifadhi PICS\n5. *Ghala liwe safi* na baridi - epuka unyevu\n6. *Lindo la panya* - tumia mitego au Racumin\n\n⚠️ *Makosa ya Kawaida:*\n• Kuhifadhi mahindi yenye unyevu mwingi\n• Magunia yamewekwa moja kwa moja sakafuni - tumia pallet",
        "follow_up_question": "Unataka kujua bei za soko la sasa?",
    },
    {
        "answer_reference": "maize_market_general",
        "intent": intents["market_question"], "crop": mahindi,
        "answer_text_sw": "Kuhusu soko la mahindi Tanzania:\n\n💰 *Bei za Takriban (2024):*\n• Singida/Dodoma: TZS 350-600/kg\n• Mwanza/Kagera: TZS 400-700/kg\n• Mbeya/Iringa: TZS 350-550/kg\n• Dar es Salaam: TZS 600-900/kg\n\n📈 *Wakati Bora wa Kuuza:*\n• Bei hupanda: Agosti-Novemba (kabla ya mavuno mapya)\n• Bei hushuka: Machi-Juni (wakati wa mavuno)\n\n🏪 *Masoko Makuu:*\n• NFRA - wananunua kwa bei ya dhamana\n• Wafanyabiashara wa ndani\n• Viwanda vya kusaga (Azam, Bakhresa)",
        "caution_note": "Bei zinaweza kubadilika. Wasiliana na mazingira ya eneo lako kwa bei za sasa.",
    },
]

for td in templates_data:
    AnswerTemplate.objects.get_or_create(
        answer_reference=td['answer_reference'],
        defaults={**td, 'active_status': 'active'}
    )
print(f"  ✅ Answer Templates: {len(templates_data)}")

# ─── Sample Farmer Questions ──────────────────────
questions_data = [
    ("Ni mbegu gani ya mahindi nipande Singida?", mahindi, intents["variety_by_location"], "Singida", "mbegu,mahindi,singida", "maize_central_zone_varieties"),
    ("Mbegu za mahindi kwa Dodoma zipi?", mahindi, intents["variety_by_location"], "Dodoma", "mbegu,mahindi,dodoma", "maize_central_zone_varieties"),
    ("Mahindi yapandwe lini Mwanza?", mahindi, intents["planting_time"], "Mwanza", "kupanda,mahindi,mwanza", "maize_lake_zone_varieties"),
    ("Nafasi ya kupanda mahindi ni ngapi?", mahindi, intents["spacing"], "", "nafasi,spacing,mahindi", "maize_spacing_general"),
    ("Mbolea gani ya kupandia mahindi?", mahindi, intents["fertilizer_planting"], "", "mbolea,kupandia,mahindi", "maize_fertilizer_planting"),
    ("Mbolea ya juu kwa mahindi ni ipi?", mahindi, intents["fertilizer_top_dressing"], "", "mbolea,juu,mahindi", "maize_fertilizer_top_dressing"),
    ("Mahindi yana wadudu, nifanye nini?", mahindi, intents["pest_identification"], "", "wadudu,pest,mahindi", "maize_pest_identification"),
    ("Mahindi yangu yana madoa, ni nini?", mahindi, intents["disease_identification"], "", "madoa,ugonjwa,mahindi", "maize_disease_identification"),
    ("Lini niweze kuvuna mahindi?", mahindi, intents["harvest_time"], "", "kuvuna,harvest,mahindi", "maize_harvest_time"),
    ("Jinsi ya kuhifadhi mahindi baada ya kuvuna?", mahindi, intents["storage_advice"], "", "kuhifadhi,storage,mahindi", "maize_storage"),
    ("Bei ya mahindi sokoni ni ngapi?", mahindi, intents["market_question"], "", "bei,soko,mahindi", "maize_market_general"),
]
for qt, crop, intent, loc, kw, ans_ref in questions_data:
    FarmerQuestion.objects.get_or_create(
        question_text=qt,
        defaults={'crop': crop, 'intent': intent, 'location': loc, 'keywords': kw, 'answer_reference': ans_ref}
    )
print(f"  ✅ Sample Questions: {len(questions_data)}")

# ─── Default Superuser ────────────────────────────
if not DjangoUser.objects.filter(username='admin').exists():
    admin_user = DjangoUser.objects.create_superuser(
        username='admin', email='admin@mkulimaai.co.tz', password='Mkulima@2024'
    )
    AdminUser.objects.create(
        django_user=admin_user, name='Super Admin',
        role='super_admin', email='admin@mkulimaai.co.tz', status='active'
    )
    print("  ✅ Admin imetengenezwa: admin / Mkulima@2024")
else:
    print("  ℹ️  Admin tayari ipo")

print("\n✅ Seed data imekamilika! Database iko tayari kwa MVP.")
