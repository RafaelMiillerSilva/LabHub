"""
Serviço centralizado para registrar eventos de auditoria no HistoricoAcao.
"""

from app.models import HistoricoAcao


def registrar_acao(usuario, acao, solicitante_username='', solicitante_email='', tipo_solicitado=''):
    """
    Registra uma ação de auditoria de forma padronizada.
    """
    return HistoricoAcao.objects.create(
        admin=usuario if (usuario and usuario.is_authenticated) else None,
        acao=acao,
        username_solicitante=solicitante_username,
        email_solicitante=solicitante_email,
        tipo_solicitado=tipo_solicitado,
    )
