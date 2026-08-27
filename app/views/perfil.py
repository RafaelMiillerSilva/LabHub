"""
Views de perfil/conta do usuário.
"""

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect

from app.models import Perfil
from .common import is_usuario_aprovado


@login_required
def minha_conta(request):
    """Exibe e processa alterações nos dados da conta do usuário."""
    if not is_usuario_aprovado(request.user):
        messages.warning(request, 'Sua conta ainda não foi aprovada.')
        return redirect('home')

    perfil = request.user.perfil

    if request.method == 'POST':
        acao = request.POST.get('acao', '')

        if acao == 'dados':
            novo_username = request.POST.get('username', '').strip()
            novo_email = request.POST.get('email', '').strip()

            erros = []
            if not novo_username:
                erros.append('O nome de usuário não pode ficar vazio.')
            elif novo_username != request.user.username:
                from django.contrib.auth.models import User
                if User.objects.filter(username=novo_username).exists():
                    erros.append('Este nome de usuário já está em uso.')

            if not novo_email:
                erros.append('O email não pode ficar vazio.')
            elif novo_email != request.user.email:
                from django.contrib.auth.models import User
                if User.objects.filter(email=novo_email).exists():
                    erros.append('Este email já está em uso.')

            if erros:
                for e in erros:
                    messages.error(request, e)
            else:
                request.user.username = novo_username
                request.user.email = novo_email
                request.user.save()
                messages.success(request, 'Dados atualizados com sucesso!')

            return redirect('minha_conta')

        elif acao == 'foto':
            foto = request.FILES.get('foto')
            if foto:
                mime = foto.content_type
                if mime not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif'):
                    messages.error(request, 'Formato de imagem inválido. Use JPG, PNG, WEBP ou GIF.')
                elif foto.size > 2 * 1024 * 1024:
                    messages.error(request, 'A foto deve ter no máximo 2 MB.')
                else:
                    perfil.foto_dados = foto.read()
                    perfil.foto_mime = mime
                    perfil.tem_foto = True
                    perfil.save()
                    messages.success(request, 'Foto atualizada com sucesso!')
            else:
                messages.warning(request, 'Nenhuma foto selecionada.')

            return redirect('minha_conta')

        elif acao == 'remover_foto':
            perfil.foto_dados = None
            perfil.foto_mime = ''
            perfil.tem_foto = False
            perfil.save()
            messages.success(request, 'Foto removida com sucesso!')
            return redirect('minha_conta')

    return render(request, 'app/minha_conta.html', {
        'title': 'Minha Conta',
        'perfil': perfil,
    })


@login_required
def alterar_senha(request):
    """Altera a senha do usuário autenticado."""
    if request.method != 'POST':
        return redirect('minha_conta')

    if not is_usuario_aprovado(request.user):
        messages.warning(request, 'Sua conta ainda não foi aprovada.')
        return redirect('home')

    senha_atual = request.POST.get('senha_atual', '')
    nova_senha = request.POST.get('nova_senha', '')
    confirmar_senha = request.POST.get('confirmar_senha', '')

    if not request.user.check_password(senha_atual):
        messages.error(request, 'A senha atual está incorreta.')
        return redirect('minha_conta')

    if len(nova_senha) < 6:
        messages.error(request, 'A nova senha deve ter no mínimo 6 caracteres.')
        return redirect('minha_conta')

    if nova_senha != confirmar_senha:
        messages.error(request, 'A nova senha e a confirmação não coincidem.')
        return redirect('minha_conta')

    request.user.set_password(nova_senha)
    request.user.save()
    update_session_auth_hash(request, request.user)
    messages.success(request, 'Senha alterada com sucesso!')
    return redirect('minha_conta')


def foto_perfil(request, user_id):
    """Retorna a foto de perfil como resposta HTTP binária (para uso em <img src>)."""
    try:
        perfil = Perfil.objects.get(user_id=user_id)
    except Perfil.DoesNotExist:
        raise Http404

    if not perfil.tem_foto or not perfil.foto_dados:
        raise Http404

    return HttpResponse(
        bytes(perfil.foto_dados),
        content_type=perfil.foto_mime or 'image/jpeg',
    )
