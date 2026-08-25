"""
Views de gerenciamento de turmas, alunos e importação de planilhas.
"""

import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.forms import AlunoForm, TurmaForm
from app.models import Aluno, Turma
from app.services.planilha_service import (
    ler_planilha,
    mapear_colunas,
    normalizar_ra,
    normalizar_texto,
)
from .common import is_admin_aprovado, is_ajax, is_usuario_aprovado


@login_required
def turmas(request):
    """Listagem e cadastro/edição de turmas com anotação otimizada de total de alunos."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = is_admin_aprovado(request.user)

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

    # Consulta otimizada com annotate para evitar N+1 queries no template
    turmas_qs = Turma.objects.annotate(total_alunos=Count('alunos')).all()

    return render(request, 'app/turmas.html', {
        'title': 'Turmas',
        'form': form if is_admin else None,
        'turmas': turmas_qs,
        'editando': instancia,
        'is_admin': is_admin,
    })


@login_required
def turma_excluir(request, turma_id):
    """Remove uma turma e todos os seus alunos vinculados."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        turma = get_object_or_404(Turma, id=turma_id)
        nome = str(turma)
        turma.delete()
        msg = f'Turma "{nome}" removida (junto com seus alunos).'

        if is_ajax(request):
            restantes = Turma.objects.count()
            return JsonResponse({
                'ok': True, 'acao': 'remover_linha', 'message': msg,
                'restantes': restantes,
                'contador': {'seletor': '#cont-turmas', 'valor': restantes},
                'vazio_html': (
                    '<tr><td colspan="4" class="text-center text-muted" style="padding: 30px;">'
                    '<em>Nenhuma turma cadastrada ainda. Cadastre a primeira ao lado.</em></td></tr>'
                ),
            })
        messages.warning(request, msg)

    return redirect('turmas')


@login_required
def turma_detalhe(request, turma_id):
    """Exibe os detalhes de uma turma e lista/adiciona alunos."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = is_admin_aprovado(request.user)
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
    """Exclui um aluno de uma turma."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        aluno = get_object_or_404(Aluno, id=aluno_id)
        turma_id = aluno.turma_id
        nome = aluno.nome
        aluno.delete()
        msg = f'Aluno "{nome}" removido.'

        if is_ajax(request):
            restantes = Aluno.objects.filter(turma_id=turma_id).count()
            return JsonResponse({
                'ok': True, 'acao': 'remover_linha', 'message': msg,
                'restantes': restantes,
                'contador': {'seletor': '#cont-alunos', 'valor': restantes},
                'vazio_html': (
                    '<tr><td colspan="4" class="text-center text-muted" style="padding: 30px;">'
                    '<em>Nenhum aluno nesta turma ainda. Adicione o primeiro ao lado.</em></td></tr>'
                ),
            })
        messages.warning(request, msg)
        return redirect('turma_detalhe', turma_id=turma_id)

    return redirect('turmas')


@login_required
def importar_alunos(request, turma_id):
    """Importa alunos a partir de um arquivo de planilha (.xlsx ou .csv)."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    turma = get_object_or_404(Turma, id=turma_id)

    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']

        linhas, erro = ler_planilha(arquivo)
        if erro:
            messages.error(request, erro)
            return redirect('turma_detalhe', turma_id=turma.id)
        if not linhas:
            messages.warning(request, 'A planilha está vazia.')
            return redirect('turma_detalhe', turma_id=turma.id)

        nome_idx, ra_idx = mapear_colunas(linhas[0])
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
            nome = normalizar_texto(linha[nome_idx])
            ra = normalizar_ra(linha[ra_idx])

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
    """Gera o arquivo modelo CSV para preenchimento e importação de alunos."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="modelo_alunos.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['nome', 'ra'])
    writer.writerow(['João da Silva', '12345'])
    writer.writerow(['Maria Souza', '12346'])
    return response
