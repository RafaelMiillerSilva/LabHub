"""
Views e endpoints para o módulo de Ocorrências do LabHub.
Acesso restrito exclusivamente a administradores aprovados.
"""

from datetime import date, datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from app.forms import OcorrenciaForm
from app.models import Agendamento, Aluno, Equipamento, Ocorrencia, OcorrenciaFoto, Turma
from .common import is_admin_aprovado

HORARIOS_INICIO_AULAS = {
    1: '07:00',
    2: '07:50',
    3: '08:40',
    4: '09:50',
    5: '10:40',
    6: '11:30',
    7: '13:00',
    8: '13:50',
    9: '14:40',
}


def _extrair_equipamentos_agendamento(ag):
    """Obtém equipamentos associados ao agendamento (via relação ou sala fixa)."""
    apelidos = set()
    if ag.relacao:
        itens = ag.relacao.itens.exclude(equipamento='').values_list('equipamento', flat=True)
        apelidos.update(filter(None, itens))

    equips_da_relacao = list(
        Equipamento.objects.filter(apelido__in=apelidos).order_by('categoria', 'apelido')
    )

    equips_sala = []
    if ag.tipo == 'SALA' and ag.sala:
        equips_sala = list(
            ag.sala.equipamentos_fixos.all().order_by('categoria', 'apelido')
        )

    # Combinar mantendo unicidade
    ids_vistos = set()
    equips_combinados = []
    for eq in equips_da_relacao + equips_sala:
        if eq.id not in ids_vistos:
            ids_vistos.add(eq.id)
            equips_combinados.append(eq)

    return equips_combinados


