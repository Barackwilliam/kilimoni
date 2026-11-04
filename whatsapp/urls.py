from django.urls import path
from . import views, greenapi_views

urlpatterns = [
    path('whatsapp/', views.webhook, name='whatsapp_webhook'),

    # Baileys WhatsApp bridge
    path('baileys/incoming/',views.baileys_incoming, name='baileys_incoming'),
    # Bridge mpya (nakala ya JamiiTek) — haisubiri jibu
    path('bridge/incoming/', views.bridge_incoming, name='bridge_incoming'),
    path('bridge/sessions/', views.bridge_sessions, name='bridge_sessions'),
    # path('greenapi/', greenapi_views.greenapi_webhook, name='greenapi_webhook'),
    
]


