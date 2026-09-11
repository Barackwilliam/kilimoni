"""
JamiiTek Website Status Middleware
====================================
Middleware hii inafaa kusakinishwa kwenye websites za wateja wa JamiiTek
ambazo zimeandikwa kwa Django.

JINSI YA KUTUMIA:
1. Sakinisha kwenye settings.py ya website ya mteja:

    JAMIITEK_API_KEY = "api-key-yako-hapa"
    JAMIITEK_API_URL = "https://jamiitek.com/api/site-status/"
    
    MIDDLEWARE = [
        ...
        'jamiitek_middleware.JamiiTekStatusMiddleware',
    ]

2. Nakili faili hii kwenye root directory ya project ya mteja
   na uiite `jamiitek_middleware.py`

NOTES:
- Middleware inafanya API call mara moja kwa dakika 5 (cache)
- Ikiwa API haifikiwi, website inaendelea kufanya kazi (fail-open)
- Features zilizozimwa zinaweza kuangaliwa kwa: request.jamiitek_features
"""

import requests
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache

logger = logging.getLogger(__name__)

SUSPENSION_HTML = """
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Huduma Imesimamishwa</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ 
    display:flex; align-items:center; justify-content:center; 
    min-height:100vh; background:#f8fafc; font-family:Arial,sans-serif; 
  }}
  .container {{ 
    text-align:center; background:white; padding:60px 50px; 
    border-radius:16px; box-shadow:0 4px 30px rgba(0,0,0,0.1); 
    max-width:500px; margin:20px;
  }}
  .icon {{ font-size:70px; margin-bottom:20px; }}
  h1 {{ color:#dc2626; margin-bottom:15px; font-size:26px; }}
  p {{ color:#6b7280; line-height:1.7; font-size:15px; }}
  .footer {{ margin-top:35px; color:#d1d5db; font-size:12px; }}
</style>
</head>
<body>
<div class="container">
  <div class="icon">🔒</div>
  <h1>Huduma Imesimamishwa</h1>
  <p>{message}</p>
  <div class="footer">Powered by JamiiTek</div>
</div>
</body>
</html>
"""

MAINTENANCE_HTML = """
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Matengenezo - Tutarudi Hivi Karibuni</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ 
    display:flex; align-items:center; justify-content:center; 
    min-height:100vh; background:#fffbeb; font-family:Arial,sans-serif; 
  }}
  .container {{ 
    text-align:center; background:white; padding:60px 50px; 
    border-radius:16px; box-shadow:0 4px 30px rgba(0,0,0,0.08); 
    max-width:500px; margin:20px;
  }}
  .icon {{ font-size:70px; margin-bottom:20px; }}
  h1 {{ color:#d97706; margin-bottom:15px; font-size:26px; }}
  p {{ color:#6b7280; line-height:1.7; font-size:15px; }}
  .footer {{ margin-top:35px; color:#d1d5db; font-size:12px; }}
</style>
</head>
<body>
<div class="container">
  <div class="icon">🔧</div>
  <h1>Matengenezo ya Website</h1>
  <p>{message}</p>
  <div class="footer">Powered by JamiiTek</div>
</div>
</body>
</html>
"""


