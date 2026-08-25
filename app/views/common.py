"""
Constantes, helpers e utilitários compartilhados entre as views.
"""

from django.template.loader import render_to_string



MESES_PT = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]

DIAS_SEMANA_PT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

DIAS_SEMANA_LONGO = [
    'Segunda-feira', 'Terça-feira', 'Quarta-feira',
    'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo',
]

AULAS_HORARIOS = [
    ('1ª Aula', '07:00 - 07:50'),
    ('2ª Aula', '07:50 - 08:40'),
    ('3ª Aula', '08:40 - 09:30'),
    ('4ª Aula', '09:50 - 10:40'),
    ('5ª Aula', '10:40 - 11:30'),
    ('6ª Aula', '11:30 - 12:20'),
    ('7ª Aula', '13:00 - 13:50'),
    ('8ª Aula', '13:50 - 14:40'),
    ('9ª Aula', '14:40 - 15:30'),
]


def is_usuario_aprovado(user):
    """Verifica se o usuário está autenticado, ativo e aprovado."""
    return (
        user.is_authenticated
        and user.is_active
        and hasattr(user, 'perfil')
        and user.perfil.aprovado
    )


def is_admin_aprovado(user):
    """Verifica se o usuário é administrador, ativo e aprovado."""
    return (
        user.is_authenticated
        and user.is_active
        and (user.is_staff or (hasattr(user, 'perfil') and user.perfil.tipo == 'ADMINISTRADOR' and user.perfil.aprovado))
    )


def is_ajax(request):
    """Verifica se a requisição foi feita via AJAX."""
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def linha_usuario_html(request, perfil):
    """Renderiza o template parcial de uma linha de usuário no painel."""
    return render_to_string(
        'app/_usuario_linha.html',
        {'u': perfil, 'user': request.user},
        request=request,
    )
