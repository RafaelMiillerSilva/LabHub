import calendar
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .forms import (
    AlunoForm,
    BootstrapAuthenticationForm,
    CadastroForm,
    EquipamentoForm,
    SalaForm,
    TurmaForm,
)
from .models import (
    Agendamento,
    Aluno,
    Equipamento,
    HistoricoAcao,
    ItemDispositivo,
    PedidoRedefinicaoSenha,
    Perfil,
    RelacaoAlunoEquipamento,
    Sala,
    Turma,
)


# ---------------------------------------------------------------------------
# Constantes de apoio (português)
# ---------------------------------------------------------------------------
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


def _is_usuario_aprovado(user):
    """Verifica se o usuário está autenticado e tem perfil aprovado."""
    return hasattr(user, 'perfil') and user.perfil.aprovado


def _is_admin_aprovado(user):
    """Verifica se o usuário é administrador e aprovado."""
    return (
        hasattr(user, 'perfil')
        and user.perfil.tipo == 'ADMINISTRADOR'
        and user.perfil.aprovado
    )


def _home_dashboard(request):
    """View do painel/dashboard dentro de app/index.html."""
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

    dia_ant = data_atual - timedelta(days=1)
    dia_prox = data_atual + timedelta(days=1)
    
    mes_ant = data_atual.month - 1
    ano_mes_ant = data_atual.year
    if mes_ant < 1:
        mes_ant = 12
        ano_mes_ant -= 1
        
    mes_prox = data_atual.month + 1
    ano_mes_prox = data_atual.year
    if mes_prox > 12:
        mes_prox = 1
        ano_mes_prox += 1
        
    ano_ant = data_atual.year - 1
    ano_prox = data_atual.year + 1

    meses = MESES_PT
    dias_semana = DIAS_SEMANA_LONGO

    is_admin = request.user.is_staff or _is_admin_aprovado(request.user)

    reservas_dia = (
        Agendamento.objects.filter(data=data_atual)
        .select_related('sala', 'turma', 'professor')
        .prefetch_related('itens')
        .order_by('aula')
    )
    
    context = {
        'dashboard': True,
        'data_atual': data_atual,
        'dia_ant': dia_ant, 'dia_prox': dia_prox,
        'mes_ant': mes_ant, 'ano_mes_ant': ano_mes_ant,
        'mes_prox': mes_prox, 'ano_mes_prox': ano_mes_prox,
        'ano_ant': ano_ant, 'ano_prox': ano_prox,
        'hoje_ano': hoje.year,
        'hoje_mes': hoje.month,
        'hoje_dia': hoje.day,
        'mes_nome': meses[data_atual.month - 1],
        'dia_semana': dias_semana[data_atual.weekday()],
        'is_admin': is_admin,
        'solicitacoes_pendentes': Perfil.objects.filter(aprovado=False).count(),
        'reservas_dia': reservas_dia,
        'total_reservas': reservas_dia.count(),
    }
    return render(request, 'app/index.html', context)


def home(request):
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

                messages.success(request, 'Solicitação enviada com sucesso! Aguarde a aprovação do administrador.')

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


@login_required
def painel(request):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    aba = request.GET.get('tab', 'solicitacoes')
    q = request.GET.get('q', '').strip()
    de = request.GET.get('de', '').strip()
    ate = request.GET.get('ate', '').strip()

    solicitacoes = Perfil.objects.filter(aprovado=False).select_related('user')

    pedidos_senha = (PedidoRedefinicaoSenha.objects.filter(atendido=False)
                     .select_related('user', 'user__perfil'))

    usuarios = (Perfil.objects.filter(aprovado=True)
                .select_related('user')
                .order_by('tipo', 'user__username'))
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


def esqueci_senha(request):
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
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        pedido = get_object_or_404(PedidoRedefinicaoSenha, id=pedido_id, atendido=False)
        nova = request.POST.get('nova_senha', '')

        if len(nova) < 6:
            messages.warning(request, 'A nova senha deve ter pelo menos 6 caracteres.')
            return redirect('painel')

        u = pedido.user
        u.set_password(nova)
        u.save()

        pedido.atendido = True
        pedido.atendido_em = timezone.now()
        pedido.atendido_por = request.user
        pedido.save()

        HistoricoAcao.objects.create(
            admin=request.user,
            acao='REDEFINIDO',
            username_solicitante=u.username,
            email_solicitante=u.email,
            tipo_solicitado=u.perfil.tipo if hasattr(u, 'perfil') else '',
        )

        messages.success(
            request,
            f'Senha de "{u.username}" redefinida. Informe a nova senha ao usuário.'
        )

    return redirect('painel')


@login_required
def cancelar_redefinicao_senha_admin(request, pedido_id):
    """Cancela um pedido de redefinicao de senha pendente."""
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        pedido = get_object_or_404(PedidoRedefinicaoSenha, id=pedido_id, atendido=False)
        u = pedido.user

        HistoricoAcao.objects.create(
            admin=request.user,
            acao='SENHA_CANCELADA',
            username_solicitante=u.username,
            email_solicitante=u.email,
            tipo_solicitado=u.perfil.tipo if hasattr(u, 'perfil') else '',
        )

        pedido.delete()
        messages.warning(request, f'Pedido de redefinição de senha para "{u.username}" foi cancelado.')

    return redirect('painel')


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _linha_usuario_html(request, perfil):
    return render_to_string(
        'app/_usuario_linha.html',
        {'u': perfil, 'user': request.user},
        request=request,
    )


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

        pendentes = Perfil.objects.filter(aprovado=False).count()
        msg = f'Usuário "{perfil.user.username}" aprovado com sucesso!'
        if _is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'aprovar', 'message': msg,
                'perfil_id': perfil.id, 'pendentes': pendentes,
                'html': _linha_usuario_html(request, perfil),
            })
        messages.success(request, msg)

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

        username = user.username
        user.delete()

        pendentes = Perfil.objects.filter(aprovado=False).count()
        msg = f'Solicitação de "{username}" negada e dados removidos.'
        if _is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'negar', 'message': msg,
                'perfil_id': perfil_id, 'pendentes': pendentes,
            })
        messages.warning(request, msg)

    return redirect('painel')


