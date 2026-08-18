from django.urls import path
from . import views, greenapi_views

urlpatterns = [
    path('whatsapp/', views.webhook, name='whatsapp_webhook'),
    path('greenapi/', greenapi_views.greenapi_webhook, name='greenapi_webhook'),  # Testing
    
]


