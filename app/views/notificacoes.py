"""
Views de notificações do sistema (AJAX).
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from app.models import Notificacao
from .common import is_usuario_aprovado


@login_required
@ensure_csrf_cookie
def listar_notificacoes(request):
    """Retorna as últimas 20 notificações do usuário em JSON."""
    if not is_usuario_aprovado(request.user):
        return JsonResponse({'ok': False, 'message': 'Acesso negado.'}, status=403)

    notificacoes = (
        Notificacao.objects
        .filter(destinatario=request.user)
        .order_by('-criada_em')[:20]
    )
    nao_lidas = (
        Notificacao.objects
        .filter(destinatario=request.user, lida=False)
        .count()
    )

    lista = []
    for n in notificacoes:
        lista.append({
            'id': n.id,
            'mensagem': n.mensagem,
            'lida': n.lida,
            'criada_em': _tempo_relativo(n.criada_em),
        })

    return JsonResponse({
        'ok': True,
        'notificacoes': lista,
        'nao_lidas': nao_lidas,
    })


@login_required
def marcar_lidas(request):
    """Marca todas as notificações do usuário como lidas."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Método não permitido.'}, status=405)

    if not is_usuario_aprovado(request.user):
        return JsonResponse({'ok': False, 'message': 'Acesso negado.'}, status=403)

    Notificacao.objects.filter(
        destinatario=request.user, lida=False
    ).update(lida=True)

    return JsonResponse({'ok': True, 'message': 'Notificações marcadas como lidas.'})

@login_required
def limpar_notificacoes(request):
    """Apaga todas as notificações do usuário."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Método não permitido.'}, status=405)

    if not is_usuario_aprovado(request.user):
        return JsonResponse({'ok': False, 'message': 'Acesso negado.'}, status=403)

    Notificacao.objects.filter(destinatario=request.user).delete()

    return JsonResponse({'ok': True, 'message': 'Notificações apagadas com sucesso.'})


def _tempo_relativo(dt):
    """Retorna string legível como 'há 2 min', 'há 1h', 'há 3 dias'."""
    from django.utils import timezone
    agora = timezone.now()
    diff = agora - dt
    segundos = int(diff.total_seconds())

    if segundos < 60:
        return 'agora'
    minutos = segundos // 60
    if minutos < 60:
        return f'há {minutos} min'
    horas = minutos // 60
    if horas < 24:
        return f'há {horas}h'
    dias = horas // 24
    if dias == 1:
        return 'há 1 dia'
    if dias < 30:
        return f'há {dias} dias'
    return dt.strftime('%d/%m/%Y')
