from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='dashboard_home'),
    path('login/', views.login_view, name='dashboard_login'),
    path('logout/', views.logout_view, name='dashboard_logout'),
    path('conversations/', views.conversations, name='conversations'),
    path('users/', views.users_list, name='users_list'),
    path('crops/', views.crops_list, name='crops_list'),
    path('crops/add/', views.crop_add, name='crop_add'),
    path('crops/<int:pk>/edit/', views.crop_edit, name='crop_edit'),
    path('templates/', views.templates_list, name='templates_list'),
    path('templates/add/', views.template_add, name='template_add'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('unresolved/', views.unresolved_list, name='unresolved_list'),
    path('unresolved/<int:pk>/resolve/', views.unresolved_resolve, name='unresolved_resolve'),
    path('synonyms/', views.synonyms_list, name='synonyms_list'),
    path('synonyms/add/', views.synonym_add, name='synonym_add'),
    path('test-bot/', views.test_bot, name='test_bot'),
    path('test-bot/classic/', views.test_bot_classic, name='test_bot_classic'),
    path('csv-import/', views.csv_import_view, name='csv_import'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('status/', views.system_status, name='system_status'),
    path('groq-status/', views.groq_status_view, name='groq_status'),
]
