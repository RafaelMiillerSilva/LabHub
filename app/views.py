import calendar
import random
from datetime import date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import IntegrityError
from django.http import HttpResponse
from .forms import (
    CadastroForm, BootstrapAuthenticationForm, SalaForm, EquipamentoForm,
    TurmaForm, AlunoForm,
)
from .models import Perfil, HistoricoAcao, Sala, Equipamento, Turma, Aluno


# ---------------------------------------------------------------------------
# Constantes de apoio (português)
# ---------------------------------------------------------------------------
MESES_PT = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]

# Cabeçalho do calendário (semana começando no Domingo, como no esboço)
DIAS_SEMANA_PT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

# date.weekday(): Segunda = 0 ... Domingo = 6
DIAS_SEMANA_LONGO = [
    'Segunda-feira', 'Terça-feira', 'Quarta-feira',
    'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo',
]

# As 9 aulas padrão (nome + horário). Ajuste os horários quando quiser.
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

# =====================================================================
# SIMULAÇÃO  ->  trocar por consultas aos models reais depois
# (quando você criar o cadastro de Salas e Dispositivos)
# =====================================================================
DISPOSITIVOS_SIMULADOS = {
    'Notebooks': 30,
    'Tablets': 20,
    'Celulares': 15,
}


def _simular_dia(data):
    """
    Gera dados FALSOS porém ESTÁVEIS para a data informada.
    Como a 'semente' é o número ordinal da data, o mesmo dia sempre
    retorna o mesmo resultado (não muda a cada refresh).

    Retorna duas listas, uma para 'Sala de Aula' e outra para
    'Equipamentos Móveis', cada uma com 9 aulas.
    """
    rng = random.Random(data.toordinal())
    professores = ['Prof. Rafael', 'Profa. Ana', 'Prof. Bruno', 'Profa. Carla', 'Prof. Diego']
    turmas = ['6º A', '6º B', '7º A', '7º C', '8º B', '9º A', '1º EM', '2º EM']

    total_dispositivos = sum(DISPOSITIVOS_SIMULADOS.values())

    salas, moveis = [], []
    for numero, (nome, horario) in enumerate(AULAS_HORARIOS, start=1):

        # ---- Sala de aula: ocupada (vermelho) ou livre (verde) ----
        if rng.random() < 0.4:  # 40% de chance de já estar agendada
            salas.append({
                'numero': numero, 'nome': nome, 'horario': horario,
                'ocupado': True,
                'turma': rng.choice(turmas),
                'professor': rng.choice(professores),
            })
        else:
            salas.append({
                'numero': numero, 'nome': nome, 'horario': horario,
                'ocupado': False,
            })

        # ---- Equipamentos móveis: quantidade disponível por aula ----
        disponivel = rng.randint(0, total_dispositivos)
        ratio = disponivel / total_dispositivos if total_dispositivos else 0
        if disponivel == 0:
            status = 'vermelho'      # nenhum disponível
        elif ratio <= 0.5:
            status = 'laranja'       # cerca de metade
        else:
            status = 'verde'         # muitos disponíveis
        moveis.append({
            'numero': numero, 'nome': nome, 'horario': horario,
            'disponivel': disponivel, 'total': total_dispositivos,
            'status': status,
        })

    return salas, moveis
# =====================================================================


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


