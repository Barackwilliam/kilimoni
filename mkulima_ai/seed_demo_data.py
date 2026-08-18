"""
seed_demo_data.py — Demo Data ya Dashboard kwa Presentation
============================================================
Script hii inaongeza data ya maonyesho kwenye dashboard:
  - Wakulima (Users) wa Tanzania
  - Mazungumzo (Conversations) ya kweli
  - Maswali Yasiyoshughulikiwa (UnresolvedQueries)
  - Analytics Logs

JINSI YA KUTUMIA:
  python scripts/seed_demo_data.py

Kumbuka: Kwanza run seed_data.py kabla ya hii.
"""

import os
import sys
import random
import django
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mkulima_ai.settings')
django.setup()

from django.utils import timezone
from bot.models import User, Conversation, UnresolvedQuery
from crops.models import Crop, Intent, Zone
from analytics.models import AnalyticsLog

print("⏳ Kuongeza demo data ya dashboard...")

# ─── Wakulima wa Demo ──────────────────────────────────────────────────────────
wakulima_data = [
    {"phone": "255712345678", "region": "Singida",       "district": "Singida Mjini", "lang": "sw"},
    {"phone": "255767891234", "region": "Dodoma",        "district": "Chamwino",      "lang": "sw"},
    {"phone": "255754321098", "region": "Mwanza",        "district": "Ilemela",       "lang": "sw"},
    {"phone": "255789012345", "region": "Mbeya",         "district": "Mbeya Mjini",   "lang": "sw"},
    {"phone": "255723456789", "region": "Arusha",        "district": "Arumeru",       "lang": "sw"},
    {"phone": "255745678901", "region": "Morogoro",      "district": "Kilosa",        "lang": "sw"},
    {"phone": "255698765432", "region": "Kagera",        "district": "Bukoba Vijijini","lang": "sw"},
    {"phone": "255711223344", "region": "Iringa",        "district": "Kilolo",        "lang": "sw"},
    {"phone": "255733445566", "region": "Tabora",        "district": "Urambo",        "lang": "sw"},
    {"phone": "255722334455", "region": "Kilimanjaro",   "district": "Moshi Vijijini","lang": "sw"},
    {"phone": "255744556677", "region": "Shinyanga",     "district": "Shinyanga Vijijini", "lang": "sw"},
    {"phone": "255755667788", "region": "Njombe",        "district": "Wanging'wa",    "lang": "sw"},
]

wakulima = []
for w in wakulima_data:
    siku_nyuma = random.randint(5, 45)
    mwisho_kuonekana = timezone.now() - timedelta(days=random.randint(0, siku_nyuma - 1))
    user, created = User.objects.get_or_create(
        phone_number=w["phone"],
        defaults={
            "region": w["region"],
            "district": w["district"],
            "preferred_language": w["lang"],
            "message_count": random.randint(3, 28),
            "active_status": "active",
            "first_seen_at": timezone.now() - timedelta(days=siku_nyuma),
            "last_seen_at": mwisho_kuonekana,
        }
    )
    wakulima.append(user)

print(f"  ✅ Wakulima: {len(wakulima)}")

# ─── Retrieve models ──────────────────────────────────────────────────────────
mahindi = Crop.objects.filter(crop_name_sw="Mahindi").first()
maharage = Crop.objects.filter(crop_name_sw="Maharage").first()
mpunga = Crop.objects.filter(crop_name_sw="Mpunga").first()

intents = {i.intent_name: i for i in Intent.objects.all()}
zones = {z.zone_name: z for z in Zone.objects.all()}

