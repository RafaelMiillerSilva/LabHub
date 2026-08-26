"""
Views das páginas institucionais e tela inicial (Home/Dashboard).
"""

from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from app.forms import BootstrapAuthenticationForm, CadastroForm
from app.models import Agendamento, Perfil
from .common import (
    DIAS_SEMANA_LONGO,
    MESES_PT,
    is_admin_aprovado,
    is_usuario_aprovado,
)


def _home_dashboard(request):
    """View do painel/dashboard dentro de app/index.html (Visão Semanal)."""
    hoje = date.today()

    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
        dia = int(request.GET.get('dia', hoje.day))
        data_atual = date(ano, mes, dia)
    except ValueError:
        try:
            data_atual = date(ano, mes, 1)
        except ValueError:
            data_atual = hoje

    # Encontrar o domingo da semana atual
    dias_para_domingo = data_atual.isoweekday() % 7
    domingo = data_atual - timedelta(days=dias_para_domingo)
    sabado = domingo + timedelta(days=6)

    semana_ant = domingo - timedelta(days=7)
    semana_prox = domingo + timedelta(days=7)

    is_admin = request.user.is_staff or is_admin_aprovado(request.user)

    reservas_qs = (
        Agendamento.objects.filter(data__range=(domingo, sabado))
        .select_related('sala', 'turma', 'professor')
        .prefetch_related('itens')
    )

    dias_cabecalho = []
    for i in range(7):
        d = domingo + timedelta(days=i)
        dias_cabecalho.append({
            'data': d,
            'numero': d.day,
            'mes_nome': MESES_PT[d.month - 1][:3],
            'nome_curto': DIAS_SEMANA_LONGO[d.weekday()][:3],
            'hoje': d == hoje
        })

    grade_semanal = []
    for aula in range(1, 10):
        linha = []
        for i in range(7):
            d = domingo + timedelta(days=i)
            # Reservas no slot
            reservas_slot = [r for r in reservas_qs if r.data == d and r.aula == aula]
            
            tem_reserva_usuario = any(r.professor == request.user for r in reservas_slot)
            
            linha.append({
                'data': d,
                'reservas': reservas_slot,
                'tem_reserva_usuario': tem_reserva_usuario
            })
        grade_semanal.append({'aula': aula, 'dias': linha})

    context = {
        'dashboard': True,
        'data_atual': data_atual,
        'semana_ant': semana_ant,
        'semana_prox': semana_prox,
        'domingo': domingo,
        'sabado': sabado,
        'hoje_ano': hoje.year,
        'hoje_mes': hoje.month,
        'hoje_dia': hoje.day,
        'is_admin': is_admin,
        'solicitacoes_pendentes': Perfil.objects.filter(aprovado=False).count(),
        'dias_cabecalho': dias_cabecalho,
        'grade_semanal': grade_semanal,
    }
    return render(request, 'app/index.html', context)


def home(request):
    """Página inicial com autenticação para visitantes ou dashboard para usuários aprovados."""
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil') and request.user.perfil.aprovado:
            return _home_dashboard(request)
        return render(request, 'app/index.html', {
            'form_login': BootstrapAuthenticationForm(),
            'form_cadastro': CadastroForm(),
            'msg_pendente': True,
            'aba_ativa': 'login'
        })

    form_login = BootstrapAuthenticationForm()
    form_cadastro = CadastroForm()
    aba_ativa = 'login'

    if request.method == 'POST':
        if 'btn_login' in request.POST:
            aba_ativa = 'login'
            form_login = BootstrapAuthenticationForm(data=request.POST)
            if form_login.is_valid():
                user = form_login.get_user()
                if hasattr(user, 'perfil') and user.perfil.aprovado:
                    login(request, user)
                    return redirect('home')
                else:
                    return render(request, 'app/index.html', {
                        'form_login': form_login,
                        'form_cadastro': form_cadastro,
                        'msg_pendente': True,
                        'aba_ativa': aba_ativa
                    })

        elif 'btn_cadastro' in request.POST:
            aba_ativa = 'cadastro'
            form_cadastro = CadastroForm(request.POST)
            if form_cadastro.is_valid():
                user = form_cadastro.save()

                if not hasattr(user, 'perfil'):
                    tipo_conta = form_cadastro.cleaned_data.get('tipo', 'PROFESSOR')
                    Perfil.objects.create(user=user, tipo=tipo_conta, aprovado=False)
                else:
                    user.perfil.aprovado = False
                    user.perfil.save()

                messages.success(
                    request,
                    'Solicitação enviada com sucesso! Aguarde a aprovação do administrador.'
                )

                return render(request, 'app/index.html', {
                    'form_login': BootstrapAuthenticationForm(),
                    'form_cadastro': CadastroForm(),
                    'msg_sucesso_cadastro': True,
                    'msg_pendente': True,
                    'aba_ativa': aba_ativa
                })

    return render(request, 'app/index.html', {
        'form_login': form_login,
        'form_cadastro': form_cadastro,
        'aba_ativa': aba_ativa,
        'title': 'Bem-vindo ao LabHub'
    })


def about(request):
    """Página Sobre."""
    return render(request, 'app/about.html', {'title': 'Sobre o LabHub'})


def contact(request):
    """Página de Contato."""
    return render(request, 'app/contact.html', {'title': 'Contato'})
