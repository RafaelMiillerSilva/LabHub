"""
Rotas do aplicativo LabHub.
"""

from django.contrib.auth.views import LogoutView
from django.urls import path
from app import views

urlpatterns = [
    # Páginas principais
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),

    # Painel administrativo e auditoria
    path('painel/', views.painel, name='painel'),
    path('painel/aprovar/<int:perfil_id>/', views.aprovar_usuario, name='aprovar_usuario'),
    path('painel/negar/<int:perfil_id>/', views.negar_usuario, name='negar_usuario'),
    path('painel/usuario/<int:user_id>/ativar/', views.usuario_toggle_ativo, name='usuario_toggle_ativo'),
    path('painel/usuario/<int:user_id>/tipo/', views.usuario_toggle_tipo, name='usuario_toggle_tipo'),
    path('painel/senha/<int:pedido_id>/', views.redefinir_senha_admin, name='redefinir_senha_admin'),
    path('painel/redefinir-senha/<int:pedido_id>/cancelar/', views.cancelar_redefinicao_senha_admin, name='cancelar_redefinicao_senha_admin'),

    # Turmas e alunos
    path('turmas/', views.turmas, name='turmas'),
    path('turmas/modelo-planilha/', views.modelo_planilha_alunos, name='modelo_planilha_alunos'),
    path('turmas/<int:turma_id>/', views.turma_detalhe, name='turma_detalhe'),
    path('turmas/<int:turma_id>/excluir/', views.turma_excluir, name='turma_excluir'),
    path('turmas/<int:turma_id>/importar/', views.importar_alunos, name='importar_alunos'),
    path('alunos/<int:aluno_id>/excluir/', views.aluno_excluir, name='aluno_excluir'),

    # Salas
    path('salas/', views.salas, name='salas'),
    path('salas/<int:sala_id>/excluir/', views.sala_excluir, name='sala_excluir'),

    # Equipamentos
    path('equipamentos/', views.equipamentos, name='equipamentos'),
    path('equipamentos/novo/', views.equipamento_form, name='equipamento_novo'),
    path('equipamentos/etiquetas/', views.etiquetas_lote, name='etiquetas_lote'),
    path('equipamentos/<int:equip_id>/editar/', views.equipamento_form, name='equipamento_editar'),
    path('equipamentos/<int:equip_id>/excluir/', views.equipamento_excluir, name='equipamento_excluir'),
    path('equipamentos/<int:equip_id>/etiqueta/', views.etiqueta_equipamento, name='etiqueta_equipamento'),
    path('equipamentos/<int:equip_id>/foto/', views.foto_equipamento, name='foto_equipamento'),
    path('equipamentos/exportar/', views.exportar_equipamentos, name='exportar_equipamentos'),

    # Agendamentos
    path('agendamentos/', views.agendamentos, name='agendamentos'),
    path('agendamentos/excel/', views.exportar_excel_mes, name='exportar_excel_mes'),
    path('agendamentos/exportar/', views.exportar_agendamentos, name='exportar_agendamentos'),
    path('agendamentos/<int:ano>/<int:mes>/<int:dia>/', views.agendamento_detalhe, name='agendamento_detalhe'),
    path('agendamentos/<int:agendamento_id>/cancelar/', views.cancelar_reserva, name='cancelar_reserva'),
    path('agendamentos/<int:agendamento_id>/relacao/', views.relacao_agendamento, name='relacao_agendamento'),

    # Relações
    path('relacoes/', views.relacoes_lista, name='relacoes_lista'),
    path('relacoes/exportar/', views.exportar_relacoes, name='exportar_relacoes'),

    # Ocorrências (acesso restrito a administradores)
    path('ocorrencias/', views.ocorrencias_lista, name='ocorrencias_lista'),
    path('ocorrencias/nova/', views.ocorrencia_criar, name='ocorrencia_criar'),
    path('ocorrencias/<int:ocorrencia_id>/', views.ocorrencia_detalhe, name='ocorrencia_detalhe'),
    path('ocorrencias/<int:ocorrencia_id>/editar/', views.ocorrencia_editar, name='ocorrencia_editar'),
    path('ocorrencias/<int:ocorrencia_id>/pdf/', views.ocorrencia_pdf, name='ocorrencia_pdf'),
    path('ocorrencias/<int:ocorrencia_id>/excluir/', views.ocorrencia_excluir, name='ocorrencia_excluir'),
    path('ocorrencias/foto/<int:foto_id>/', views.foto_ocorrencia, name='foto_ocorrencia'),
    path('ocorrencias/foto/<int:foto_id>/cortar/', views.ocorrencia_foto_cortar, name='ocorrencia_foto_cortar'),
    path('ocorrencias/api/agendamentos-por-data/', views.api_agendamentos_por_data, name='api_agendamentos_por_data'),
    path('ocorrencias/api/agendamento/<int:agendamento_id>/contexto/', views.api_agendamento_contexto, name='api_agendamento_contexto'),

    # Notificações
    path('notificacoes/', views.listar_notificacoes, name='listar_notificacoes'),
    path('notificacoes/lidas/', views.marcar_lidas, name='marcar_lidas'),
    path('notificacoes/limpar/', views.limpar_notificacoes, name='limpar_notificacoes'),
    path('notificacoes/enviar-geral/', views.enviar_notificacao_geral, name='enviar_notificacao_geral'),

    # Chat
    path('chat/', views.chat_inbox, name='chat_inbox'),
    path('chat/<int:usuario_id>/', views.chat_conversa, name='chat_conversa'),
    path('chat/api/contatos/', views.api_chat_contatos, name='api_chat_contatos'),
    path('chat/api/enviar/<int:usuario_id>/', views.api_chat_enviar, name='api_chat_enviar'),
    path('chat/api/buscar/<int:usuario_id>/', views.api_chat_buscar, name='api_chat_buscar'),
    path('chat/api/nao-lidas/', views.api_chat_nao_lidas, name='api_chat_nao_lidas'),

    # Perfil / Conta
    path('conta/', views.minha_conta, name='minha_conta'),
    path('conta/senha/', views.alterar_senha, name='alterar_senha'),
    path('conta/verificar-senha/', views.verificar_senha, name='verificar_senha'),
    path('perfil/<int:user_id>/foto/', views.foto_perfil, name='foto_perfil'),

    # Autenticação e Senha
    path('esqueci-senha/', views.esqueci_senha, name='esqueci_senha'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
]