class JamiiTekStatusMiddleware:
    """
    Django Middleware ya kuangalia hali ya website kutoka JamiiTek Panel.
    """
    
    CACHE_KEY = 'jamiitek_site_status'
    CACHE_TIMEOUT = 300  # Sekunde 300 = dakika 5
    # /webhook/ — bot inashughulikiwa yenyewe (JSON, si HTML)
    # /dashboard/malipo/ — mteja lazima aweze kuona deni na jinsi ya kulipa
    BYPASS_PATHS = ['/admin/', '/api/', '/static/', '/media/',
                    '/dashboard/malipo/', '/dashboard/login/', '/dashboard/logout/']

    # Njia za bot: hapa hatutoi HTML — tunarudisha jibu la Kiswahili
    # kwa mkulima, kisha bridge inalituma WhatsApp.
    BOT_PATHS = ['/webhook/']

    BOT_SUSPENDED_MESSAGE = (
        "🔒 *Huduma imesitishwa kwa muda*\n\n"
        "Samahani, huduma ya Kilimoni AI haipatikani kwa sasa.\n\n"
        "Tafadhali wasiliana na msimamizi wa huduma.\n\n"
        "_Tunaomba radhi kwa usumbufu._"
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.api_key = getattr(settings, 'JAMIITEK_API_KEY', None)
        self.api_url = getattr(settings, 'JAMIITEK_API_URL', 'https://jamiitek.com/api/site-status/')

    def __call__(self, request):
        # Ruka admin na static files
        for path in self.BYPASS_PATHS:
            if request.path.startswith(path):
                return self.get_response(request)

        if not self.api_key and not getattr(settings, 'JAMIITEK_FORCE_STATUS', ''):
            return self.get_response(request)

        status_data = self._get_status()
        
        if status_data:
            # Hifadhi features kwenye request
            request.jamiitek_features = status_data.get('features', {})
            request.jamiitek_status = status_data.get('status', 'active')

            site_status = status_data.get('status', 'active')
            message = status_data.get('suspension_message', 'Huduma imesimamishwa kwa muda.')

            if site_status in ('suspended', 'maintenance'):

                # Bot: mkulima apate ujumbe wa Kiswahili, si ukurasa wa HTML.
                # Bila hii, bridge ingepokea HTML na mkulima asingepata kitu.
                if any(request.path.startswith(p) for p in self.BOT_PATHS):
                    return JsonResponse({
                        'status': 'service_suspended',
                        'reply': self.BOT_SUSPENDED_MESSAGE,
                    }, status=200)

                if site_status == 'suspended':
                    html = SUSPENSION_HTML.format(message=message)
                else:
                    html = MAINTENANCE_HTML.format(message=message)
                return HttpResponse(html, status=503, content_type='text/html')

        return self.get_response(request)

    def _get_status(self):
        """Angalia hali ya website (na cache kwa dakika 5)"""

        # Swichi ya MAJARIBIO — inapita paneli kabisa.
        # Weka JAMIITEK_FORCE_STATUS=suspended (au maintenance)
        # kujaribu bila kugusa paneli ya wateja halisi.
        forced = getattr(settings, 'JAMIITEK_FORCE_STATUS', '')
        if forced:
            return {
                'status': forced,
                'suspension_message': getattr(
                    settings, 'JAMIITEK_FORCE_MESSAGE',
                    'Huduma imesitishwa kwa muda. Wasiliana na JamiiTek.'
                ),
                'features': {},
            }

        cached = cache.get(self.CACHE_KEY)
        if cached is not None:
            return cached

        try:
            url = f"{self.api_url.rstrip('/')}/{self.api_key}/"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                cache.set(self.CACHE_KEY, data, self.CACHE_TIMEOUT)
                return data
        except Exception as e:
            logger.warning(f"JamiiTek: Imeshindwa kuangalia hali: {e}")
        
        return None


def is_feature_enabled(request, feature_key):
    """
    Helper function kuangalia ikiwa feature fulani imewashwa.
    
    Matumizi kwenye views:
        from jamiitek_middleware import is_feature_enabled
        
        def my_view(request):
            if not is_feature_enabled(request, 'ecommerce'):
                return HttpResponse("Huduma hii haipo sasa hivi.")
            ...
    
    Matumizi kwenye templates:
        {% load jamiitek_tags %}
        {% if request|feature_enabled:"ecommerce" %}
            ... onyesha ecommerce content ...
        {% endif %}
    """
    features = getattr(request, 'jamiitek_features', {})
    return features.get(feature_key, True)  # Default: True (imewashwa)