def _admins_ativos_qs():
    return Perfil.objects.filter(
        tipo='ADMINISTRADOR', aprovado=True, user__is_active=True
    )


@login_required
def usuario_toggle_ativo(request, user_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        alvo = get_object_or_404(User, id=user_id)

        if alvo.id == request.user.id:
            msg = 'Você não pode desativar a sua própria conta.'
            if _is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        eh_admin = hasattr(alvo, 'perfil') and alvo.perfil.tipo == 'ADMINISTRADOR'
        if alvo.is_active and eh_admin and _admins_ativos_qs().count() <= 1:
            msg = 'Não é possível desativar o último administrador ativo.'
            if _is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        alvo.is_active = not alvo.is_active
        alvo.save(update_fields=['is_active'])

        HistoricoAcao.objects.create(
            admin=request.user,
            acao='ATIVADO' if alvo.is_active else 'DESATIVADO',
            username_solicitante=alvo.username,
            email_solicitante=alvo.email,
            tipo_solicitado=alvo.perfil.tipo if hasattr(alvo, 'perfil') else '',
        )

        estado = 'ativada' if alvo.is_active else 'desativada'
        msg = f'Conta de "{alvo.username}" {estado} com sucesso.'
        if _is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'atualizar_usuario', 'message': msg,
                'user_id': alvo.id, 'html': _linha_usuario_html(request, alvo.perfil),
            })
        messages.success(request, msg)

    return redirect('painel')


@login_required
def usuario_toggle_tipo(request, user_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        alvo = get_object_or_404(User, id=user_id)
        perfil = alvo.perfil

        if alvo.id == request.user.id:
            msg = 'Você não pode alterar o seu próprio nível de acesso.'
            if _is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        virando_professor = perfil.tipo == 'ADMINISTRADOR'
        if virando_professor and _admins_ativos_qs().count() <= 1:
            msg = 'Não é possível rebaixar o último administrador ativo.'
            if _is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.warning(request, msg)
            return redirect('painel')

        perfil.tipo = 'PROFESSOR' if virando_professor else 'ADMINISTRADOR'
        perfil.save(update_fields=['tipo'])

        HistoricoAcao.objects.create(
            admin=request.user,
            acao='REBAIXADO' if virando_professor else 'PROMOVIDO',
            username_solicitante=alvo.username,
            email_solicitante=alvo.email,
            tipo_solicitado=perfil.tipo,
        )

        novo = 'administrador' if perfil.tipo == 'ADMINISTRADOR' else 'professor'
        msg = f'"{alvo.username}" agora é {novo}.'
        if _is_ajax(request):
            return JsonResponse({
                'ok': True, 'acao': 'atualizar_usuario', 'message': msg,
                'user_id': alvo.id, 'html': _linha_usuario_html(request, alvo.perfil),
            })
        messages.success(request, msg)

    return redirect('painel')


# ---------------------------------------------------------------------------
# CALENDÁRIO DE AGENDAMENTOS
# ---------------------------------------------------------------------------
@login_required
def agendamentos(request):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    hoje = date.today()

    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
        dia = int(request.GET.get('dia', hoje.day))
        data_atual = date(ano, mes, dia)
    except (TypeError, ValueError):
        ano, mes, dia = hoje.year, hoje.month, hoje.day
        data_atual = hoje

    if not (1 <= mes <= 12):
        mes = hoje.month

    dia_ant = data_atual - timedelta(days=1)
    dia_prox = data_atual + timedelta(days=1)

    mes_ant = data_atual.month - 1
    ano_mes_ant = data_atual.year
    if mes_ant < 1:
        mes_ant = 12
        ano_mes_ant -= 1

    mes_prox = data_atual.month + 1
    ano_mes_prox = data_atual.year
    if mes_prox > 12:
        mes_prox = 1
        ano_mes_prox += 1

    ano_ant = data_atual.year - 1
    ano_prox = data_atual.year + 1

    cal = calendar.Calendar(firstweekday=6)
    semanas = []
    for semana in cal.monthdayscalendar(ano, mes):
        linha = []
        for d in semana:
            if d == 0:
                linha.append(None)
            else:
                dia_data = date(ano, mes, d)
                linha.append({
                    'numero': d,
                    'hoje': (dia_data == hoje),
                    'passado': (dia_data < hoje),
                })
        semanas.append(linha)

    minhas_reservas = (
        Agendamento.objects
        .filter(data=data_atual)
        .select_related('sala', 'turma', 'professor')
        .prefetch_related('itens')
        .order_by('aula')
    )

    context = {
        'title': 'Agendamentos',
        'data_atual': data_atual,
        'ano': ano,
        'mes': mes,
        'dia': dia,
        'mes_nome': MESES_PT[mes - 1],
        'dias_semana': DIAS_SEMANA_PT,
        'semanas': semanas,
        'dia_ant': dia_ant, 'dia_prox': dia_prox,
        'mes_ant': mes_ant, 'ano_mes_ant': ano_mes_ant,
        'mes_prox': mes_prox, 'ano_mes_prox': ano_mes_prox,
        'ano_ant': ano_ant, 'ano_prox': ano_prox,
        'hoje_ano': hoje.year, 
        'hoje_mes': hoje.month, 
        'hoje_dia': hoje.day, 
        'lista_meses': list(enumerate(MESES_PT, start=1)),
        'lista_anos': range(hoje.year - 2, hoje.year + 4),
        'is_admin': _is_admin_aprovado(request.user),
        'minhas_reservas': minhas_reservas,
    }
    return render(request, 'app/agendamentos.html', context)


# ---------------------------------------------------------------------------
# DETALHE DO DIA E PROCESSAMENTO DE RESERVAS
# ---------------------------------------------------------------------------
def _resolver_professor(request):
    is_admin = _is_admin_aprovado(request.user)
    prof_id = request.POST.get('professor')
    if is_admin and prof_id:
        prof = User.objects.filter(id=prof_id).first()
        if prof:
            return prof
    return request.user


def _professores_aprovados():
    return User.objects.filter(perfil__aprovado=True).order_by('username')


def _processar_agendamento_sala(request, data, ano, mes, dia):
    turma_id = request.POST.get('turma')
    selecionadas = request.POST.getlist('reserva')
    observacao = request.POST.get('observacao', '').strip()

    if not turma_id:
        messages.warning(request, 'Escolha a turma antes de agendar.')
        return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)
    if not selecionadas:
        messages.warning(request, 'Selecione pelo menos uma sala disponível.')
        return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)

    turma = get_object_or_404(Turma, id=turma_id)
    professor = _resolver_professor(request)
    criados = 0
    conflitos = 0

    for item in selecionadas:
        try:
            aula_str, sala_str = item.split(':')
            aula = int(aula_str)
            sala_id = int(sala_str)
        except (ValueError, AttributeError):
            continue

        ja_existe = Agendamento.objects.filter(
            data=data, aula=aula, tipo='SALA', sala_id=sala_id
        ).exists()
        if ja_existe:
            conflitos += 1
            continue

        Agendamento.objects.create(
            data=data, aula=aula, tipo='SALA',
            professor=professor, turma=turma,
            sala_id=sala_id, observacao=observacao,
        )
        criados += 1

    if criados:
        HistoricoAcao.objects.create(
            admin=request.user,
            acao='AGENDOU',
            username_solicitante=professor.username,
            email_solicitante=professor.email,
            tipo_solicitado=professor.perfil.tipo if hasattr(professor, 'perfil') else '',
        )
        messages.success(
            request,
            f'{criados} reserva(s) de sala realizada(s) para {data:%d/%m/%Y}.'
        )
    if conflitos:
        messages.warning(
            request,
            f'{conflitos} sala(s) já tinham sido reservadas nesse meio tempo e foram ignoradas.'
        )
    return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)


