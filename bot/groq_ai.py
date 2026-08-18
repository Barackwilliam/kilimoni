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
1. ANZA na mstari wa kichwa: emoji moja inayohusiana + *MADA FUPI KWA HERUFI KUBWA*
   Mstari unaofuata uwe: ━━━━━━━━━━━━━━━
   Mfano:
   🌾 *KUPANDA MAHINDI — SINGIDA*
   ━━━━━━━━━━━━━━━
2. Kisha mwili wa jibu: aya FUPI za mistari 1-2, zikitenganishwa na mstari mtupu
3. Orodha zitumie alama • (nukta nene), kila moja mstari wake
4. *bold* — tumia KWA MAKUSUDI tu: majina ya mbegu, vipimo vya mbolea, vipindi/tarehe muhimu, na maneno ya tahadhari
5. _italic_ — kwa mifano ya sentensi tu
6. Emoji: kichwa 1 + ndani ya jibu zisizidi 2 (ziwe na maana: ⚠️ kwa tahadhari, 💡 kwa dokezo)
7. Kama kuna tahadhari, iwe mstari wake: ⚠️ *Tahadhari:* ...
8. Mwisho (hiari): swali MOJA fupi la kufuatilia kwa italic — bila footer, bila sahihi, bila jina lako
9. Jibu zima lisizidi mistari 14 ya WhatsApp

KANUNI:
1. LAZIMA Kiswahili
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


def get_groq_response(user_message: str, crop=None, intent=None,
                      location: str = '', zone=None) -> str:
    """
    Tuma swali kwa Groq AI pamoja na muktadha wa dataset.
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

    try:
        resp = http_requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
                "max_tokens": 600,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
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