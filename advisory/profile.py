"""
Profile ya shamba la mkulima + kuunganisha moduli (Hatua 6)
===========================================================

Bot inakumbuka kile mkulima alichokwisha sema — eneo (User.ward/aez_code),
zao (User.last_crop_id) na udongo (User.soil_code) — na moduli zote za
ushauri zinakitumia bila kumuuliza tena:

  • Mbegu   → inaongeza ufaafu wa zao kwa udongo wake (MHD-004)
  • Udongo  → "udongo wangu unafaa mpunga?" inajibiwa kwa udongo uliokumbukwa
  • Mzunguko→ kanuni za udongo (SOILROT-*) kwa udongo uliokumbukwa

AI router: ujumbe usio na neno la moduli yoyote, AI inauchagulia moduli
kutoka orodha funge (au "nyingine" → mtiririko wa kawaida).
"""
from diagnosis import plain

from .models import SoilSuitability, SoilType

MODULES = {
    'diagnosis': 'mazao/mmea una tatizo, ugonjwa, wadudu au dalili (majani, shina, kukauka, mashimo)',
    'seed': 'anataka kuchagua mbegu au aina ya mbegu, au anauliza kama mbegu fulani inafaa',
    'planting': 'anauliza wakati au mwezi wa kupanda, au kama apande sasa kulingana na mvua',
    'soil': 'anauliza kuhusu udongo wake, rutuba, au kama udongo unafaa zao',
    'rotation': 'anauliza zao gani lifuate baada ya zao jingine, au mzunguko wa mazao',
    'other': 'jambo jingine (mbolea, bei, kuvuna, salamu, au swali lisilo la kilimo)',
}


def profile_soil(user):
    if not user or not getattr(user, 'soil_code', ''):
        return None
    return SoilType.objects.filter(source_id=user.soil_code, is_active=True).first()


def remember_soil(user, soil):
    if user is not None and soil is not None and user.soil_code != soil.source_id:
        user.soil_code = soil.source_id
        user.save(update_fields=['soil_code'])


def soil_in_text(text, state=None):
    """Udongo uliotajwa kwenye ujumbe huu (si wa profile)."""
    from . import soil as soil_mod
    return soil_mod.identify(text, state) if soil_mod.wants_soil(text) else None


def soil_note(soil, crop):
    """Mistari ya ufaafu wa zao kwa udongo wa mkulima (kwa majibu ya moduli nyingine)."""
    if not soil or not crop:
        return [], []
    s = SoilSuitability.objects.filter(soil=soil, crop=crop, is_active=True).first()
    if not s or s.score is None:
        return [], []
    lines = [f"🟤 *Udongo wako ({soil.name_sw}):* ufaafu wa {crop.crop_name_sw} ni {s.rating} ({s.score}/100)."]
    if s.score < 85 and s.improvements_sw:
        lines.append(f"   Kabla ya kupanda: {plain.clean(s.improvements_sw)[0].rstrip('.')}.")
    return lines, [s.source_id]


def route(text, state=None):
    """Moduli ya ushauri kwa maana ya ujumbe (AI, orodha funge). None = shughulikia kawaida."""
    from diagnosis import ai_layer
    code = ai_layer.match_option(text, MODULES, state, step='router')
    return code if code and code != 'other' else None