def _disponibilidade_dispositivos(data):
    linhas = (
        ItemDispositivo.objects
        .filter(agendamento__data=data, agendamento__tipo='DISPOSITIVO')
        .values('agendamento__aula', 'categoria')
        .annotate(total=Sum('quantidade'))
    )
    return {(l['agendamento__aula'], l['categoria']): l['total'] for l in linhas}


def _estoque_por_categoria():
    linhas = (
        Equipamento.objects
        .filter(status='ATIVO')
        .values('categoria')
        .annotate(n=Count('id'))
    )
    return {l['categoria']: l['n'] for l in linhas}


def _processar_agendamento_dispositivo(request, data, ano, mes, dia):
    turma_id = request.POST.get('turma')
    observacao = request.POST.get('observacao', '').strip()

    if not turma_id:
        messages.warning(request, 'Escolha a turma antes de agendar.')
        return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)

    selecao = defaultdict(dict)
    for chave, valor in request.POST.items():
        if not chave.startswith('qtd_'):
            continue
        try:
            _, aula_str, categoria = chave.split('_')
            qtd = int(valor)
        except (ValueError, AttributeError):
            continue
        if qtd > 0:
            selecao[int(aula_str)][categoria] = qtd

    if not selecao:
        messages.warning(request, 'Arraste pelo menos um slider para reservar algum equipamento.')
        return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)

    turma = get_object_or_404(Turma, id=turma_id)
    professor = _resolver_professor(request)
    reservado = _disponibilidade_dispositivos(data)
    estoque = _estoque_por_categoria()

    aulas_agendadas = 0
    ajustes = 0

    for aula, itens in selecao.items():
        itens_validos = []
        for categoria, qtd in itens.items():
            total = estoque.get(categoria, 0)
            disponivel = total - reservado.get((aula, categoria), 0)
            if disponivel <= 0:
                ajustes += 1
                continue
            usar = min(qtd, disponivel)
            if usar < qtd:
                ajustes += 1
            itens_validos.append((categoria, usar))

        if not itens_validos:
            continue

        agendamento = Agendamento.objects.create(
            data=data, aula=aula, tipo='DISPOSITIVO',
            professor=professor, turma=turma,
            sala=None, observacao=observacao,
        )
        for categoria, usar in itens_validos:
            ItemDispositivo.objects.create(
                agendamento=agendamento, categoria=categoria, quantidade=usar
            )
            reservado[(aula, categoria)] = reservado.get((aula, categoria), 0) + usar
        aulas_agendadas += 1

    if aulas_agendadas:
        HistoricoAcao.objects.create(
            admin=request.user,
            acao='AGENDOU',
            username_solicitante=professor.username,
            email_solicitante=professor.email,
            tipo_solicitado=professor.perfil.tipo if hasattr(professor, 'perfil') else '',
        )
        messages.success(
            request,
            f'Equipamentos reservados em {aulas_agendadas} aula(s) no dia {data:%d/%m/%Y}.'
        )
    if ajustes:
        messages.warning(
            request,
            f'{ajustes} item(ns) reduzido(s) ou ignorado(s) por falta de estoque disponível.'
        )
    if not aulas_agendadas:
        messages.warning(request, 'Nenhum equipamento pôde ser reservado (estoque esgotado).')
    return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)


