"""
Groq AI Integration — Kilimoni AI
Inatumika kwa maswali ambayo templates hazijashughulikia.
AI inapewa muktadha kutoka DATASET (crop profiles, templates, mbegu)
ili majibu yawe sahihi na yaendane na maarifa ya mfumo.

Inatumia REST API moja kwa moja (requests) — hakuna groq library
inayohitajika, kwa hiyo hakuna version conflicts.
"""
import logging
import requests as http_requests

from django.conf import settings

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


# ═══════════════════════════════════════════════════════
# DATASET CONTEXT BUILDER
# Kusanya maarifa yanayohusiana na swali kutoka database
# ═══════════════════════════════════════════════════════
def build_dataset_context(crop, intent, zone) -> str:
    """
    Chota taarifa za dataset zinazohusiana na swali:
    - Crop profile (kanuni za kilimo za zao husika)
    - Answer templates zinazokaribiana
    - Mbegu zilizothibitishwa
    AI itatumia hizi kama chanzo cha ukweli (source of truth).
    """
    from crops.models import CropProfile, SeedVariety, AnswerTemplate

    parts = []

    if crop:
        # Crop profile — general au ya zone husika
        profile = None
        if zone:
            profile = CropProfile.objects.filter(crop=crop, zone=zone).first()
        if not profile:
            profile = CropProfile.objects.filter(crop=crop).first()

        if profile:
            fields = [
                ('Wakati wa kupanda', profile.planting_window_simple),
                ('Nafasi ya kupanda', profile.spacing),
                ('Mbolea ya kupandia', profile.fertilizer_planting),
                ('Mbolea ya kukuzia', profile.fertilizer_top_dressing),
                ('Wadudu wa kawaida', profile.common_pests),
                ('Magonjwa ya kawaida', profile.common_diseases),
                ('Dalili za kawaida', profile.common_symptoms),
                ('Wakati wa kuvuna', profile.harvest_window),
                ('Uhifadhi', profile.storage_notes),
                ('Masoko', profile.market_notes),
            ]
            profile_text = '\n'.join(
                f"- {label}: {value}" for label, value in fields if value
            )
            if profile_text:
                parts.append(
                    f"TAARIFA ZA ZAO ({crop.crop_name_sw}"
                    + (f", zone: {zone.zone_name}" if zone else "")
                    + f"):\n{profile_text}"
                )

        # Mbegu zilizothibitishwa
        varieties = SeedVariety.objects.filter(
            crop=crop, verification_status='verified'
        )
        if zone:
            zone_varieties = varieties.filter(recommended_zone=zone)
            if zone_varieties.exists():
                varieties = zone_varieties
        if varieties.exists():
            names = ', '.join(v.variety_name for v in varieties[:6])
            parts.append(f"MBEGU ZILIZOTHIBITISHWA: {names}")

        # Templates chache zinazohusiana (kama zipo)
        templates = AnswerTemplate.objects.filter(
            crop=crop, active_status='active'
        )
        if intent:
            intent_templates = templates.filter(intent=intent)
            if intent_templates.exists():
                templates = intent_templates
        for t in templates[:2]:
            parts.append(f"MAARIFA YA ZIADA:\n{t.answer_text_sw[:500]}")

    return '\n\n'.join(parts) if parts else ''


