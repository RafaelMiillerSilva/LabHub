"""
Views do painel administrativo e controle de usuários.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from app.models import HistoricoAcao, PedidoRedefinicaoSenha, Perfil
from app.services.historico_service import registrar_acao
from .common import is_admin_aprovado, is_ajax, linha_usuario_html


def _admins_ativos_qs():
    return Perfil.objects.filter(
        tipo='ADMINISTRADOR', aprovado=True, user__is_active=True
    )


@login_required
def painel(request):
    """Exibe o painel de administração geral."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    aba = request.GET.get('tab', 'solicitacoes')
    q = request.GET.get('q', '').strip()
    de = request.GET.get('de', '').strip()
    ate = request.GET.get('ate', '').strip()

    solicitacoes = Perfil.objects.filter(aprovado=False).select_related('user')

    pedidos_senha = (
        PedidoRedefinicaoSenha.objects.filter(atendido=False)
        .select_related('user', 'user__perfil')
    )

    usuarios = (
        Perfil.objects.filter(aprovado=True)
        .select_related('user')
        .order_by('tipo', 'user__username')
    )
    if q:
        usuarios = usuarios.filter(
            Q(user__username__icontains=q) | Q(user__email__icontains=q)
        )

    historico = HistoricoAcao.objects.select_related('admin').all()
    d_de = parse_date(de) if de else None
    d_ate = parse_date(ate) if ate else None
    if d_de:
        historico = historico.filter(data_acao__date__gte=d_de)
    if d_ate:
        historico = historico.filter(data_acao__date__lte=d_ate)
    historico = historico[:100]

    if q and aba == 'solicitacoes':
        aba = 'usuarios'
    if (de or ate) and aba == 'solicitacoes':
        aba = 'historico'

    return render(request, 'app/painel.html', {
        'title': 'Painel Administrativo',
        'solicitacoes': solicitacoes,
        'pedidos_senha': pedidos_senha,
        'historico': historico,
        'usuarios': usuarios,
        'aba': aba,
        'q': q,
        'de': de,
        'ate': ate,
    })


@login_required
def aprovar_usuario(request, perfil_id):
    """Aprova a solicitação de cadastro de um usuário."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        perfil = get_object_or_404(Perfil, id=perfil_id, aprovado=False)

        registrar_acao(
            usuario=request.user,
            acao='APROVADO',
            solicitante_username=perfil.user.username,
            solicitante_email=perfil.user.email,
            tipo_solicitado=perfil.tipo,
        )

        perfil.aprovado = True
        perfil.save()

        pendentes = Perfil.objects.filter(aprovado=False).count()
        msg = f'Usuário "{perfil.user.username}" aprovado com sucesso!'
        if is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'aprovar', 'message': msg,
                'perfil_id': perfil.id, 'pendentes': pendentes,
                'html': linha_usuario_html(request, perfil),
            })
        messages.success(request, msg)

    return redirect('painel')


@login_required
def negar_usuario(request, perfil_id):
    """Nega a solicitação de cadastro e remove o usuário."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        perfil = get_object_or_404(Perfil, id=perfil_id, aprovado=False)
        user = perfil.user

        registrar_acao(
            usuario=request.user,
            acao='NEGADO',
            solicitante_username=user.username,
            solicitante_email=user.email,
            tipo_solicitado=perfil.tipo,
        )

        username = user.username
        user.delete()

        pendentes = Perfil.objects.filter(aprovado=False).count()
        msg = f'Solicitação de "{username}" negada e dados removidos.'
        if is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'negar', 'message': msg,
                'perfil_id': perfil_id, 'pendentes': pendentes,
            })
        messages.warning(request, msg)

    return redirect('painel')


@login_required
def usuario_toggle_ativo(request, user_id):
    """Ativa ou desativa a conta de um usuário."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        alvo = get_object_or_404(User, id=user_id)

        if alvo.id == request.user.id:
            msg = 'Você não pode desativar a sua própria conta.'
            if is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        eh_admin = hasattr(alvo, 'perfil') and alvo.perfil.tipo == 'ADMINISTRADOR'
        if alvo.is_active and eh_admin and _admins_ativos_qs().count() <= 1:
            msg = 'Não é possível desativar o último administrador ativo.'
            if is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        alvo.is_active = not alvo.is_active
        alvo.save(update_fields=['is_active'])

        registrar_acao(
            usuario=request.user,
            acao='ATIVADO' if alvo.is_active else 'DESATIVADO',
            solicitante_username=alvo.username,
            solicitante_email=alvo.email,
            tipo_solicitado=alvo.perfil.tipo if hasattr(alvo, 'perfil') else '',
        )

        estado = 'ativada' if alvo.is_active else 'desativada'
        msg = f'Conta de "{alvo.username}" {estado} com sucesso.'
        if is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'atualizar_usuario', 'message': msg,
                'user_id': alvo.id, 'html': linha_usuario_html(request, alvo.perfil),
            })
        messages.success(request, msg)

    return redirect('painel')


@login_required
def usuario_toggle_tipo(request, user_id):
    """Altera o nível de acesso entre Administrador e Professor."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        alvo = get_object_or_404(User, id=user_id)
        perfil = alvo.perfil

        if alvo.id == request.user.id:
            msg = 'Você não pode alterar o seu próprio nível de acesso.'
            if is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        virando_professor = perfil.tipo == 'ADMINISTRADOR'
        if virando_professor and _admins_ativos_qs().count() <= 1:
            msg = 'Não é possível rebaixar o último administrador ativo.'
            if is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        perfil.tipo = 'PROFESSOR' if virando_professor else 'ADMINISTRADOR'
        perfil.save(update_fields=['tipo'])

        registrar_acao(
            usuario=request.user,
            acao='REBAIXADO' if virando_professor else 'PROMOVIDO',
            solicitante_username=alvo.username,
            solicitante_email=alvo.email,
            tipo_solicitado=perfil.tipo,
        )

        novo = 'administrador' if perfil.tipo == 'ADMINISTRADOR' else 'professor'
        msg = f'"{alvo.username}" agora é {novo}.'
        if is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'atualizar_usuario', 'message': msg,
                'user_id': alvo.id, 'html': linha_usuario_html(request, alvo.perfil),
            })
        messages.success(request, msg)

    return redirect('painel')
