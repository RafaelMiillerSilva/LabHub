"""
Views das páginas institucionais e tela inicial (Home/Dashboard).
"""

from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from app.forms import BootstrapAuthenticationForm, CadastroForm
from app.models import Agendamento, Perfil, Sala
from .common import (
    DIAS_SEMANA_LONGO,
    MESES_PT,
    is_admin_aprovado,
    is_usuario_aprovado,
)


def _home_dashboard(request):
    """View do painel/dashboard diário dentro de app/index.html."""
    hoje = date.today()

    data_param = request.GET.get('data')
    if data_param:
        try:
            data_atual = date.fromisoformat(data_param)
        except ValueError:
            data_atual = hoje
    else:
        try:
            ano = int(request.GET.get('ano', hoje.year))
            mes = int(request.GET.get('mes', hoje.month))
            dia = int(request.GET.get('dia', hoje.day))
            data_atual = date(ano, mes, dia)
        except (TypeError, ValueError):
            data_atual = hoje

    dia_ant = data_atual - timedelta(days=1)
    dia_prox = data_atual + timedelta(days=1)
    is_hoje = (data_atual == hoje)

    is_admin = request.user.is_staff or is_admin_aprovado(request.user)

    salas = list(Sala.objects.filter(ativo=True).order_by('nome'))

    reservas_dia = list(
        Agendamento.objects.filter(data=data_atual)
        .select_related('sala', 'turma', 'professor')
        .prefetch_related('itens')
    )

    # Mapear reservas de salas por (aula, sala_id)
    reservas_sala = {}
    for r in reservas_dia:
        if r.tipo == 'SALA' and r.sala_id:
            reservas_sala[(r.aula, r.sala_id)] = r

    # Mapear reservas de dispositivos por aula
    reservas_disp = {aula: [] for aula in range(1, 10)}
    for r in reservas_dia:
        if r.tipo == 'DISPOSITIVO':
            reservas_disp[r.aula].append(r)

    # Identificar células a pular por causa de rowspan=2 (aulas seguidas iguais)
    skip_salas = {s.id: set() for s in salas}
    skip_disp = set()

    grade_diaria = []

    for aula in range(1, 10):
        colunas_salas = []
        for s in salas:
            if aula in skip_salas[s.id]:
                colunas_salas.append({
                    'sala': s,
                    'skip': True,
                })
            else:
                r = reservas_sala.get((aula, s.id))
                if r is None:
                    colunas_salas.append({
                        'sala': s,
                        'reserva': None,
                        'rowspan': 1,
                        'skip': False,
                        'dupla': False,
                        'aula': aula,
                    })
                else:
                    # Verificar se a próxima aula (aula + 1) é idêntica para agrupar em 2 linhas
                    r_prox = reservas_sala.get((aula + 1, s.id)) if aula < 9 else None
                    if (
                        r_prox is not None
                        and r_prox.professor_id == r.professor_id
                        and r_prox.turma_id == r.turma_id
                    ):
                        colunas_salas.append({
                            'sala': s,
                            'reserva': r,
                            'reserva_segunda': r_prox,
                            'rowspan': 2,
                            'skip': False,
                            'dupla': True,
                            'aula': aula,
                            'aula_fim': aula + 1,
                        })
                        skip_salas[s.id].add(aula + 1)
                    else:
                        colunas_salas.append({
                            'sala': s,
                            'reserva': r,
                            'rowspan': 1,
                            'skip': False,
                            'dupla': False,
                            'aula': aula,
                        })

        # Coluna de Equipamentos
        if aula in skip_disp:
            coluna_equip = {'skip': True}
        else:
            disp_list = reservas_disp.get(aula, [])
            if len(disp_list) == 1 and aula < 9:
                r = disp_list[0]
                disp_prox = reservas_disp.get(aula + 1, [])
                if len(disp_prox) == 1:
                    r_prox = disp_prox[0]
                    if (
                        r_prox.professor_id == r.professor_id
                        and r_prox.turma_id == r.turma_id
                    ):
                        # Conferir se itens de equipamentos são iguais
                        itens_r = sorted([(it.categoria, it.quantidade) for it in r.itens.all()])
                        itens_prox = sorted([(it.categoria, it.quantidade) for it in r_prox.itens.all()])
                        if itens_r == itens_prox:
                            coluna_equip = {
                                'reservas': [r],
                                'reserva_segunda': r_prox,
                                'rowspan': 2,
                                'skip': False,
                                'dupla': True,
                                'aula': aula,
                                'aula_fim': aula + 1,
                            }
                            skip_disp.add(aula + 1)
                        else:
                            coluna_equip = {
                                'reservas': disp_list,
                                'rowspan': 1,
                                'skip': False,
                                'dupla': False,
                                'aula': aula,
                            }
                    else:
                        coluna_equip = {
                            'reservas': disp_list,
                            'rowspan': 1,
                            'skip': False,
                            'dupla': False,
                            'aula': aula,
                        }
                else:
                    coluna_equip = {
                        'reservas': disp_list,
                        'rowspan': 1,
                        'skip': False,
                        'dupla': False,
                        'aula': aula,
                    }
            else:
                coluna_equip = {
                    'reservas': disp_list,
                    'rowspan': 1,
                    'skip': False,
                    'dupla': False,
                    'aula': aula,
                }

        grade_diaria.append({
            'aula': aula,
            'colunas_salas': colunas_salas,
            'coluna_equip': coluna_equip,
        })

    dia_semana_hoje = DIAS_SEMANA_LONGO[hoje.weekday()]
    mes_nome_hoje = MESES_PT[hoje.month - 1]
    data_dia_semana = DIAS_SEMANA_LONGO[data_atual.weekday()]
    data_mes_nome = MESES_PT[data_atual.month - 1]

    total_sala = Agendamento.objects.filter(data=hoje, tipo='SALA').count()
    total_disp = Agendamento.objects.filter(data=hoje, tipo='DISPOSITIVO').count()

    context = {
        'dashboard': True,
        'data_atual': data_atual,
        'dia_ant': dia_ant,
        'dia_prox': dia_prox,
        'is_hoje': is_hoje,
        'hoje_ano': hoje.year,
        'hoje_mes': hoje.month,
        'hoje_dia': hoje.day,
        'dia_semana': dia_semana_hoje,
        'mes_nome': mes_nome_hoje,
        'data_dia_semana': data_dia_semana,
        'data_mes_nome': data_mes_nome,
        'total_sala': total_sala,
        'total_disp': total_disp,
        'is_admin': is_admin,
        'solicitacoes_pendentes': Perfil.objects.filter(aprovado=False).count(),
        'salas': salas,
        'grade_diaria': grade_diaria,
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

