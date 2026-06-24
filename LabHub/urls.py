"""
Definition of urls for LabHub.
"""

from datetime import datetime
from django.urls import path
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from app import forms, views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('',                              views.home,           name='home'),
    path('about/',                        views.about,          name='about'),
    path('contact/',                      views.contact,        name='contact'),
    path('agendamentos/',                 views.agendamentos,   name='agendamentos'),
    path('painel/',                       views.painel,         name='painel'),
    path('painel/aprovar/<int:perfil_id>/', views.aprovar_usuario, name='aprovar_usuario'),
    path('painel/negar/<int:perfil_id>/',   views.negar_usuario,   name='negar_usuario'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
]
