"""
Kiwango cha USD -> TZS kinachojisasisha
=======================================

Chanzo: ExchangeRate-API, endpoint ya wazi (bila API key):
    https://open.er-api.com/v6/latest/USD
Inasasishwa mara moja kwa siku. Masharti yao yanaruhusu kuhifadhi
kiwango na kukitumia kibiashara, lakini yanahitaji kuwataja
(attribution) — ndiyo sababu ukurasa wa malipo una link yao.

Mpangilio wa kupata kiwango:
  1. Kiwango kilichohifadhiwa ni cha chini ya saa 12  -> kinatumika
  2. Kimepitwa                                       -> kinachukuliwa upya
  3. Huduma haipatikani                              -> kiwango cha mwisho
                                                        kilichopatikana
  4. Hakuna kilichowahi kupatikana                   -> settings.USD_TZS_RATE

Hivyo ukurasa hauwezi kuvunjika hata huduma ya nje ikizimika, na
tunaiita mara chache (kwa heshima ya kikomo chao cha matumizi).
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

FX_URL = 'https://open.er-api.com/v6/latest/USD'
FX_ATTRIBUTION_URL = 'https://www.exchangerate-api.com'
REFRESH_AFTER = timedelta(hours=12)
REQUEST_TIMEOUT = 4

# Kinga dhidi ya takwimu mbovu: kiwango nje ya kipimo hiki kinakataliwa
MIN_SANE, MAX_SANE = 1000, 10000


def _fetch_live_rate():
    """Rudisha kiwango cha TZS kwa dola moja, au None kikishindikana."""
    import requests
    try:
        resp = requests.get(FX_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get('result') != 'success':
            return None
        rate = float(data['rates']['TZS'])
        if not (MIN_SANE < rate < MAX_SANE):
            logger.warning(f"[FX] Kiwango kisicho cha kawaida kimekataliwa: {rate}")
            return None
        return rate
    except Exception as e:
        logger.warning(f"[FX] Imeshindikana kupata kiwango: {e}")
        return None


def get_usd_tzs_rate(sub):
    """
    Rudisha dict:
      rate     — TZS kwa USD 1
      updated  — lini kiwango kilipatikana (datetime au None)
      status   — 'live' | 'stale' | 'fallback'
    """
    now = timezone.now()

    # 1. Kiwango kilichohifadhiwa bado ni kipya
    if sub.fx_rate and sub.fx_rate_updated and now - sub.fx_rate_updated < REFRESH_AFTER:
        return {'rate': float(sub.fx_rate), 'updated': sub.fx_rate_updated, 'status': 'live'}

    # 2. Chukua upya
    live = _fetch_live_rate()
    if live:
        sub.fx_rate = round(live, 2)
        sub.fx_rate_updated = now
        sub.save(update_fields=['fx_rate', 'fx_rate_updated'])
        return {'rate': live, 'updated': now, 'status': 'live'}

    # 3. Kiwango cha mwisho kilichopatikana
    if sub.fx_rate:
        return {'rate': float(sub.fx_rate), 'updated': sub.fx_rate_updated, 'status': 'stale'}

    # 4. Hakuna kilichowahi kupatikana
    return {
        'rate': float(getattr(settings, 'USD_TZS_RATE', 2650)),
        'updated': None,
        'status': 'fallback',
    }
