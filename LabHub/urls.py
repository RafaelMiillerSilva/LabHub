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

    # Agendamentos
    path('agendamentos/',                 views.agendamentos,   name='agendamentos'),
    path('agendamentos/<int:ano>/<int:mes>/<int:dia>/',
         views.agendamento_detalhe, name='agendamento_detalhe'),

    # Cadastro de salas (somente admin)
    path('salas/',                        views.salas,          name='salas'),
    path('salas/excluir/<int:sala_id>/',  views.sala_excluir,   name='sala_excluir'),

    # Cadastro de equipamentos (somente admin)
    path('equipamentos/',                 views.equipamentos,        name='equipamentos'),
    path('equipamentos/excluir/<int:equip_id>/',
         views.equipamento_excluir, name='equipamento_excluir'),

    # Cadastro de turmas e alunos (somente admin)
    path('turmas/',                       views.turmas,         name='turmas'),
    path('turmas/modelo-alunos/',         views.modelo_planilha_alunos, name='modelo_planilha_alunos'),
    path('turmas/excluir/<int:turma_id>/', views.turma_excluir, name='turma_excluir'),
    path('turmas/<int:turma_id>/',        views.turma_detalhe,  name='turma_detalhe'),
    path('turmas/<int:turma_id>/importar/', views.importar_alunos, name='importar_alunos'),
    path('turmas/aluno/excluir/<int:aluno_id>/',
         views.aluno_excluir, name='aluno_excluir'),

    # Painel administrativo
    path('painel/',                       views.painel,         name='painel'),
    path('painel/aprovar/<int:perfil_id>/', views.aprovar_usuario, name='aprovar_usuario'),
    path('painel/negar/<int:perfil_id>/',   views.negar_usuario,   name='negar_usuario'),

    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
]