@login_required
def ocorrencias_lista(request):
    """Lista todas as ocorrências registradas (acesso exclusivo para administradores)."""
    if not is_admin_aprovado(request.user):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('home')

    ocorrencias = (
        Ocorrencia.objects
        .select_related('agendamento', 'professor', 'criado_por', 'agendamento__turma', 'agendamento__sala')
        .prefetch_related('alunos', 'equipamentos', 'fotos')
        .order_by('-data_hora_fato', '-criado_em')
    )

    # Filtros de busca
    termo = request.GET.get('q', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()
    professor_id = request.GET.get('professor', '').strip()

    if termo:
        ocorrencias = ocorrencias.filter(
            Q(descricao__icontains=termo) |
            Q(professor__first_name__icontains=termo) |
            Q(professor__last_name__icontains=termo) |
            Q(professor__username__icontains=termo) |
            Q(alunos__nome__icontains=termo) |
            Q(equipamentos__apelido__icontains=termo)
        ).distinct()

    if data_inicio:
        try:
            di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            ocorrencias = ocorrencias.filter(data_hora_fato__date__gte=di)
        except ValueError:
            pass

    if data_fim:
        try:
            df = datetime.strptime(data_fim, '%Y-%m-%d').date()
            ocorrencias = ocorrencias.filter(data_hora_fato__date__lte=df)
        except ValueError:
            pass

    if professor_id and professor_id.isdigit():
        ocorrencias = ocorrencias.filter(professor_id=int(professor_id))

    professores = User.objects.filter(is_active=True).order_by('first_name', 'username')

    return render(request, 'app/ocorrencias_lista.html', {
        'title': 'Ocorrências Registradas',
        'ocorrencias': ocorrencias,
        'professores': professores,
        'termo': termo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'professor_selecionado': int(professor_id) if professor_id and professor_id.isdigit() else None,
        'total_ocorrencias': ocorrencias.count(),
    })


@login_required
def ocorrencia_detalhe(request, ocorrencia_id):
    """Exibe os detalhes de uma ocorrência específica com fotos e envolvidos."""
    if not is_admin_aprovado(request.user):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('home')

    ocorrencia = get_object_or_404(
        Ocorrencia.objects
        .select_related('agendamento', 'professor', 'criado_por', 'agendamento__turma', 'agendamento__sala')
        .prefetch_related('alunos', 'equipamentos', 'fotos'),
        id=ocorrencia_id
    )

    return render(request, 'app/ocorrencia_detalhe.html', {
        'title': f'Ocorrência #{ocorrencia.id}',
        'ocorrencia': ocorrencia,
    })


@login_required
def ocorrencia_criar(request):
    """
    Criação de nova ocorrência.
    Suporta Cenário A (com agendamento prévio) e Cenário B (seleção dinâmica de data/aula).
    """
    if not is_admin_aprovado(request.user):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('home')

    todos_equipamentos = list(
        Equipamento.objects.filter(status='ATIVO').order_by('categoria', 'apelido')
    )
    professores = list(
        User.objects.filter(is_active=True).order_by('first_name', 'username')
    )

    if request.method == 'POST':
        form = OcorrenciaForm(request.POST, request.FILES)
        agendamento_id = request.POST.get('agendamento') or request.POST.get('agendamento_id')
        ag = None
        if agendamento_id and str(agendamento_id).isdigit():
            ag = Agendamento.objects.filter(id=int(agendamento_id)).first()

        # Ajusta querysets dos campos ManyToMany para validação do formulário
        if ag and ag.turma_id:
            form.fields['alunos'].queryset = Aluno.objects.filter(turma_id=ag.turma_id)
        else:
            form.fields['alunos'].queryset = Aluno.objects.all()
        form.fields['equipamentos'].queryset = Equipamento.objects.all()

        if form.is_valid():
            ocorrencia = form.save(commit=False)
            ocorrencia.criado_por = request.user
            if ag:
                ocorrencia.agendamento = ag
            ocorrencia.save()
            form.save_m2m()

            # Processamento das fotos enviadas
            fotos = request.FILES.getlist('fotos')
            for foto in fotos:
                OcorrenciaFoto.objects.create(ocorrencia=ocorrencia, foto=foto)

            messages.success(
                request,
                f'Ocorrência #{ocorrencia.id} registrada com sucesso!'
            )
            return redirect('ocorrencia_detalhe', ocorrencia_id=ocorrencia.id)
        else:
            messages.error(request, 'Por favor, corrija os erros no formulário.')
            # Recarregar contexto de aula caso estivesse em contexto de agendamento
            alunos_disponiveis = []
            equipamentos_relacionados = []
            if ag:
                alunos_disponiveis = list(ag.turma.alunos.all().order_by('nome'))
                equipamentos_relacionados = _extrair_equipamentos_agendamento(ag)
            return render(request, 'app/ocorrencia_form.html', {
                'title': 'Registrar Ocorrência',
                'form': form,
                'ag_selecionado': ag,
                'alunos_disponiveis': alunos_disponiveis,
                'equipamentos_relacionados': equipamentos_relacionados,
                'todos_equipamentos': todos_equipamentos,
                'professores': professores,
                'hoje': timezone.localtime().strftime('%Y-%m-%d'),
            })

    # Tratamento GET
    agendamento_id = request.GET.get('agendamento_id')
    ag_selecionado = None
    alunos_disponiveis = []
    equipamentos_relacionados = []
    initial_data = {}

    if agendamento_id and agendamento_id.isdigit():
        # Cenário A: Aberto a partir de um Agendamento
        ag_selecionado = get_object_or_404(
            Agendamento.objects
            .select_related('turma', 'professor', 'sala', 'relacao')
            .prefetch_related('itens'),
            id=int(agendamento_id)
        )
        horario = HORARIOS_INICIO_AULAS.get(ag_selecionado.aula, '08:00')
        data_hora_sugerida = f"{ag_selecionado.data.isoformat()}T{horario}"

        initial_data = {
            'agendamento': ag_selecionado.id,
            'professor': ag_selecionado.professor_id,
            'data_hora_fato': data_hora_sugerida,
        }

        alunos_disponiveis = list(ag_selecionado.turma.alunos.all().order_by('nome'))
        equipamentos_relacionados = _extrair_equipamentos_agendamento(ag_selecionado)
    else:
        # Cenário B: Aberto pelo ícone da Navbar / Standalone
        agora = timezone.localtime()
        initial_data = {
            'data_hora_fato': agora.strftime('%Y-%m-%dT%H:%M'),
        }

    form = OcorrenciaForm(initial=initial_data)

    return render(request, 'app/ocorrencia_form.html', {
        'title': 'Registrar Ocorrência',
        'form': form,
        'ag_selecionado': ag_selecionado,
        'alunos_disponiveis': alunos_disponiveis,
        'equipamentos_relacionados': equipamentos_relacionados,
        'todos_equipamentos': todos_equipamentos,
        'professores': professores,
        'hoje': (ag_selecionado.data if ag_selecionado else timezone.localtime().date()).strftime('%Y-%m-%d'),
    })


@login_required
def ocorrencia_excluir(request, ocorrencia_id):
    """Exclui uma ocorrência registrada (acesso exclusivo para administradores)."""
    if not is_admin_aprovado(request.user):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('home')

    ocorrencia = get_object_or_404(Ocorrencia, id=ocorrencia_id)
    if request.method == 'POST':
        num_id = ocorrencia.id
        # Excluir arquivos físicos das fotos se existirem
        for foto in ocorrencia.fotos.all():
            if foto.foto:
                try:
                    foto.foto.delete(save=False)
                except Exception:
                    pass
        ocorrencia.delete()
        messages.success(request, f'Ocorrência #{num_id} excluída com sucesso.')
        return redirect('ocorrencias_lista')

    messages.error(request, 'Método de exclusão inválido.')
    return redirect('ocorrencia_detalhe', ocorrencia_id=ocorrencia.id)


# ---------------------------------------------------------------------------
# Endpoints de API para Busca Assíncrona (Cenário B e formulário dinâmico)
# ---------------------------------------------------------------------------

@login_required
def api_agendamentos_por_data(request):
    """Retorna lista de aulas agendadas em uma data específica."""
    if not is_admin_aprovado(request.user):
        return JsonResponse({'sucesso': False, 'erro': 'Acesso não autorizado.'}, status=403)

    data_str = request.GET.get('data', '').strip()
    if not data_str:
        return JsonResponse({'sucesso': False, 'erro': 'Parâmetro data é obrigatório.'}, status=400)

    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'sucesso': False, 'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    agendamentos = (
        Agendamento.objects
        .filter(data=data_obj)
        .select_related('turma', 'professor', 'sala')
        .prefetch_related('itens')
        .order_by('aula', 'turma__nome')
    )

    lista = []
    for ag in agendamentos:
        if ag.tipo == 'SALA' and ag.sala:
            local_nome = f"Sala: {ag.sala.nome}"
        else:
            itens_str = ", ".join(f"{it.get_categoria_display()} ×{it.quantidade}" for it in ag.itens.all())
            local_nome = f"Dispositivos: {itens_str}" if itens_str else "Dispositivos Móveis"

        horario = HORARIOS_INICIO_AULAS.get(ag.aula, '')
        prof_nome = ag.professor.get_full_name() or ag.professor.username

        lista.append({
            'id': ag.id,
            'aula': ag.aula,
            'aula_rotulo': f"{ag.aula}ª Aula ({horario})",
            'horario': horario,
            'turma_id': ag.turma_id,
            'turma_nome': ag.turma.nome,
            'turma_turno': ag.turma.get_turno_display(),
            'professor_id': ag.professor_id,
            'professor_nome': prof_nome,
            'tipo': ag.tipo,
            'local': local_nome,
            'observacao': ag.observacao or '',
        })

    return JsonResponse({
        'sucesso': True,
        'data': data_str,
        'total': len(lista),
        'agendamentos': lista,
    })


