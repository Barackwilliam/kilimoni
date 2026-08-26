"""
seed_demo_data.py — Demo Data ya Dashboard kwa Presentation
Run: python scripts/seed_demo_data.py
Kwanza lazima seed_data.py iwe imekwisha run.
"""
import os, sys, random, django
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mkulima_ai.settings')
django.setup()

from django.utils import timezone
from bot.models import User, Conversation, UnresolvedQuery
from crops.models import Crop, Intent, Zone, Region, District, Ward
from analytics.models import AnalyticsLog

print("⏳ Kuongeza demo data ya dashboard...")

# Helper — pata Region/District objects salama
def get_region(name):
    return Region.objects.filter(name__iexact=name).first()

def get_district(name, region_name):
    region = get_region(region_name)
    if not region:
        return None
    # Try exact match first
    d = District.objects.filter(name__iexact=name, region=region).first()
    if d:
        return d
    # Try partial match
    return District.objects.filter(name__icontains=name.split()[0], region=region).first()

# ── Wakulima wa Demo ──────────────────────────────────────
wakulima_info = [
    ("255712345678", "Singida",     "Singida Urban"),
    ("255767891234", "Dodoma",      "Chamwino"),
    ("255754321098", "Mwanza",      "Ilemela"),
    ("255789012345", "Mbeya",       "Mbeya Urban"),
    ("255723456789", "Arusha",      "Arusha Urban"),
    ("255745678901", "Morogoro",    "Kilosa"),
    ("255698765432", "Kagera",      "Bukoba Rural"),
    ("255711223344", "Iringa",      "Kilolo"),
    ("255733445566", "Tabora",      "Urambo"),
    ("255722334455", "Kilimanjaro", "Moshi Rural"),
    ("255744556677", "Shinyanga",   "Shinyanga Urban"),
    ("255755667788", "Njombe",      "Njombe Urban"),
]

wakulima = []
for phone, region_name, district_name in wakulima_info:
    region_obj = get_region(region_name)
    district_obj = get_district(district_name, region_name)

    user, _ = User.objects.get_or_create(
        phone_number=phone,
        defaults={
            "region": region_obj,
            "district": district_obj,
            "location_text": district_name + ", " + region_name,
            "preferred_language": "sw",
            "message_count": random.randint(3, 28),
            "active_status": "active",
        }
    )
    wakulima.append(user)

print(f"  ✅ Wakulima: {len(wakulima)}")

# ── Models ────────────────────────────────────────────────
mahindi  = Crop.objects.filter(crop_name_sw="Mahindi").first()
maharage = Crop.objects.filter(crop_name_sw="Maharage").first()
mpunga   = Crop.objects.filter(crop_name_sw="Mpunga").first()
intents  = {i.intent_name: i for i in Intent.objects.all()}
zones    = {z.zone_name: z for z in Zone.objects.all()}

def zone_for(region_name):
    mapping = {
        "Singida": "Central Zone", "Dodoma": "Central Zone",
        "Mwanza": "Lake Zone", "Kagera": "Lake Zone", "Mara": "Lake Zone",
        "Mbeya": "Southern Highlands", "Iringa": "Southern Highlands",
        "Njombe": "Southern Highlands",
        "Arusha": "Northern Zone", "Kilimanjaro": "Northern Zone",
        "Morogoro": "Morogoro Corridor",
        "Tabora": "Western Zone", "Kigoma": "Western Zone",
        "Shinyanga": "Lake Zone",
    }
    return zones.get(mapping.get(region_name, ""), None)

