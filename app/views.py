from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import CadastroForm, BootstrapAuthenticationForm
from .models import Perfil, HistoricoAcao


def home(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil') and request.user.perfil.aprovado:
            if request.user.perfil.tipo == 'ADMINISTRADOR':
                return redirect('painel')
            return redirect('agendamentos')
        else:
            return render(request, 'app/index.html', {
                'form_login': BootstrapAuthenticationForm(),
                'form_cadastro': CadastroForm(),
                'msg_pendente': True
            })

    form_login = BootstrapAuthenticationForm()
    form_cadastro = CadastroForm()

    if request.method == 'POST':
        if 'btn_login' in request.POST:
            form_login = BootstrapAuthenticationForm(data=request.POST)
            if form_login.is_valid():
                user = form_login.get_user()
                if hasattr(user, 'perfil') and user.perfil.aprovado:
                    login(request, user)
                    return redirect('painel') if user.perfil.tipo == 'ADMINISTRADOR' else redirect('agendamentos')
                else:
                    return render(request, 'app/index.html', {
                        'form_login': form_login,
                        'form_cadastro': form_cadastro,
                        'msg_pendente': True
                    })

        elif 'btn_cadastro' in request.POST:
            form_cadastro = CadastroForm(request.POST)
            if form_cadastro.is_valid():
                form_cadastro.save()
                return render(request, 'app/index.html', {
                    'form_login': form_login,
                    'form_cadastro': CadastroForm(),
                    'msg_sucesso_cadastro': True
                })

    return render(request, 'app/index.html', {
        'form_login': form_login,
        'form_cadastro': form_cadastro,
        'title': 'Bem-vindo ao LabHub'
    })


def _is_admin_aprovado(user):
    return (
        hasattr(user, 'perfil')
        and user.perfil.tipo == 'ADMINISTRADOR'
        and user.perfil.aprovado
    )


@login_required
def painel(request):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    solicitacoes = Perfil.objects.filter(aprovado=False).select_related('user')
    historico = HistoricoAcao.objects.select_related('admin').all()[:50]

    return render(request, 'app/painel.html', {
        'title': 'Painel Administrativo',
        'solicitacoes': solicitacoes,
        'historico': historico,
    })


@login_required
def aprovar_usuario(request, perfil_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        perfil = get_object_or_404(Perfil, id=perfil_id, aprovado=False)

        HistoricoAcao.objects.create(
            admin=request.user,
            acao='APROVADO',
            username_solicitante=perfil.user.username,
            email_solicitante=perfil.user.email,
            tipo_solicitado=perfil.tipo,
        )

        perfil.aprovado = True
        perfil.save()

        messages.success(
            request,
            f'Usuário "{perfil.user.username}" aprovado com sucesso!'
        )

    return redirect('painel')


@login_required
def negar_usuario(request, perfil_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        perfil = get_object_or_404(Perfil, id=perfil_id, aprovado=False)
        user = perfil.user

        HistoricoAcao.objects.create(
            admin=request.user,
            acao='NEGADO',
            username_solicitante=user.username,
            email_solicitante=user.email,
            tipo_solicitado=perfil.tipo,
        )

        # Deletar o usuário apaga o Perfil em cascata (CASCADE)
        username = user.username
        user.delete()

        messages.warning(
            request,
            f'Solicitação de "{username}" negada e dados removidos.'
        )

    return redirect('painel')


@login_required
def agendamentos(request):
    if not hasattr(request.user, 'perfil') or request.user.perfil.tipo != 'PROFESSOR' or not request.user.perfil.aprovado:
        return redirect('home')
    return render(request, 'app/agendamentos.html', {'title': 'Meus Agendamentos'})


def about(request):
    return render(request, 'app/about.html', {'title': 'Sobre o LabHub'})


def contact(request):
    return render(request, 'app/contact.html', {'title': 'Contato'})