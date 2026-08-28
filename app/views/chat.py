import json
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.db.models import Q

from app.models import MensagemChat, Notificacao
from .common import is_usuario_aprovado


def limpar_mensagens_antigas():
    """Remove mensagens de chat com mais de 7 dias para não pesar o banco."""
    limite = timezone.now() - timedelta(days=7)
    MensagemChat.objects.filter(data_envio__lt=limite).delete()


@login_required
def chat_inbox(request):
    """Exibe a lista de contatos com quem o usuário tem conversas ativas ou pode conversar."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    limpar_mensagens_antigas()

    usuarios_disponiveis = User.objects.filter(perfil__aprovado=True).exclude(id=request.user.id).order_by('first_name', 'username')

    contatos = []
    for u in usuarios_disponiveis:
        ultima_msg = MensagemChat.objects.filter(
            Q(remetente=request.user, destinatario=u) |
            Q(remetente=u, destinatario=request.user)
        ).order_by('-data_envio').first()

        nao_lidas = MensagemChat.objects.filter(
            remetente=u, destinatario=request.user, lida=False
        ).count()

        contatos.append({
            'usuario': u,
            'ultima_msg': ultima_msg,
            'nao_lidas': nao_lidas,
            'data_ordenacao': ultima_msg.data_envio if ultima_msg else (timezone.now() - timedelta(days=3650))
        })

    contatos.sort(key=lambda x: x['data_ordenacao'], reverse=True)
    
    return render(request, 'app/chat_inbox.html', {
        'contatos': contatos,
        'title': 'Mensagens',
    })


@login_required
def chat_conversa(request, usuario_id):
    """Exibe a conversa com um usuário específico."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    limpar_mensagens_antigas()

    contato = get_object_or_404(User, id=usuario_id, perfil__aprovado=True)

    Notificacao.objects.filter(
        destinatario=request.user,
        lida=False,
        mensagem__icontains=contato.username
    ).update(lida=True)

    MensagemChat.objects.filter(remetente=contato, destinatario=request.user, lida=False).update(lida=True)

    mensagens = MensagemChat.objects.filter(
        Q(remetente=request.user, destinatario=contato) |
        Q(remetente=contato, destinatario=request.user)
    ).order_by('data_envio')

    return render(request, 'app/chat_conversa.html', {
        'contato': contato,
        'mensagens': mensagens,
        'title': f'Chat com {contato.get_full_name() or contato.username}',
    })


@login_required
def api_chat_enviar(request, usuario_id):
    """Endpoint via POST para enviar uma mensagem via AJAX."""
    if request.method == 'POST':
        if not is_usuario_aprovado(request.user):
            return JsonResponse({'sucesso': False, 'erro': 'Não autorizado'}, status=403)

        contato = get_object_or_404(User, id=usuario_id, perfil__aprovado=True)
        try:
            dados = json.loads(request.body)
            texto = dados.get('texto', '').strip()
            
            if texto:
                msg = MensagemChat.objects.create(
                    remetente=request.user,
                    destinatario=contato,
                    texto=texto
                )
                
                Notificacao.objects.create(
                    destinatario=contato,
                    mensagem=f"Nova mensagem no Chat de {request.user.get_full_name() or request.user.username}"
                )

                return JsonResponse({
                    'sucesso': True,
                    'mensagem': {
                        'id': msg.id,
                        'texto': msg.texto,
                        'data': msg.data_envio.strftime('%H:%M')
                    }
                })
            else:
                return JsonResponse({'sucesso': False, 'erro': 'Mensagem vazia'})
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})

    return JsonResponse({'sucesso': False, 'erro': 'Método inválido'}, status=400)


@login_required
def api_chat_buscar(request, usuario_id):
    """Endpoint via GET para buscar mensagens não lidas ou após um certo ID."""
    if not is_usuario_aprovado(request.user):
        return JsonResponse({'sucesso': False}, status=403)

    contato = get_object_or_404(User, id=usuario_id, perfil__aprovado=True)
    ultimo_id = request.GET.get('ultimo_id', 0)

    try:
        ultimo_id = int(ultimo_id)
    except ValueError:
        ultimo_id = 0

    novas_mensagens = MensagemChat.objects.filter(
        Q(remetente=contato, destinatario=request.user) |
        Q(remetente=request.user, destinatario=contato),
        id__gt=ultimo_id
    ).order_by('data_envio')

    if novas_mensagens.filter(remetente=contato).exists():
        MensagemChat.objects.filter(
            id__in=[m.id for m in novas_mensagens if m.remetente == contato]
        ).update(lida=True)

    dados_mensagens = []
    for m in novas_mensagens:
        dados_mensagens.append({
            'id': m.id,
            'remetente': m.remetente.id,
            'texto': m.texto,
            'data': m.data_envio.strftime('%H:%M'),
            'e_minha': m.remetente == request.user
        })

    return JsonResponse({'sucesso': True, 'mensagens': dados_mensagens})


@login_required
def api_chat_nao_lidas(request):
    """Retorna o número total de mensagens não lidas."""
    if not is_usuario_aprovado(request.user):
        return JsonResponse({'total': 0})
    
    total = MensagemChat.objects.filter(destinatario=request.user, lida=False).count()
    return JsonResponse({'total': total})
