"""
Definition of urls for LabHub.
"""

from django.urls import path
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from app import views


urlpatterns = [
    path('admin/', admin.site.urls),

    # Páginas principais
    path('',         views.home,    name='home'),
    path('about/',   views.about,   name='about'),
    path('contact/', views.contact, name='contact'),

    # Painel administrativo
    path('painel/',                              views.painel,              name='painel'),
    path('painel/aprovar/<int:perfil_id>/',      views.aprovar_usuario,     name='aprovar_usuario'),
    path('painel/negar/<int:perfil_id>/',        views.negar_usuario,       name='negar_usuario'),
    path('painel/usuario/<int:user_id>/ativar/', views.usuario_toggle_ativo, name='usuario_toggle_ativo'),
    path('painel/usuario/<int:user_id>/tipo/',   views.usuario_toggle_tipo,  name='usuario_toggle_tipo'),

    # Turmas e alunos
    path('turmas/',                          views.turmas,                 name='turmas'),
    path('turmas/modelo-planilha/',          views.modelo_planilha_alunos, name='modelo_planilha_alunos'),
    path('turmas/<int:turma_id>/',           views.turma_detalhe,          name='turma_detalhe'),
    path('turmas/<int:turma_id>/excluir/',   views.turma_excluir,          name='turma_excluir'),
    path('turmas/<int:turma_id>/importar/',  views.importar_alunos,        name='importar_alunos'),
    path('alunos/<int:aluno_id>/excluir/',   views.aluno_excluir,          name='aluno_excluir'),

    # Salas
    path('salas/',                        views.salas,       name='salas'),
    path('salas/<int:sala_id>/excluir/',  views.sala_excluir, name='sala_excluir'),

    # Equipamentos
    path('equipamentos/',                          views.equipamentos,        name='equipamentos'),
    path('equipamentos/novo/',                     views.equipamento_form,    name='equipamento_novo'),
    path('equipamentos/etiquetas/',                views.etiquetas_lote,      name='etiquetas_lote'),
    path('equipamentos/<int:equip_id>/editar/',    views.equipamento_form,    name='equipamento_editar'),
    path('equipamentos/<int:equip_id>/excluir/',   views.equipamento_excluir, name='equipamento_excluir'),
    path('equipamentos/<int:equip_id>/etiqueta/',  views.etiqueta_equipamento, name='etiqueta_equipamento'),
    path('equipamentos/<int:equip_id>/foto/',      views.foto_equipamento,    name='foto_equipamento'),

    # Agendamentos
    path('agendamentos/',                                    views.agendamentos,        name='agendamentos'),
    path('agendamentos/<int:ano>/<int:mes>/<int:dia>/',      views.agendamento_detalhe, name='agendamento_detalhe'),
    path('agendamentos/<int:agendamento_id>/cancelar/',      views.cancelar_reserva,    name='cancelar_reserva'),
    path('agendamentos/<int:agendamento_id>/relacao/',       views.relacao_agendamento, name='relacao_agendamento'),

    # Autenticação
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
]