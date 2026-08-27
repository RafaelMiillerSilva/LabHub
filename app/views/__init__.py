"""
Pacote de views modular do LabHub.
Re-exporta todas as views para garantir compatibilidade com URLs e outros módulos.
"""

from .paginas import home, about, contact
from .auth import (
    esqueci_senha,
    redefinir_senha_admin,
    cancelar_redefinicao_senha_admin,
)
from .painel import (
    painel,
    aprovar_usuario,
    negar_usuario,
    usuario_toggle_ativo,
    usuario_toggle_tipo,
)
from .salas import (
    salas,
    sala_excluir,
)
from .turmas import (
    turmas,
    turma_detalhe,
    turma_excluir,
    aluno_excluir,
    importar_alunos,
    modelo_planilha_alunos,
)
from .equipamentos import (
    equipamentos,
    equipamento_form,
    equipamento_editar,
    foto_equipamento,
    equipamento_excluir,
    etiqueta_equipamento,
    etiquetas_lote,
    exportar_equipamentos,
)
from .agendamentos import (
    agendamentos,
    agendamento_detalhe,
    cancelar_reserva,
    relacao_agendamento,
    _disponibilidade_dispositivos,
    _estoque_por_categoria,
)
from .notificacoes import (
    listar_notificacoes,
    marcar_lidas,
    limpar_notificacoes,
)

__all__ = [
    'home',
    'about',
    'contact',
    'esqueci_senha',
    'redefinir_senha_admin',
    'cancelar_redefinicao_senha_admin',
    'painel',
    'aprovar_usuario',
    'negar_usuario',
    'usuario_toggle_ativo',
    'usuario_toggle_tipo',
    'salas',
    'sala_excluir',
    'turmas',
    'turma_detalhe',
    'turma_excluir',
    'aluno_excluir',
    'importar_alunos',
    'modelo_planilha_alunos',
    'equipamentos',
    'equipamento_form',
    'equipamento_editar',
    'foto_equipamento',
    'equipamento_excluir',
    'etiqueta_equipamento',
    'etiquetas_lote',
    'exportar_equipamentos',
    'agendamentos',
    'agendamento_detalhe',
    'cancelar_reserva',
    'relacao_agendamento',
    '_disponibilidade_dispositivos',
    '_estoque_por_categoria',
    'listar_notificacoes',
    'marcar_lidas',
    'limpar_notificacoes',
]
