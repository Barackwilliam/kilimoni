from django.urls import path
from . import views

urlpatterns = [
    path('test-message/', views.test_message, name='test_message'),
    path('users/', views.user_list, name='user_list'),
]
