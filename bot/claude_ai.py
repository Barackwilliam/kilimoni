"""
Claude AI Integration — Mkulima AI Tanzania
Inatumika kwa maswali ambayo templates hazijashughulikia
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def get_claude_response(user_message: str, crop_name: str = '', location: str = '', zone_name: str = '', context: str = '') -> str:
    """
    Tumia Claude AI kutoa jibu kwa maswali ngumu ambayo template haijajibu.
    Claude anafanya kazi kama Afisa Ugani wa digital — anatoa ushauri wa kilimo
    kwa Kiswahili rahisi, kulingana na mazingira ya Tanzania.
    """
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY haijawekwa — Claude AI hairudiwa")
        return ''

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Build context string
        context_parts = []
        if crop_name:
            context_parts.append(f"Zao: {crop_name}")
        if location:
            context_parts.append(f"Eneo: {location}")
        if zone_name:
            context_parts.append(f"Agro-ecological zone: {zone_name}")
        if context:
            context_parts.append(f"Mazingira zaidi: {context}")

        context_str = '\n'.join(context_parts) if context_parts else 'Hakuna taarifa za ziada'

        system_prompt = """Wewe ni Msaidizi wa Kilimo wa Mkulima AI Tanzania — bot ya WhatsApp inayosaidia wakulima wa Tanzania kupitia WhatsApp.

KAZI YAKO:
- Toa ushauri wa kilimo kwa Kiswahili rahisi na kueleweka
- Jibu kulingana na mazingira ya Tanzania (hali ya hewa, aina za udongo, masoko ya ndani)
- Tumia lugha ya kawaida ya mkulima wa Tanzania, si lugha ya kitaaluma sana
- Jibu liwe fupi na la moja kwa moja — hii ni WhatsApp, si kitabu

KANUNI MUHIMU:
1. Jibu LAZIMA liwe kwa Kiswahili
2. Jibu liwe fupi (mistari 5-12 ya WhatsApp)
3. Toa ushauri wa vitendo, si nadharia tu
4. Kama swali linahitaji Afisa Ugani, sema hivyo
5. Tumia emoji kidogo kwa urafiki (🌱🌽💧🐛 n.k.)
6. Mwisho wa jibu, weka mstari: "─────────────────"
7. Kisha: "🤖 Mkulima AI Tanzania"
8. Kisha: "💬 Piga nambari *0* kupata msaada zaidi"

USISEME:
- Usiseme "Kama AI..." au "Kama msaidizi wa AI..."
- Usitoe dawa au kemikali bila kusema "wasiliana na duka la pembejeo lako"
- Usibuni bei za soko — sema bei zinaweza kutofautiana
- Usijibu maswali yasiyohusiana na kilimo au chakula

Tanzania agricultural zones na mazao makuu:
- Central Zone (Singida, Dodoma): Ukame, mahindi ya mapema, mtama, alizeti
- Lake Zone (Mwanza, Kagera, Geita): Mvua bimodal, mahindi, pamba, mihogo  
- Northern Zone (Arusha, Kilimanjaro): Kahawa, mahindi, ndizi, ngano
- Southern Highlands (Mbeya, Iringa, Njombe): Chai, mahindi, viazi, ngano
- Eastern Zone (Morogoro, Pwani, DSM): Mpunga, korosho, mahindi
- Western Zone (Tabora, Kigoma): Tumbaku, mahindi, mihogo"""

        user_prompt = f"""Taarifa za Mkulima:
{context_str}

Swali la Mkulima:
"{user_message}"

Toa jibu la ushauri wa kilimo kwa Kiswahili:"""

        message = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response = message.content[0].text.strip()
        logger.info(f"Claude AI alitoa jibu kwa: {user_message[:50]}")
        return response

    except Exception as e:
        logger.error(f"Claude AI error: {e}")
        return ''