@login_required
def api_agendamento_contexto(request, agendamento_id):
    """
    Retorna os detalhes de contexto de um agendamento:
    Alunos da turma com equipamentos atribuídos na relação,
    equipamentos vinculados e professor responsável.
    """
    if not is_admin_aprovado(request.user):
        return JsonResponse({'sucesso': False, 'erro': 'Acesso não autorizado.'}, status=403)

    ag = get_object_or_404(
        Agendamento.objects
        .select_related('turma', 'professor', 'sala', 'relacao')
        .prefetch_related('itens'),
        id=agendamento_id
    )

    # Mapear equipamento de cada aluno na relação, se houver
    atribuicoes = {}
    if ag.relacao:
        for it in ag.relacao.itens.all():
            if it.equipamento:
                atribuicoes[it.aluno_id] = it.equipamento

    alunos_data = []
    for al in ag.turma.alunos.all().order_by('nome'):
        alunos_data.append({
            'id': al.id,
            'nome': al.nome,
            'ra': al.ra_formatado,
            'equipamento': atribuicoes.get(al.id, ''),
        })

    equips_relacionados = _extrair_equipamentos_agendamento(ag)
    equips_data = [
        {
            'id': eq.id,
            'apelido': eq.apelido,
            'categoria': eq.get_categoria_display(),
            'modelo': eq.modelo or '',
            'status': eq.get_status_display(),
        }
        for eq in equips_relacionados
    ]

    horario = HORARIOS_INICIO_AULAS.get(ag.aula, '08:00')
    data_hora_sugerida = f"{ag.data.isoformat()}T{horario}"

    prof_nome = ag.professor.get_full_name() or ag.professor.username
    local_str = ag.sala.nome if ag.tipo == 'SALA' and ag.sala else 'Dispositivos Móveis'

    return JsonResponse({
        'sucesso': True,
        'agendamento': {
            'id': ag.id,
            'data': ag.data.isoformat(),
            'data_formatada': ag.data.strftime('%d/%m/%Y'),
            'aula': ag.aula,
            'aula_rotulo': f"{ag.aula}ª Aula ({horario})",
            'data_hora_sugerida': data_hora_sugerida,
            'turma_id': ag.turma_id,
            'turma_nome': ag.turma.nome,
            'professor_id': ag.professor_id,
            'professor_nome': prof_nome,
            'local': local_str,
        },
        'alunos': alunos_data,
        'equipamentos_relacionados': equips_data,
    })
