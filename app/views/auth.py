"""
Views de autenticação, recuperação e redefinição de senhas.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from app.models import PedidoRedefinicaoSenha
from app.services.historico_service import registrar_acao
from .common import is_admin_aprovado


def esqueci_senha(request):
    """Permite ao usuário solicitar redefinição de senha ao administrador."""
    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        if identificador:
            user = User.objects.filter(
                Q(email__iexact=identificador) | Q(username__iexact=identificador)
            ).first()
            if user:
                PedidoRedefinicaoSenha.objects.get_or_create(user=user, atendido=False)

        messages.success(
            request,
            'Se a conta existir, o administrador foi avisado e vai definir uma nova '
            'senha para você. Procure a coordenação para retirá-la.'
        )
        return redirect('home')

    return render(request, 'app/esqueci_senha.html', {'title': 'Esqueci minha senha'})


@login_required
def redefinir_senha_admin(request, pedido_id):
    """Administrador define uma nova senha para o usuário solicitante."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        pedido = get_object_or_404(PedidoRedefinicaoSenha, id=pedido_id, atendido=False)
        nova = request.POST.get('nova_senha', '')

        try:
            validate_password(nova, user=pedido.user)
        except ValidationError as e:
            for erro in e.messages:
                messages.warning(request, erro)
            return redirect('painel')

        u = pedido.user
        u.set_password(nova)
        u.save()

        pedido.atendido = True
        pedido.atendido_em = timezone.now()
        pedido.atendido_por = request.user
        pedido.save()

        registrar_acao(
            usuario=request.user,
            acao='REDEFINIDO',
            solicitante_username=u.username,
            solicitante_email=u.email,
            tipo_solicitado=u.perfil.tipo if hasattr(u, 'perfil') else '',
        )

        messages.success(
            request,
            f'Senha de "{u.username}" redefinida com sucesso. Informe a nova senha ao usuário.'
        )

    return redirect('painel')


@login_required
def cancelar_redefinicao_senha_admin(request, pedido_id):
    """Cancela um pedido de redefinição de senha pendente."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        pedido = get_object_or_404(PedidoRedefinicaoSenha, id=pedido_id, atendido=False)
        u = pedido.user

        registrar_acao(
            usuario=request.user,
            acao='SENHA_CANCELADA',
            solicitante_username=u.username,
            solicitante_email=u.email,
            tipo_solicitado=u.perfil.tipo if hasattr(u, 'perfil') else '',
        )

        pedido.delete()
        messages.warning(request, f'Pedido de redefinição de senha para "{u.username}" foi cancelado.')

    return redirect('painel')