# ---------------------------------------------------------------------------
# CALENDÁRIO DE AGENDAMENTOS
# ---------------------------------------------------------------------------
@login_required
def agendamentos(request):
    # Mantém a regra de acesso: precisa de perfil aprovado
    if not hasattr(request.user, 'perfil') or not request.user.perfil.aprovado:
        return redirect('home')

    hoje = date.today()

    # Ano e mês vêm da URL (?ano=2026&mes=6). Se não vier, usa o mês atual.
    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
    except (TypeError, ValueError):
        ano, mes = hoje.year, hoje.month

    if not (1 <= mes <= 12):
        mes = hoje.month

    # Monta a grade do mês com a semana começando no Domingo.
    # No módulo 'calendar', firstweekday=6 corresponde a Domingo.
    cal = calendar.Calendar(firstweekday=6)
    semanas = []
    for semana in cal.monthdayscalendar(ano, mes):
        linha = []
        for dia in semana:
            if dia == 0:
                linha.append(None)  # célula vazia (dia de outro mês)
            else:
                linha.append({
                    'numero': dia,
                    'hoje': (dia == hoje.day and mes == hoje.month and ano == hoje.year),
                })
        semanas.append(linha)

    # Navegação de mês anterior / próximo
    primeiro_dia = date(ano, mes, 1)
    mes_anterior = primeiro_dia - timedelta(days=1)
    proximo_mes = (primeiro_dia.replace(day=28) + timedelta(days=4)).replace(day=1)

    context = {
        'title': 'Agendamentos',
        'ano': ano,
        'mes': mes,
        'mes_nome': MESES_PT[mes - 1],
        'dias_semana': DIAS_SEMANA_PT,
        'semanas': semanas,
        # navegação
        'ano_ant': mes_anterior.year, 'mes_ant': mes_anterior.month,
        'ano_prox': proximo_mes.year, 'mes_prox': proximo_mes.month,
        'hoje_ano': hoje.year, 'hoje_mes': hoje.month,
        # dropdowns "clicáveis" de mês e ano
        'lista_meses': list(enumerate(MESES_PT, start=1)),
        'lista_anos': range(hoje.year - 2, hoje.year + 4),
    }
    return render(request, 'app/agendamentos.html', context)


# ---------------------------------------------------------------------------
# DETALHE DO DIA: escolhe aulas e tipo de agendamento
# ---------------------------------------------------------------------------
@login_required
def agendamento_detalhe(request, ano, mes, dia):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.aprovado:
        return redirect('home')

    try:
        data = date(ano, mes, dia)
    except ValueError:
        messages.error(request, 'Data inválida.')
        return redirect('agendamentos')

    # ----- Envio do formulário de reserva (simulado, sem salvar no banco) -----
    if request.method == 'POST':
        tipo = request.POST.get('tipo')           # 'sala' ou 'movel'
        aulas = request.POST.getlist('aulas')     # ex.: ['1', '3', '4']

        if not aulas:
            messages.warning(request, 'Selecione pelo menos uma aula para agendar.')
        else:
            lista_aulas = ', '.join(f'{a}ª' for a in sorted(aulas, key=int))
            if tipo == 'movel':
                equipamento = request.POST.get('equipamento', 'Equipamentos')
                messages.success(
                    request,
                    f'(Simulação) {equipamento} reservados nas aulas {lista_aulas} '
                    f'do dia {data:%d/%m/%Y}.'
                )
            else:
                messages.success(
                    request,
                    f'(Simulação) Sala de aula reservada nas aulas {lista_aulas} '
                    f'do dia {data:%d/%m/%Y}.'
                )
        return redirect('agendamento_detalhe', ano=ano, mes=mes, dia=dia)

    # ----- Exibição -----
    salas, moveis = _simular_dia(data)

    context = {
        'title': f'Agendamento {data:%d/%m/%Y}',
        'data': data,
        'ano': ano, 'mes': mes, 'dia': dia,
        'dia_semana': DIAS_SEMANA_LONGO[data.weekday()],
        'mes_nome': MESES_PT[mes - 1],
        'salas': salas,
        'moveis': moveis,
        'equipamentos': DISPOSITIVOS_SIMULADOS,
    }
    return render(request, 'app/agendamento_detalhe.html', context)


# ---------------------------------------------------------------------------
# CADASTRO DE SALAS  (somente administradores)
# ---------------------------------------------------------------------------
@login_required
def salas(request):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    # Se veio ?editar=<id>, carrega a sala para edição
    instancia = None
    editar_id = request.GET.get('editar')
    if editar_id:
        instancia = Sala.objects.filter(id=editar_id).first()

    if request.method == 'POST':
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
        'form': form,
        'salas': Sala.objects.all(),
        'editando': instancia,
    })