@login_required
def agendamento_detalhe(request, ano, mes, dia):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    try:
        data = date(ano, mes, dia)
    except ValueError:
        messages.error(request, 'Data inválida.')
        return redirect('agendamentos')

    is_admin = _is_admin_aprovado(request.user)
    if data < date.today() and not is_admin:
        messages.warning(
            request,
            f'{data:%d/%m/%Y} é uma data passada — não é possível agendar.'
        )
        return redirect('agendamentos')

    if request.method == 'POST':
        if request.POST.get('tipo') == 'sala':
            return _processar_agendamento_sala(request, data, ano, mes, dia)
        if request.POST.get('tipo') == 'dispositivo':
            return _processar_agendamento_dispositivo(request, data, ano, mes, dia)
        return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)

    salas_ativas = list(Sala.objects.filter(ativo=True))

    reservas = (
        Agendamento.objects
        .filter(data=data, tipo='SALA')
        .select_related('sala', 'turma', 'professor')
    )
    ocupacao = {(r.aula, r.sala_id): r for r in reservas}

    aulas = []
    for numero, (nome, horario) in enumerate(AULAS_HORARIOS, start=1):
        linha_salas = []
        livres = 0
        for sala in salas_ativas:
            reserva = ocupacao.get((numero, sala.id))
            if reserva:
                prof = reserva.professor.get_full_name() or reserva.professor.username
                linha_salas.append({
                    'sala': sala, 'ocupado': True,
                    'turma': reserva.turma.nome, 'professor': prof,
                    'ag_id': reserva.id,
                })
            else:
                linha_salas.append({'sala': sala, 'ocupado': False})
                livres += 1
        aulas.append({
            'numero': numero, 'nome': nome, 'horario': horario,
            'salas': linha_salas, 'livres': livres, 'total': len(salas_ativas),
        })

    estoque_categoria = _estoque_por_categoria()
    reservado_disp = _disponibilidade_dispositivos(data)

    ags_disp = (
        Agendamento.objects
        .filter(data=data, tipo='DISPOSITIVO')
        .select_related('turma', 'professor')
        .prefetch_related('itens')
        .order_by('aula')
    )
    cards_por_aula = defaultdict(list)
    for ag in ags_disp:
        cards_por_aula[ag.aula].append(ag)

    aulas_disp = []
    for numero, (nome, horario) in enumerate(AULAS_HORARIOS, start=1):
        grupos = []
        for cat_valor, cat_label in Equipamento.CATEGORIA_CHOICES:
            total = estoque_categoria.get(cat_valor, 0)
            if total == 0:
                continue
            restante = max(total - reservado_disp.get((numero, cat_valor), 0), 0)
            ratio = restante / total if total else 0
            if restante == 0:
                status = 'vermelho'
            elif ratio <= 0.5:
                status = 'laranja'
            else:
                status = 'verde'
            grupos.append({
                'categoria': cat_valor, 'label': cat_label,
                'restante': restante, 'total': total, 'status': status,
            })
        aulas_disp.append({
            'numero': numero, 'nome': nome, 'horario': horario,
            'grupos': grupos,
            'cards': cards_por_aula.get(numero, []),
        })

    context = {
        'title': f'Agendamento {data:%d/%m/%Y}',
        'data': data,
        'ano': ano, 'mes': mes, 'dia': dia,
        'dia_semana': DIAS_SEMANA_LONGO[data.weekday()],
        'mes_nome': MESES_PT[mes - 1],
        'aulas': aulas,
        'aulas_disp': aulas_disp,
        'turmas': Turma.objects.all(),
        'tem_salas': bool(salas_ativas),
        'tem_equipamentos': bool(estoque_categoria),
        'is_admin': is_admin,
        'professores': _professores_aprovados() if is_admin else None,
    }
    return render(request, 'app/agendamento_detalhe.html', context)


# ---------------------------------------------------------------------------
# CADASTRO E VISUALIZAÇÃO DE SALAS
# ---------------------------------------------------------------------------
@login_required
def salas(request):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = _is_admin_aprovado(request.user)

    instancia = None
    editar_id = request.GET.get('editar')
    if editar_id:
        if not is_admin:
            messages.error(request, 'Apenas administradores podem editar salas.')
            return redirect('salas')
        instancia = Sala.objects.filter(id=editar_id).first()

    if request.method == 'POST':
        if not is_admin:
            messages.error(request, 'Apenas administradores podem cadastrar ou editar salas.')
            return redirect('salas')

        post_id = request.POST.get('sala_id')
        if post_id:
            instancia = get_object_or_404(Sala, id=post_id)
        form = SalaForm(request.POST, instance=instancia)
        if form.is_valid():
            sala = form.save()
            if post_id:
                messages.success(request, f'Sala "{sala.nome}" atualizada com sucesso!')
            else:
                messages.success(request, f'Sala "{sala.nome}" cadastrada com sucesso!')
            return redirect('salas')
    else:
        form = SalaForm(instance=instancia)

    return render(request, 'app/salas.html', {
        'title': 'Salas de Aula',
        'form': form if is_admin else None,
        'salas': Sala.objects.all(),
        'editando': instancia,
        'is_admin': is_admin,
    })