# ─── Mazungumzo (Conversations) ───────────────────────────────────────────────
mazungumzo_data = [
    # Mkulima 1 - Singida - maswali 4
    {
        "user": wakulima[0], "crop": mahindi,
        "intent_key": "variety_by_location", "location": "Singida",
        "pairs": [
            ("Ni mbegu gani ya mahindi nipande Singida?",
             "Kwa maeneo ya Singida, inapendekezwa: PAN 23 (siku 85-95), SC 403 (siku 90-100). Mbegu hizi zinastahimili ukame vizuri.\n─────────────────\n🤖 Mkulima AI Tanzania\n💬 Piga nambari *0* kupata msaada zaidi"),
            ("PAN 23 inapatikana wapi Singida?",
             "PAN 23 inapatikana kwa mawakala wa pembejeo Singida Mjini na AGSS. Pia unaweza kuwasiliana na Afisa Ugani wa Wilaya yako.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Mbolea gani ya kupandia?",
             "Tumia DAP gramu 50-70 kwa shimo au CAN gramu 60-80. Weka upande wa mbegu, si moja kwa moja.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Asante sana, umesaidia",
             "Karibu sana! 🌱 Mkulima AI Tanzania ipo kukusaidia wakati wote. Piga *0* ukihitaji msaada zaidi."),
        ]
    },
    # Mkulima 2 - Dodoma
    {
        "user": wakulima[1], "crop": mahindi,
        "intent_key": "planting_time", "location": "Dodoma",
        "pairs": [
            ("Mahindi yapandwe lini Dodoma?",
             "Dodoma: Panda Novemba hadi Desemba baada ya mvua ya kwanza ya kutosha. Usipande ardhi ikiwa kavu.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Mvua bado haijanyesha, nisubiri?",
             "Ndiyo, subiri mvua ya kwanza (mm 20+ kwa siku 2-3 mfululizo) kisha panda haraka. Mbegu ziwe tayari mapema.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 3 - Mwanza - wadudu
    {
        "user": wakulima[2], "crop": mahindi,
        "intent_key": "pest_identification", "location": "Mwanza",
        "pairs": [
            ("Mahindi yangu yana viwavi wakubwa wanakula majani usiku",
             "Hii ni Fall Armyworm (Viwavi wa Majani). 🐛\nDawa: Emamectin Benzoate au Spinosad.\nPiga dawa asubuhi au jioni tu.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Dawa ya Emamectin inapatikana wapi Mwanza?",
             "Inapatikana kwa mawakala wa pembejeo Mwanza Mjini. Bei takriban TZS 5,000-15,000 kulingana na kiasi. Wasiliana na duka la pembejeo lako.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Ninapiga dawa lakini bado wako",
             "Piga dawa mapema asubuhi (kabla saa 10) au jioni (baada ya saa 12). Hakikisha unafikia ndani ya mmea (funnel). Rudia baada ya siku 7-10 kama bado wako.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 4 - Mbeya - kuvuna
    {
        "user": wakulima[3], "crop": mahindi,
        "intent_key": "harvest_time", "location": "Mbeya",
        "pairs": [
            ("Mahindi yangu Mbeya yako tayari kuvuna?",
             "Angalia hivi: Maganda ya kahawia ✓, nywele zimekauka ✓, punje ngumu ✓. Kama dalili hizi zipo, mahindi yako tayari! 🌽\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Ninaweza kuvuna mvua ikiwa?",
             "Epuka kuvuna wakati wa mvua - unyevu utaongezeka na kusababisha uozo wakati wa kuhifadhi. Subiri hewa nzuri.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Jinsi ya kuhifadhi baada ya kuvuna?",
             "1. Kausha hadi unyevu 13.5% 2. Tumia magunia ya PICS 3. Ghala liwe safi na baridi 4. Lindo la panya\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 5 - Arusha - mbegu
    {
        "user": wakulima[4], "crop": mahindi,
        "intent_key": "seed_selection", "location": "Arusha",
        "pairs": [
            ("Napenda mbegu ya mahindi inayotoa mavuno mengi Arusha",
             "Kwa Arusha (Northern Zone): TMV 1 (TARI) inafanya vizuri. Matunda makubwa na stahimili magonjwa.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("TMV 1 inapandwa lini Arusha?",
             "Arusha ina mvua mbili: Masika (Machi-Aprili) na Vuli (Oktoba-Novemba). Panda mwanzo wa kila msimu wa mvua.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 6 - Morogoro - ugonjwa
    {
        "user": wakulima[5], "crop": mahindi,
        "intent_key": "disease_identification", "location": "Morogoro",
        "pairs": [
            ("Mahindi yangu yana madoa ya kijivu kwenye majani",
             "Hii inaweza kuwa Gray Leaf Spot. 🦠\nDawa: Mancozeb au Propiconazole.\nRoteshea mazao msimu ujao.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Roteshea maana yake nini?",
             "Roteshea = panda zao tofauti shambani mwako msimu ujao. Mfano: mahindi mwaka huu → maharage au viazi mwaka ujao. Hii inazuia magonjwa yasirudie.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 7 - Kagera - soko
    {
        "user": wakulima[6], "crop": mahindi,
        "intent_key": "market_question", "location": "Kagera",
        "pairs": [
            ("Bei ya mahindi Kagera ni ngapi sasa?",
             "Bei za takriban Kagera (2024):\n• Sokoni: TZS 400-650/kg\n• Wakati bora kuuza: Agosti-Novemba\n\nBei zinaweza kutofautiana. Wasiliana na Cooperative Society ya eneo lako.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("NFRA wananunua Kagera?",
             "NFRA wana ghala baadhi ya maeneo. Wasiliana na ofisi ya NFRA Kagera au Mwanza kwa taarifa za ununuzi wa msimu huu.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 8 - Iringa - mbolea
    {
        "user": wakulima[7], "crop": mahindi,
        "intent_key": "fertilizer_top_dressing", "location": "Iringa",
        "pairs": [
            ("Wakati wa mbolea ya juu kwa mahindi Iringa?",
             "Mbolea ya juu (Urea/CAN) wiki 5-7 baada ya kupanda, mahindi yakiwa urefu wa 30-50cm. Iringa: mvua nyingi = funika mbolea kidogo kwa udongo.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Gramu ngapi kwa mmea?",
             "Urea: gramu 50-70 kwa mmea. CAN: gramu 60-80 kwa mmea. Weka kando ya mmea umbali wa cm 10-15 kutoka shina.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 9 - Tabora - maharage
    {
        "user": wakulima[8], "crop": maharage,
        "intent_key": "seed_selection", "location": "Tabora",
        "pairs": [
            ("Mbegu za maharage zipi zinafaa Tabora?",
             "🌱 Kwa Tabora (Western Zone), maharage yanayofaa:\n• Lyamungu 85 - mapema, tija nzuri\n• SUA 90 - wastani, stahimili magonjwa\n\nWasiliana na TARI Tumbi Tabora kwa mbegu bora.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
    # Mkulima 10 - Kilimanjaro - mpunga
    {
        "user": wakulima[9], "crop": mpunga,
        "intent_key": "planting_time", "location": "Kilimanjaro",
        "pairs": [
            ("Mpunga upandwe lini Kilimanjaro?",
             "Kilimanjaro: Mpunga kwenye mabondeni hupandwa:\n• Masika: Machi-Aprili\n• Vuli: Oktoba-Novemba\n\nHitaji maji ya umwagiliaji au mvua ya kutosha.\n─────────────────\n🤖 Mkulima AI Tanzania"),
            ("Umbali wa mpanda mpunga ni upi?",
             "Nafasi ya mpunga: Safu 20-25cm, shimo 20cm. Miche 2-3 kwa shimo. Kwa SRI method: 25x25cm, mche 1 kwa shimo.\n─────────────────\n🤖 Mkulima AI Tanzania"),
        ]
    },
]

conversation_count = 0
analytics_count = 0

for mz in mazungumzo_data:
    user = mz["user"]
    crop = mz["crop"]
    intent = intents.get(mz["intent_key"])
    location = mz["location"]
    zone_obj = None

    # Match zone
    for zname, zobj in zones.items():
        if location.lower() in zname.lower() or zname.lower() in location.lower():
            zone_obj = zobj
            break

    base_time = timezone.now() - timedelta(days=random.randint(1, 20))

    for i, (swali, jibu) in enumerate(mz["pairs"]):
        msg_time = base_time + timedelta(minutes=i * random.randint(1, 10))

        # Inbound - mkulima
        Conversation.objects.get_or_create(
            user=user,
            raw_message=swali, 
            message_direction="inbound",
            defaults={
                "message_type": "text",
                "normalized_text": swali.lower(),
                "detected_crop": crop,
                "detected_intent": intent,
                "detected_location": location,
                "detected_zone": zone_obj,
                "created_at": msg_time,
            }
        )

        # Outbound - bot reply
        Conversation.objects.get_or_create(
            user=user,
            raw_message=jibu,
            message_direction="outbound",
            defaults={
                "message_type": "text",
                "normalized_text": "",
                "detected_crop": crop,
                "detected_intent": intent,
                "detected_location": location,
                "detected_zone": zone_obj,
                "response_reference": mz.get("intent_key", ""),
                "created_at": msg_time + timedelta(seconds=random.randint(2, 8)),
            }
        )

        conversation_count += 2

        # Analytics log
        AnalyticsLog.objects.create(
            user_id=user.id,
            phone_number=user.phone_number,
            crop=crop,
            intent=intent,
            zone=zone_obj,
            success_flag=True,
            response_time_ms=random.randint(180, 1200),
            created_at=msg_time,
        )
        analytics_count += 1

print(f"  ✅ Mazungumzo: {conversation_count} (inbound + outbound)")
print(f"  ✅ Analytics logs: {analytics_count}")

# ─── Maswali Yasiyoshughulikiwa (UnresolvedQueries) ───────────────────────────
unresolved_data = [
    {
        "user": wakulima[0], "crop": mahindi,
        "message": "Bei ya mbolea DAP imeongezeka sana, kuna bei mpya?",
        "normalized": "bei mbolea dap imeongezeka kuna bei mpya",
        "reason": "no_answer",
        "status": "pending",
    },
    {
        "user": wakulima[2], "crop": mahindi,
        "message": "Ninaweza kupata mkopo wa pembejeo wapi Mwanza?",
        "normalized": "mkopo pembejeo mwanza",
        "reason": "no_intent",
        "status": "pending",
    },
    {
        "user": wakulima[4], "crop": None,
        "message": "Hali ya hewa Arusha itakuwa vipi wiki ijayo?",
        "normalized": "hali hewa arusha wiki ijayo",
        "reason": "no_intent",
        "status": "pending",
    },
    {
        "user": wakulima[5], "crop": mahindi,
        "message": "mahindi yangu yana rangi ya zambarau kwenye majani",
        "normalized": "mahindi rangi zambarau majani",
        "reason": "no_answer",
        "status": "pending",
    },
    {
        "user": wakulima[7], "crop": maharage,
        "message": "Maharage yangu yamebadilika rangi na kudondoka kabla ya wakati",
        "normalized": "maharage badilika rangi kudondoka kabla wakati",
        "reason": "no_answer",
        "status": "resolved",
        "resolution_notes": "Inaweza kuwa Anthracnose - fungicide ya Copper inasaidia. Imeongezwa kwenye template.",
    },
    {
        "user": wakulima[9], "crop": mpunga,
        "message": "Mpunga wangu unasimama polepole sana, nitumie nini?",
        "normalized": "mpunga kusimama polepole nini",
        "reason": "no_answer",
        "status": "pending",
    },
    {
        "user": wakulima[10], "crop": mahindi,
        "message": "Nondo wa shina wameharibu zaidi ya nusu ya shamba langu Shinyanga",
        "normalized": "nondo shina waharibu nusu shamba shinyanga",
        "reason": "no_answer",
        "status": "pending",
    },
    {
        "user": wakulima[11], "crop": mahindi,
        "message": "Baridi Njombe inasababisha mahindi yangu kudumaa",
        "normalized": "baridi njombe mahindi kudumaa",
        "reason": "no_answer",
        "status": "pending",
    },
]

unresolved_count = 0
for ud in unresolved_data:
    days_ago = random.randint(1, 14)
    obj, created = UnresolvedQuery.objects.get_or_create(
        user=ud["user"],
        raw_message=ud["message"],
        defaults={
            "normalized_text": ud["normalized"],
            "detected_crop": ud.get("crop"),
            "reason": ud["reason"],
            "status": ud["status"],
            "resolution_notes": ud.get("resolution_notes", ""),
            "created_at": timezone.now() - timedelta(days=days_ago),
        }
    )
    if created:
        unresolved_count += 1

print(f"  ✅ Maswali Yasiyoshughulikiwa: {unresolved_count}")

# ─── Analytics ya nyuma (history) ─────────────────────────────────────────────
# Ongeza logs za wiki 3 zilizopita ili grafiki zionekane
zone_list = list(zones.values())
intent_list = list(intents.values())
crop_list = [c for c in [mahindi, maharage, mpunga] if c]

history_count = 0
for days_back in range(1, 22):
    logs_kwa_siku = random.randint(8, 35)
    for _ in range(logs_kwa_siku):
        user = random.choice(wakulima)
        AnalyticsLog.objects.create(
            user_id=user.id,
            phone_number=user.phone_number,
            crop=random.choice(crop_list),
            intent=random.choice(intent_list),
            zone=random.choice(zone_list),
            success_flag=random.choices([True, False], weights=[85, 15])[0],
            response_time_ms=random.randint(150, 2000),
            created_at=timezone.now() - timedelta(days=days_back, hours=random.randint(6, 22), minutes=random.randint(0, 59)),
        )
        history_count += 1

print(f"  ✅ Analytics history (siku 21): {history_count} logs")

# ─── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("✅ DEMO DATA IMEKAMILIKA!")
print("="*55)
print(f"  👥 Wakulima:               {len(wakulima)}")
print(f"  💬 Mazungumzo:             {conversation_count}")
print(f"  ❓ Maswali Yasiyojibika:   {unresolved_count}")
print(f"  📊 Analytics (jumla):      {analytics_count + history_count}")
print("="*55)
print("\nDashboard iko tayari kwa presentation! 🚀")
print("Fungua: http://localhost:8000/dashboard/")
print("Login:  admin / Mkulima@2024")