@login_required
def sala_excluir(request, sala_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        sala = get_object_or_404(Sala, id=sala_id)
        nome = sala.nome
        sala.delete()
        messages.warning(request, f'Sala "{nome}" removida.')

    return redirect('salas')


# ---------------------------------------------------------------------------
# CADASTRO DE EQUIPAMENTOS  (somente administradores)
# ---------------------------------------------------------------------------
@login_required
def equipamentos(request):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    instancia = None
    editar_id = request.GET.get('editar')
    if editar_id:
        instancia = Equipamento.objects.filter(id=editar_id).first()

    if request.method == 'POST':
        post_id = request.POST.get('equip_id')
        if post_id:
            instancia = get_object_or_404(Equipamento, id=post_id)
        form = EquipamentoForm(request.POST, instance=instancia)
        if form.is_valid():
            equip = form.save()
            if post_id:
                messages.success(request, f'Equipamento "{equip.nome}" atualizado com sucesso!')
            else:
                messages.success(request, f'Equipamento "{equip.nome}" cadastrado com sucesso!')
            return redirect('equipamentos')
    else:
        form = EquipamentoForm(instance=instancia)

    return render(request, 'app/equipamentos.html', {
        'title': 'Equipamentos',
        'form': form,
        'equipamentos': Equipamento.objects.all(),
        'editando': instancia,
    })


@login_required
def equipamento_excluir(request, equip_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        equip = get_object_or_404(Equipamento, id=equip_id)
        nome = equip.nome
        equip.delete()
        messages.warning(request, f'Equipamento "{nome}" removido.')

    return redirect('equipamentos')


# ---------------------------------------------------------------------------
# CADASTRO DE TURMAS E ALUNOS  (somente administradores)
# ---------------------------------------------------------------------------
@login_required
def turmas(request):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    # ?editar=<id> carrega a turma para edição
    instancia = None
    editar_id = request.GET.get('editar')
    if editar_id:
        instancia = Turma.objects.filter(id=editar_id).first()

    if request.method == 'POST':
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
        'form': form,
        'turmas': Turma.objects.all(),
        'editando': instancia,
    })


@login_required
def turma_excluir(request, turma_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        turma = get_object_or_404(Turma, id=turma_id)
        nome = str(turma)
        turma.delete()  # apaga os alunos em cascata
        messages.warning(request, f'Turma "{nome}" removida (junto com seus alunos).')

    return redirect('turmas')


@login_required
def turma_detalhe(request, turma_id):
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    turma = get_object_or_404(Turma, id=turma_id)

    # POST aqui = adicionar um aluno manualmente
    if request.method == 'POST':
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
        'form': form,
        'alunos': turma.alunos.all(),
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
        messages.warning(request, f'Aluno "{nome}" removido.')
        return redirect('turma_detalhe', turma_id=turma_id)

    return redirect('turmas')


# ---------------------------------------------------------------------------
# IMPORTAÇÃO DE ALUNOS POR PLANILHA  (.xlsx ou .csv)
# ---------------------------------------------------------------------------

# Cabeçalhos aceitos para cada coluna (tudo minúsculo, sem espaços nas pontas)
_ALIAS_NOME = {'nome', 'aluno', 'nome do aluno', 'nome completo', 'nome completo do aluno'}
_ALIAS_RA = {'ra', 'ra (registro)', 'registro', 'matricula', 'matrícula',
             'numero', 'número', 'nº', 'n', 'registro do aluno'}


def _normalizar_texto(valor):
    if valor is None:
        return ''
    return str(valor).strip()


def _normalizar_ra(valor):
    """RA pode vir como número no Excel (ex: 12345.0). Normaliza para texto limpo."""
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _detectar_separador(texto):
    primeira_linha = texto.splitlines()[0] if texto.splitlines() else ''
    return ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','


def _ler_planilha(arquivo):
    """
    Lê um arquivo .xlsx ou .csv e devolve (linhas, erro).
    'linhas' é uma lista de listas (a primeira é o cabeçalho).
    """
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
    """Descobre em quais posições estão as colunas de nome e RA."""
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

            # Pula linhas incompletas ou RA já existente (no banco ou já visto no arquivo)
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
    """Gera um CSV modelo para o admin preencher e importar."""
    if not _is_admin_aprovado(request.user):
        return redirect('home')

    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="modelo_alunos.csv"'
    response.write('\ufeff')  # BOM para o Excel reconhecer os acentos
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['nome', 'ra'])
    writer.writerow(['João da Silva', '12345'])
    writer.writerow(['Maria Souza', '12346'])
    return response


def about(request):
    return render(request, 'app/about.html', {'title': 'Sobre o LabHub'})


def contact(request):
    return render(request, 'app/contact.html', {'title': 'Contato'})