@login_required
def sala_excluir(request, sala_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        sala = get_object_or_404(Sala, id=sala_id)
        nome = sala.nome
        sala.delete()
        msg = f'Sala "{nome}" removida.'

        if _is_ajax(request):
            restantes = Sala.objects.count()
            return JsonResponse({
                'ok': True, 'acao': 'remover_linha', 'message': msg,
                'restantes': restantes,
                'contador': {'seletor': '#cont-salas', 'valor': restantes},
                'vazio_html': '<tr><td colspan="5" class="text-center text-muted" '
                              'style="padding: 30px;"><em>Nenhuma sala cadastrada ainda. '
                              'Cadastre a primeira ao lado.</em></td></tr>',
            })
        messages.warning(request, msg)

    return redirect('salas')


# ---------------------------------------------------------------------------
# EQUIPAMENTOS - Visualização para professores e edição restrita a admins
# ---------------------------------------------------------------------------
@login_required
def equipamentos(request):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = _is_admin_aprovado(request.user)
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()
    lista = Equipamento.objects.defer('foto_dados').select_related('sala')
    if q:
        lista = lista.filter(apelido__icontains=q)
    if cat:
        lista = lista.filter(categoria=cat)

    return render(request, 'app/equipamentos.html', {
        'title': 'Equipamentos',
        'equipamentos': lista,
        'total': lista.count(),
        'q': q,
        'cat': cat,
        'categorias': Equipamento.CATEGORIA_CHOICES,
        'is_admin': is_admin,
    })


@login_required
def equipamento_form(request, equip_id=None):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    instancia = get_object_or_404(Equipamento, id=equip_id) if equip_id else None

    if request.method == 'POST':
        form = EquipamentoForm(request.POST, request.FILES, instance=instancia)
        if form.is_valid():
            equip = form.save()
            if instancia:
                messages.success(request, f'Equipamento "{equip.apelido}" atualizado com sucesso!')
            else:
                messages.success(request, f'Equipamento "{equip.apelido}" cadastrado com sucesso!')
            return redirect('equipamentos')
    else:
        form = EquipamentoForm(instance=instancia)

    return render(request, 'app/equipamento_form.html', {
        'title': 'Editar Equipamento' if instancia else 'Cadastrar Equipamento',
        'form': form,
        'editando': instancia,
        'categorias_com_chip': list(Equipamento.CATEGORIAS_COM_CHIP),
    })


@login_required
def equipamento_editar(request, pk=None):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if pk:
        equipamento = get_object_or_404(Equipamento, pk=pk)
    else:
        equipamento = None

    # Captura os filtros atuais da URL (seja via GET ao abrir ou QueryString ao enviar)
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()

    if request.method == 'POST':
        form = EquipamentoForm(request.POST, request.FILES, instance=equipamento)
        if form.is_valid():
            equip = form.save()
            if equipamento:
                messages.success(request, f'Equipamento "{equip.apelido}" atualizado com sucesso!')
            else:
                messages.success(request, f'Equipamento "{equip.apelido}" cadastrado com sucesso!')

            # Redireciona mantendo os parâmetros de busca
            base_url = reverse('equipamentos')
            query_params = {}
            if q:
                query_params['q'] = q
            if cat:
                query_params['cat'] = cat

            if query_params:
                redirect_url = f'{base_url}?{urlencode(query_params)}'
            else:
                redirect_url = base_url

            return redirect(redirect_url)
    else:
        form = EquipamentoForm(instance=equipamento)

    context = {
        'title': 'Editar Equipamento' if equipamento else 'Cadastrar Equipamento',
        'form': form,
        'editando': equipamento,
        'q': q,
        'cat': cat,
        'categorias_com_chip': list(Equipamento.CATEGORIAS_COM_CHIP),
    }
    return render(request, 'app/equipamento_form.html', context)


@login_required
def foto_equipamento(request, equip_id):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    equip = get_object_or_404(Equipamento, id=equip_id)
    if not equip.foto_dados:
        raise Http404('Equipamento sem foto.')

    return HttpResponse(bytes(equip.foto_dados),
                        content_type=equip.foto_mime or 'image/jpeg')


@login_required
def equipamento_excluir(request, equip_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    # Captura os parâmetros para manter o filtro após excluir
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()

    if request.method == 'POST':
        equip = get_object_or_404(Equipamento, id=equip_id)
        apelido = equip.apelido
        equip.delete()
        messages.warning(request, f'Equipamento "{apelido}" removido.')

    base_url = reverse('equipamentos')
    query_params = {}
    if q:
        query_params['q'] = q
    if cat:
        query_params['cat'] = cat

    if query_params:
        return redirect(f'{base_url}?{urlencode(query_params)}')

    return redirect('equipamentos')


def _gerar_etiqueta_png(equip):
    from PIL import Image, ImageDraw, ImageFont

    W, H = 520, 300
    AZUL = (30, 60, 114)
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)

    def _fonte(tam, negrito=False):
        nomes = (['DejaVuSans-Bold.ttf', 'arialbd.ttf'] if negrito
                 else ['DejaVuSans.ttf', 'arial.ttf'])
        for nome in nomes:
            try:
                return ImageFont.truetype(nome, tam)
            except Exception:
                continue
        return ImageFont.load_default()

    d.rectangle([4, 4, W - 5, H - 5], outline=AZUL, width=4)
    d.rectangle([4, 4, W - 5, 58], fill=AZUL)
    d.text((20, 16), equip.apelido or '—', fill='white', font=_fonte(30, True))
    d.text((W - 200, 22), equip.get_categoria_display(), fill='white', font=_fonte(18, True))

    linhas = [
        f"Identificação: {equip.identificacao_escola or '—'}",
        f"Patrimônio: {equip.numero_patrimonio or '—'}",
        f"Nº de série: {equip.numero_serie or '—'}",
    ]
    if equip.fixo and equip.sala:
        linhas.append(f"Sala: {equip.sala.nome}")
    if equip.imei:
        linhas.append(f"IMEI: {equip.imei}")

    fonte = _fonte(20)
    y = 78
    for ln in linhas:
        d.text((24, y), ln, fill=(35, 35, 35), font=fonte)
        y += 34

    return img


@login_required
def etiqueta_equipamento(request, equip_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    equip = get_object_or_404(Equipamento, id=equip_id)
    img = _gerar_etiqueta_png(equip)

    response = HttpResponse(content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="etiqueta_{equip.apelido}.png"'
    img.save(response, 'PNG')
    return response


@login_required
def etiquetas_lote(request):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    ids = request.GET.getlist('ids')
    equips = list(Equipamento.objects.filter(id__in=ids))

    if not equips:
        messages.warning(request, 'Selecione pelo menos um equipamento para baixar a etiqueta.')
        return redirect('equipamentos')

    if len(equips) == 1:
        return etiqueta_equipamento(request, equips[0].id)

    import io
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for equip in equips:
            img = _gerar_etiqueta_png(equip)
            png_bytes = io.BytesIO()
            img.save(png_bytes, 'PNG')
            zf.writestr(f'etiqueta_{equip.apelido}.png', png_bytes.getvalue())
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="etiquetas.zip"'
    return response


@login_required
def exportar_equipamentos(request):
    """Exporta a lista de equipamentos filtrados para um arquivo CSV."""
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    import csv

    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()

    lista = Equipamento.objects.defer('foto_dados').select_related('sala')
    if q:
        lista = lista.filter(apelido__icontains=q)
    if cat:
        lista = lista.filter(categoria=cat)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="equipamentos.csv"'
    response.write('\ufeff')  # BOM para acentuação correta no Excel

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Apelido',
        'Categoria',
        'Fixo',
        'Sala',
        'Identificação Escola',
        'Nº Patrimônio',
        'Nº de Série',
        'IMEI',
        'Status',
    ])

    for equip in lista:
        writer.writerow([
            equip.apelido or '',
            equip.get_categoria_display() if hasattr(equip, 'get_categoria_display') else equip.categoria,
            'Sim' if equip.fixo else 'Não',
            equip.sala.nome if equip.fixo and equip.sala else '',
            equip.identificacao_escola or '',
            equip.numero_patrimonio or '',
            equip.numero_serie or '',
            equip.imei or '',
            getattr(equip, 'status', ''),
        ])

    return response


# ---------------------------------------------------------------------------
# CADASTRO E VISUALIZAÇÃO DE TURMAS E ALUNOS
# ---------------------------------------------------------------------------
@login_required
def turmas(request):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = _is_admin_aprovado(request.user)

    instancia = None
    editar_id = request.GET.get('editar')
    if editar_id:
        if not is_admin:
            messages.error(request, 'Apenas administradores podem editar turmas.')
            return redirect('turmas')
        instancia = Turma.objects.filter(id=editar_id).first()

    if request.method == 'POST':
        if not is_admin:
            messages.error(request, 'Apenas administradores podem cadastrar ou editar turmas.')
            return redirect('turmas')

        post_id = request.POST.get('turma_id')
        if post_id:
            instancia = get_object_or_404(Turma, id=post_id)
        form = TurmaForm(request.POST, instance=instancia)
        if form.is_valid():
            turma = form.save()
            if post_id:
                messages.success(request, f'Turma "{turma}" atualizada com sucesso!')
            else:
                messages.success(request, f'Turma "{turma}" cadastrada com sucesso!')
            return redirect('turmas')
    else:
        form = TurmaForm(instance=instancia)

    return render(request, 'app/turmas.html', {
        'title': 'Turmas',
        'form': form if is_admin else None,
        'turmas': Turma.objects.all(),
        'editando': instancia,
        'is_admin': is_admin,
    })


@login_required
def turma_excluir(request, turma_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        turma = get_object_or_404(Turma, id=turma_id)
        nome = str(turma)
        turma.delete()
        msg = f'Turma "{nome}" removida (junto com seus alunos).'

        if _is_ajax(request):
            restantes = Turma.objects.count()
            return JsonResponse({
                'ok': True, 'acao': 'remover_linha', 'message': msg,
                'restantes': restantes,
                'contador': {'seletor': '#cont-turmas', 'valor': restantes},
                'vazio_html': '<tr><td colspan="4" class="text-center text-muted" '
                              'style="padding: 30px;"><em>Nenhuma turma cadastrada ainda. '
                              'Cadastre a primeira ao lado.</em></td></tr>',
            })
        messages.warning(request, msg)

    return redirect('turmas')


@login_required
def turma_detalhe(request, turma_id):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = _is_admin_aprovado(request.user)
    turma = get_object_or_404(Turma, id=turma_id)

    if request.method == 'POST':
        if not is_admin:
            messages.error(request, 'Apenas administradores podem adicionar alunos.')
            return redirect('turma_detalhe', turma_id=turma.id)

        form = AlunoForm(request.POST)
        if form.is_valid():
            aluno = form.save(commit=False)
            aluno.turma = turma
            aluno.save()
            messages.success(request, f'Aluno "{aluno.nome}" adicionado à turma.')
            return redirect('turma_detalhe', turma_id=turma.id)
    else:
        form = AlunoForm()

    return render(request, 'app/turma_detalhe.html', {
        'title': f'Turma {turma}',
        'turma': turma,
        'form': form if is_admin else None,
        'alunos': turma.alunos.all(),
        'is_admin': is_admin,
    })


@login_required
def aluno_excluir(request, aluno_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        aluno = get_object_or_404(Aluno, id=aluno_id)
        turma_id = aluno.turma_id
        nome = aluno.nome
        aluno.delete()
        msg = f'Aluno "{nome}" removido.'

        if _is_ajax(request):
            restantes = Aluno.objects.filter(turma_id=turma_id).count()
            return JsonResponse({
                'ok': True, 'acao': 'remover_linha', 'message': msg,
                'restantes': restantes,
                'contador': {'seletor': '#cont-alunos', 'valor': restantes},
                'vazio_html': '<tr><td colspan="4" class="text-center text-muted" '
                              'style="padding: 30px;"><em>Nenhum aluno nesta turma ainda. '
                              'Adicione o primeiro ao lado.</em></td></tr>',
            })
        messages.warning(request, msg)
        return redirect('turma_detalhe', turma_id=turma_id)

    return redirect('turmas')


# ---------------------------------------------------------------------------
# IMPORTAÇÃO DE ALUNOS POR PLANILHA (.xlsx ou .csv)
# ---------------------------------------------------------------------------
_ALIAS_NOME = {'nome', 'aluno', 'nome do aluno', 'nome completo', 'nome completo do aluno'}
_ALIAS_RA = {'ra', 'ra (registro)', 'registro', 'matricula', 'matrícula',
             'numero', 'número', 'nº', 'n', 'registro do aluno'}


def _normalizar_texto(valor):
    if valor is None:
        return ''
    return str(valor).strip()


def _normalizar_ra(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _detectar_separador(texto):
    primeira_linha = texto.splitlines()[0] if texto.splitlines() else ''
    return ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','


def _ler_planilha(arquivo):
    nome_arquivo = arquivo.name.lower()

    if nome_arquivo.endswith('.csv'):
        import csv
        import io
        dados = arquivo.read()
        try:
            texto = dados.decode('utf-8-sig')
        except UnicodeDecodeError:
            texto = dados.decode('latin-1')
        separador = _detectar_separador(texto)
        leitor = csv.reader(io.StringIO(texto), delimiter=separador)
        return [list(linha) for linha in leitor], None

    if nome_arquivo.endswith('.xlsx'):
        try:
            import openpyxl
        except ImportError:
            return None, ('Para importar arquivos .xlsx é preciso instalar a biblioteca '
                          'openpyxl (pip install openpyxl). Como alternativa, envie um .csv.')
        wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
        ws = wb.active
        linhas = []
        for row in ws.iter_rows(values_only=True):
            linhas.append(['' if c is None else c for c in row])
        return linhas, None

    return None, 'Formato não suportado. Envie um arquivo .xlsx ou .csv.'


def _mapear_colunas(cabecalho):
    nome_idx = ra_idx = None
    for i, valor in enumerate(cabecalho):
        v = str(valor).strip().lower()
        if nome_idx is None and v in _ALIAS_NOME:
            nome_idx = i
        if ra_idx is None and v in _ALIAS_RA:
            ra_idx = i
    return nome_idx, ra_idx


@login_required
def importar_alunos(request, turma_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    turma = get_object_or_404(Turma, id=turma_id)

    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']

        linhas, erro = _ler_planilha(arquivo)
        if erro:
            messages.error(request, erro)
            return redirect('turma_detalhe', turma_id=turma.id)
        if not linhas:
            messages.warning(request, 'A planilha está vazia.')
            return redirect('turma_detalhe', turma_id=turma.id)

        nome_idx, ra_idx = _mapear_colunas(linhas[0])
        if nome_idx is None or ra_idx is None:
            messages.error(request, (
                'Não encontrei as colunas "nome" e "ra" no cabeçalho da planilha. '
                'Verifique se a primeira linha tem esses títulos (baixe o modelo para conferir o formato).'
            ))
            return redirect('turma_detalhe', turma_id=turma.id)

        criados = 0
        ignorados = 0
        ras_existentes = set(Aluno.objects.values_list('ra', flat=True))

        for linha in linhas[1:]:
            if not linha or len(linha) <= max(nome_idx, ra_idx):
                continue
            nome = _normalizar_texto(linha[nome_idx])
            ra = _normalizar_ra(linha[ra_idx])

            if not nome or not ra or ra in ras_existentes:
                ignorados += 1
                continue

            try:
                Aluno.objects.create(turma=turma, nome=nome, ra=ra)
                ras_existentes.add(ra)
                criados += 1
            except IntegrityError:
                ignorados += 1

        messages.success(request, f'Importação concluída: {criados} aluno(s) adicionado(s).')
        if ignorados:
            messages.warning(
                request,
                f'{ignorados} linha(s) ignorada(s) — RA duplicado ou dados incompletos.'
            )
        return redirect('turma_detalhe', turma_id=turma.id)

    return redirect('turma_detalhe', turma_id=turma.id)


@login_required
def modelo_planilha_alunos(request):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="modelo_alunos.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['nome', 'ra'])
    writer.writerow(['João da Silva', '12345'])
    writer.writerow(['Maria Souza', '12346'])
    return response


# ---------------------------------------------------------------------------
# CANCELAR UMA RESERVA (COM REGISTRO NO HISTÓRICO)
# ---------------------------------------------------------------------------
@login_required
def cancelar_reserva(request, agendamento_id):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        ag = get_object_or_404(Agendamento, id=agendamento_id)
        is_admin = _is_admin_aprovado(request.user)

        if ag.professor_id != request.user.id and not is_admin:
            msg = 'Você só pode cancelar as suas próprias reservas.'
            if _is_ajax(request):
                return JsonResponse({'ok': False, 'message': msg})
            messages.error(request, msg)
            return redirect('agendamentos')

        prof = ag.professor
        ag.delete()

        HistoricoAcao.objects.create(
            admin=request.user,
            acao='CANCELOU_AGENDAMENTO',
            username_solicitante=prof.username,
            email_solicitante=prof.email,
            tipo_solicitado=prof.perfil.tipo if hasattr(prof, 'perfil') else '',
        )

        msg = 'Reserva cancelada com sucesso.'

        if _is_ajax(request):
            restantes = Agendamento.objects.filter(
                professor=request.user, data__gte=date.today()
            ).count()
            return JsonResponse({
                'ok': True, 'acao': 'remover_linha', 'message': msg,
                'restantes': restantes,
                'vazio_html': '<tr><td colspan="6" class="text-center text-muted" '
                              'style="padding: 32px;"><span>📭</span>'
                              '<p style="margin-top: 8px; font-style: italic;">Você não tem '
                              'reservas futuras. Clique em um dia para agendar.</p></td></tr>',
            })
        messages.warning(request, msg)

    return redirect('agendamentos')


# ---------------------------------------------------------------------------
# RELAÇÃO ALUNO x EQUIPAMENTO DE UM AGENDAMENTO (E EDIÇÃO DA RESERVA)
# ---------------------------------------------------------------------------
def _salas_para_edicao(ag):
    ocupadas = set(
        Agendamento.objects
        .filter(data=ag.data, aula=ag.aula, tipo='SALA')
        .exclude(id=ag.id)
        .values_list('sala_id', flat=True)
    )
    opcoes = []
    for s in Sala.objects.filter(ativo=True):
        if s.id not in ocupadas or s.id == ag.sala_id:
            opcoes.append({'sala': s, 'atual': s.id == ag.sala_id})
    return opcoes


def _categorias_para_edicao(ag):
    estoque = _estoque_por_categoria()
    reservado_total = _disponibilidade_dispositivos(ag.data)
    atuais = {it.categoria: it.quantidade for it in ag.itens.all()}

    opcoes = []
    for cat_valor, cat_label in Equipamento.CATEGORIA_CHOICES:
        total = estoque.get(cat_valor, 0)
        atual = atuais.get(cat_valor, 0)
        if total == 0 and atual == 0:
            continue
        reservado_outros = reservado_total.get((ag.aula, cat_valor), 0) - atual
        maximo = max(total - reservado_outros, 0)
        opcoes.append({
            'categoria': cat_valor, 'label': cat_label,
            'atual': atual, 'maximo': maximo,
        })
    return opcoes


def _aplicar_edicao_dispositivo(request, ag):
    estoque = _estoque_por_categoria()
    reservado_total = _disponibilidade_dispositivos(ag.data)
    atuais = {it.categoria: it for it in ag.itens.all()}

    for cat_valor, _label in Equipamento.CATEGORIA_CHOICES:
        campo = request.POST.get(f'qtd_cat_{cat_valor}')
        if campo is None:
            continue
        try:
            novo = max(int(campo), 0)
        except (TypeError, ValueError):
            continue

        atual_qtd = atuais[cat_valor].quantidade if cat_valor in atuais else 0
        reservado_outros = reservado_total.get((ag.aula, cat_valor), 0) - atual_qtd
        maximo = max(estoque.get(cat_valor, 0) - reservado_outros, 0)
        novo = min(novo, maximo)

        if novo > 0:
            if cat_valor in atuais:
                item = atuais[cat_valor]
                item.quantidade = novo
                item.save()
            else:
                ItemDispositivo.objects.create(
                    agendamento=ag, categoria=cat_valor, quantidade=novo
                )
        elif cat_valor in atuais:
            atuais[cat_valor].delete()


@login_required
def relacao_agendamento(request, agendamento_id):
    if not _is_usuario_aprovado(request.user):
        return redirect('home')

    ag = get_object_or_404(
        Agendamento.objects
        .select_related('sala', 'turma', 'professor')
        .prefetch_related('itens'),
        id=agendamento_id
    )

    is_admin = _is_admin_aprovado(request.user)
    pode_editar = is_admin or ag.professor_id == request.user.id

    alunos = list(ag.turma.alunos.all())

    if request.method == 'POST':
        if not pode_editar:
            messages.error(request, 'Você não pode editar esta reserva.')
            return redirect('relacao_agendamento', agendamento_id=ag.id)

        acao = request.POST.get('acao', 'relacao')

        if acao == 'editar':
            ag.observacao = request.POST.get('observacao', '').strip()

            turma = Turma.objects.filter(id=request.POST.get('turma')).first()
            if turma and turma.id != ag.turma_id:
                ag.relacoes.all().delete()
                ag.turma = turma

            if is_admin:
                prof = User.objects.filter(id=request.POST.get('professor')).first()
                if prof:
                    ag.professor = prof

            if ag.tipo == 'SALA':
                nova = request.POST.get('sala', '')
                if nova.isdigit() and int(nova) != ag.sala_id:
                    nova_id = int(nova)
                    ocupada = (
                        Agendamento.objects
                        .filter(data=ag.data, aula=ag.aula, tipo='SALA', sala_id=nova_id)
                        .exclude(id=ag.id).exists()
                    )
                    if ocupada:
                        messages.warning(request, 'A sala escolhida já está ocupada nessa aula; mantida a anterior.')
                    else:
                        ag.sala_id = nova_id

            ag.save()

            if ag.tipo == 'DISPOSITIVO':
                _aplicar_edicao_dispositivo(request, ag)
                if not ag.itens.exists():
                    ag.delete()
                    messages.warning(request, 'A reserva ficou sem equipamentos e foi removida.')
                    return redirect('agendamentos')

            HistoricoAcao.objects.create(
                admin=request.user,
                acao='ALTEROU_AGENDAMENTO',
                username_solicitante=ag.professor.username,
                email_solicitante=ag.professor.email,
                tipo_solicitado=ag.professor.perfil.tipo if hasattr(ag.professor, 'perfil') else '',
            )

            messages.success(request, 'Reserva atualizada com sucesso!')
            return redirect('relacao_agendamento', agendamento_id=ag.id)

        for aluno in alunos:
            valor = request.POST.get(f'equip_{aluno.id}', '').strip()
            RelacaoAlunoEquipamento.objects.update_or_create(
                agendamento=ag, aluno=aluno,
                defaults={'equipamento': valor},
            )
        messages.success(request, 'Relação de alunos e equipamentos salva com sucesso!')
        return redirect('relacao_agendamento', agendamento_id=ag.id)

    salvos = {r.aluno_id: r.equipamento for r in ag.relacoes.all()}
    linhas = [{'aluno': a, 'equipamento': salvos.get(a.id, '')} for a in alunos]

    return render(request, 'app/relacao_agendamento.html', {
        'title': 'Relação Alunos x Equipamentos',
        'ag': ag,
        'linhas': linhas,
        'pode_editar': pode_editar,
        'is_admin': is_admin,
        'turmas': Turma.objects.all(),
        'professores': _professores_aprovados() if is_admin else None,
        'salas_edicao': _salas_para_edicao(ag) if pode_editar and ag.tipo == 'SALA' else None,
        'categorias_edicao': _categorias_para_edicao(ag) if pode_editar and ag.tipo == 'DISPOSITIVO' else None,
    })


def about(request):
    return render(request, 'app/about.html', {'title': 'Sobre o LabHub'})


def contact(request):
    return render(request, 'app/contact.html', {'title': 'Contato'})