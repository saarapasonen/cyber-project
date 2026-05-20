from django.urls import path

from . import views

urlpatterns = [
    path('', views.entry_list, name='entry_list'),
    path('new/', views.entry_create, name='entry_create'),
    path('<int:pk>/', views.entry_detail, name='entry_detail'),
    path('<int:pk>/edit/', views.entry_edit, name='entry_edit'),
    path('<int:pk>/delete/', views.entry_delete, name='entry_delete'),
    path('profile/pin/', views.profile_pin, name='profile_pin'),
    path('team/', views.team_summary, name='team_summary'),
    path('debug-error/', views.debug_error, name='debug_error'),
    path('accounts/register/', views.register, name='register'),
]