# ── Mazungumzo ────────────────────────────────────────────
mazungumzo = [
    (wakulima[0],  mahindi,  "variety_by_location", "Singida", [
        ("Ni mbegu gani ya mahindi nipande Singida?",
         "🌽 MAHINDI | 📍 Singida\n\nKwa Singida (Central Zone), mbegu zinazostahimili ukame:\n• PAN 23 (siku 85-95) — ukame: Juu\n• SC 403 (siku 90-100) — ukame: Juu\n• DK 8051 (siku 95-110) — ukame: Wastani\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
        ("Mbolea gani ya kupandia mahindi?",
         "🌽 MAHINDI\n\nDAP gramu 50-70 kwa shimo au CAN gramu 60-80. Weka upande wa mbegu.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
        ("Asante sana", "Karibu! 🌱 Piga *0* ukihitaji msaada."),
    ]),
    (wakulima[1], mahindi, "planting_time", "Dodoma", [
        ("Mahindi yapandwe lini Dodoma?",
         "📅 Dodoma (Central Zone): Panda Novemba–Desemba baada ya mvua ya kwanza mm 20+.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
        ("Mvua bado haijanyesha nisubiri?",
         "Ndiyo, subiri mvua ya kwanza thabiti (siku 2-3 mfululizo). Mbegu ziwe tayari mapema!\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[2], mahindi, "pest_identification", "Mwanza", [
        ("Mahindi yangu yana viwavi wakubwa wanakula majani usiku",
         "🐛 Hii ni Fall Armyworm!\nDawa: Emamectin Benzoate au Spinosad.\nPiga asubuhi au jioni.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
        ("Ninapiga dawa lakini bado wako",
         "Piga ndani ya mmea (funnel). Rudia baada ya siku 7-10. Hakikisha dawa haijapitwa na muda.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[3], mahindi, "harvest_time", "Mbeya", [
        ("Mahindi yangu Mbeya yako tayari kuvuna?",
         "🌽 Angalia: Maganda ya kahawia ✓, nywele zimekauka ✓, punje ngumu ✓ = Tayari kuvuna!\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
        ("Jinsi ya kuhifadhi baada ya kuvuna?",
         "1. Kausha hadi 13.5% 2. Tumia magunia ya PICS 3. Ghala safi na baridi 4. Lindo la panya\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[4], mahindi, "seed_selection", "Arusha", [
        ("Napenda mbegu ya mahindi inayotoa mavuno mengi Arusha",
         "🌽 Arusha (Northern Zone): TMV 1 (TARI) inafanya vizuri. Stahimili magonjwa, mavuno mazuri.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[5], mahindi, "disease_identification", "Morogoro", [
        ("Mahindi yangu yana madoa ya kijivu kwenye majani",
         "🦠 Hii inaweza kuwa Gray Leaf Spot.\nDawa: Mancozeb au Propiconazole. Roteshea mazao msimu ujao.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[6], mahindi, "market_question", "Kagera", [
        ("Bei ya mahindi Kagera ni ngapi sasa?",
         "💰 Bei Kagera (2024): TZS 400-650/kg.\nWakati bora kuuza: Agosti-Novemba.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[7], mahindi, "fertilizer_top_dressing", "Iringa", [
        ("Wakati wa mbolea ya juu kwa mahindi Iringa?",
         "🧪 Wiki 5-7 baada ya kupanda, mahindi yakiwa 30-50cm. Urea gramu 50-70 kwa mmea.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[8], maharage, "seed_selection", "Tabora", [
        ("Mbegu za maharage zipi zinafaa Tabora?",
         "🫘 Tabora (Western Zone): Lyamungu 85, SUA 90. Wasiliana na TARI Tumbi Tabora.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
    (wakulima[9], mpunga, "planting_time", "Kilimanjaro", [
        ("Mpunga upandwe lini Kilimanjaro?",
         "🌾 Kilimanjaro: Masika (Machi-Aprili) na Vuli (Oktoba-Novemba). Nafasi: 20x20cm.\n\n─────────────────\n🤖 Kilimoni AI Tanzania"),
    ]),
]

conv_count = 0
analytics_count = 0

for user, crop, intent_key, location, pairs in mazungumzo:
    intent = intents.get(intent_key)
    region_name = location
    zone_obj = zone_for(region_name)
    region_obj = get_region(region_name)
    base_time = timezone.now() - timedelta(days=random.randint(1, 20))

    for i, (swali, jibu) in enumerate(pairs):
        t = base_time + timedelta(minutes=i * random.randint(2, 8))

        Conversation.objects.get_or_create(
            user=user, raw_message=swali, message_direction='inbound',
            defaults={
                'message_type': 'text',
                'normalized_text': swali.lower(),
                'detected_crop': crop,
                'detected_intent': intent,
                'detected_location_text': location,
                'detected_zone': zone_obj,
                'detected_region': region_obj,
                'answer_source': 'template',
                'dataset_used': 'TARI Seed Data 2024',
                'reasoning_trace': f'Source: template | Region: {region_name} | Zone: {zone_obj} | Crop: {crop} | Intent: {intent_key}',
                'created_at': t,
            }
        )
        Conversation.objects.get_or_create(
            user=user, raw_message=jibu, message_direction='outbound',
            defaults={
                'message_type': 'text',
                'detected_crop': crop,
                'detected_intent': intent,
                'detected_location_text': location,
                'detected_zone': zone_obj,
                'detected_region': region_obj,
                'answer_source': 'template',
                'created_at': t + timedelta(seconds=random.randint(2, 6)),
            }
        )
        conv_count += 2

        AnalyticsLog.objects.create(
            user_id=user.id, phone_number=user.phone_number,
            crop=crop, intent=intent, zone=zone_obj,
            success_flag=True,
            response_time_ms=random.randint(180, 1200),
            created_at=t,
        )
        analytics_count += 1

print(f"  ✅ Mazungumzo: {conv_count}")
print(f"  ✅ Analytics: {analytics_count}")

# ── Maswali Yasiyoshughulikiwa ─────────────────────────────
unresolved_data = [
    (wakulima[0],  mahindi,  "Bei ya mbolea DAP imeongezeka sana, kuna bei mpya?", "no_answer", "pending", ""),
    (wakulima[2],  mahindi,  "Ninaweza kupata mkopo wa pembejeo wapi Mwanza?", "no_intent", "pending", ""),
    (wakulima[4],  None,     "Hali ya hewa Arusha itakuwa vipi wiki ijayo?", "no_intent", "pending", ""),
    (wakulima[5],  mahindi,  "Mahindi yangu yana rangi ya zambarau kwenye majani", "no_answer", "pending", ""),
    (wakulima[7],  maharage, "Maharage yamebadilika rangi na kudondoka kabla ya wakati", "no_answer", "resolved", "Inaweza kuwa Anthracnose — fungicide ya Copper inasaidia."),
    (wakulima[9],  mpunga,   "Mpunga wangu unasimama polepole sana, nitumie nini?", "no_answer", "pending", ""),
    (wakulima[10], mahindi,  "Nondo wa shina waharibu zaidi ya nusu ya shamba Shinyanga", "no_answer", "pending", ""),
    (wakulima[11], mahindi,  "Baridi Njombe inasababisha mahindi yangu kudumaa", "no_answer", "pending", ""),
]

u_count = 0
for user, crop, msg, reason, status, notes in unresolved_data:
    obj, created = UnresolvedQuery.objects.get_or_create(
        user=user, raw_message=msg,
        defaults={
            'detected_crop': crop,
            'reason': reason,
            'status': status,
            'resolution_notes': notes,
            'created_at': timezone.now() - timedelta(days=random.randint(1, 14)),
        }
    )
    if created:
        u_count += 1

print(f"  ✅ Maswali Yasiyoshughulikiwa: {u_count}")

# ── Analytics history — siku 21 ───────────────────────────
zone_list   = list(zones.values())
intent_list = list(intents.values())
crop_list   = [c for c in [mahindi, maharage, mpunga] if c]

h_count = 0
for days_back in range(1, 22):
    for _ in range(random.randint(8, 35)):
        user = random.choice(wakulima)
        AnalyticsLog.objects.create(
            user_id=user.id,
            phone_number=user.phone_number,
            crop=random.choice(crop_list),
            intent=random.choice(intent_list),
            zone=random.choice(zone_list),
            success_flag=random.choices([True, False], weights=[85, 15])[0],
            response_time_ms=random.randint(150, 2000),
            created_at=timezone.now() - timedelta(
                days=days_back,
                hours=random.randint(6, 22),
                minutes=random.randint(0, 59)
            ),
        )
        h_count += 1

print(f"  ✅ Analytics history (siku 21): {h_count} logs")

print()
print("="*50)
print("✅ DEMO DATA IMEKAMILIKA!")
print("="*50)
print(f"  👥 Wakulima:            {len(wakulima)}")
print(f"  💬 Mazungumzo:          {conv_count}")
print(f"  ❓ Yasiyoshughulikiwa:  {u_count}")
print(f"  📊 Analytics (jumla):   {analytics_count + h_count}")
print()
print("Dashboard: http://localhost:8000/dashboard/")
print("Login: admin / Mkulima@2024")