# ═══════════════════════════════════════════════════════
# GROQ RESPONSE
# ═══════════════════════════════════════════════════════
SYSTEM_PROMPT = """Wewe ni *Kilimoni AI* — msaidizi wa kilimo wa WhatsApp kwa wakulima wa Tanzania. Unafanya kazi kama Afisa Ugani wa kidijitali.

KAZI YAKO:
- Toa ushauri wa kilimo kwa Kiswahili rahisi, sahihi na wa vitendo
- Jibu kulingana na mazingira ya Tanzania (hali ya hewa, udongo, masoko ya ndani)
- Kama umepewa TAARIFA ZA DATASET hapo chini, ZITUMIE kama chanzo chako kikuu cha ukweli — usizipingane
- Kama swali si la kilimo kabisa, lielekeze kwa upole kwenye mada za kilimo bila kumkwaza mteja

MUUNDO WA WHATSAPP (fuata kikamilifu — huu ndio mtindo rasmi wa Kilimoni AI):
1. ANZA moja kwa moja na jibu. USITUMIE mistari ya mapambo (━━━)
   wala vichwa vya herufi kubwa. Andika kama unavyomjibu mtu kwenye WhatsApp.
2. Kama swali ni la zao mahususi, unaweza kuanza na mstari mfupi:
   🌾 *Mahindi* — Singida
   Kisha mstari mtupu, kisha jibu.
3. Aya FUPI za mistari 1-2, zikitenganishwa na mstari mtupu
4. Orodha zitumie alama • kila moja mstari wake
5. *bold* — kwa majina ya mbegu, vipimo, na tarehe muhimu tu
6. Emoji zisizidi 2 kwenye jibu zima
7. Tahadhari iwe mstari wake: ⚠️ ...
8. Mwisho (hiari): swali MOJA fupi la kufuatilia kwa italic
9. Jibu zima lisizidi mistari 12

KANUNI:
0. MAZUNGUMZO: Umepewa historia ya mazungumzo hapo juu. ITUMIE.
   - Mkulima akijibu kwa neno moja ("ndio", "mahindi", "Singida",
     "hilo la pili"), rejea ulichokiuliza wewe na uendelee. USIANZE UPYA.
   - Usimuulize tena kitu alichokwisha kukujibu.
   - Ukibadilisha mada, ionyeshe kwa mstari mfupi wa kuunganisha.
1. LAZIMA Kiswahili cha kawaida — kama afisa ugani anavyoongea na mkulima
   kijijini. Si Kiswahili cha vitabu, si cha kikompyuta.
2. Usiseme "Kama AI..." au kutaja kuwa wewe ni mfumo/model
3. USISEME kamwe kuwa hujaelewa, huna taarifa, au mfumo una upungufu — badala yake toa ushauri bora unaowezekana, na kama unahitaji taarifa zaidi uliza swali moja mahususi kwa staha
4. Dawa/kemikali: taja jina ukishauri, lakini ongeza "fuata maelekezo ya kifungashio au uliza duka la pembejeo"
5. Bei za soko: sema zinabadilika kulingana na msimu na eneo — usibuni namba kamili
6. Maswali makubwa ya kitaalamu (mfano ugonjwa usiotambulika): shauri pia kuonana na Afisa Ugani wa eneo lake

TANZANIA AGRO-ZONES:
- Central (Singida, Dodoma, Tabora): ukame, mahindi ya mapema, mtama, alizeti
- Lake (Mwanza, Kagera, Geita, Mara): mvua bimodal, mahindi, pamba, mihogo
- Northern (Arusha, Kilimanjaro, Manyara): kahawa, mahindi, ndizi, ngano
- Southern Highlands (Mbeya, Iringa, Njombe, Songwe): chai, mahindi, viazi, ngano
- Eastern (Morogoro, Pwani, DSM, Tanga): mpunga, korosho, mahindi
- Western (Kigoma, Katavi, Rukwa): tumbaku, mahindi, mihogo, mpunga"""


def build_history_messages(user, limit: int = 8) -> list:
    """
    Chukua mazungumzo ya karibuni ya mkulima huyu na yageuze kuwa
    ujumbe wa chat (user/assistant) ambao Groq anaelewa.

    Hii ndiyo inayomwezesha AI kuelewa majibu mafupi kama
    "ndio", "sawa", "mahindi" — kwa sababu anaona alichoulizwa.
    """
    from bot.models import Conversation

    try:
        rows = list(
            Conversation.objects
            .filter(user=user)
            .order_by('-created_at')[:limit]
        )
    except Exception as e:
        logger.error(f"History error: {e}")
        return []

    rows.reverse()  # kutoka ya zamani hadi ya karibuni
    messages = []
    for row in rows:
        text = (row.raw_message or '').strip()
        if not text:
            continue
        role = 'user' if row.message_direction == 'inbound' else 'assistant'
        messages.append({'role': role, 'content': text[:1200]})
    return messages


def get_groq_response(user_message: str, crop=None, intent=None,
                      location: str = '', zone=None, user=None) -> str:
    """
    Tuma swali kwa Groq AI pamoja na muktadha wa dataset na historia
    ya mazungumzo.
    Inarudisha '' kama imeshindwa (engine itatumia fallback).
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        logger.warning("GROQ_API_KEY haijawekwa — AI fallback hairudiwi")
        return ''

    # Muktadha wa mkulima
    context_parts = []
    if crop:
        context_parts.append(f"Zao: {crop.crop_name_sw}")
    if location:
        context_parts.append(f"Eneo: {location}")
    if zone:
        context_parts.append(f"Agro-ecological zone: {zone.zone_name}")
    farmer_context = '\n'.join(context_parts) if context_parts else 'Hakuna taarifa za ziada'

    # Muktadha wa dataset
    try:
        dataset_context = build_dataset_context(crop, intent, zone)
    except Exception as e:
        logger.error(f"Dataset context error: {e}")
        dataset_context = ''

    user_prompt = f"""Taarifa za mkulima:
{farmer_context}
"""
    if dataset_context:
        user_prompt += f"""
TAARIFA ZA DATASET (chanzo chako kikuu cha ukweli):
{dataset_context}
"""
    user_prompt += f"""
Swali la mkulima:
"{user_message}"

Toa jibu la ushauri wa kilimo kwa Kiswahili, ukifuata muundo wa WhatsApp:"""

    # Historia ya mazungumzo — inampa AI kumbukumbu ya kile
    # alichokiuliza mkulima na kile mfumo ulichojibu.
    history = build_history_messages(user) if user is not None else []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    try:
        resp = http_requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                "max_tokens": 600,
                "temperature": 0.4,
                "messages": messages,
            },
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data['choices'][0]['message']['content'].strip()
        logger.info(f"[Groq] Jibu limetolewa kwa: {user_message[:50]}")
        return answer
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return ''