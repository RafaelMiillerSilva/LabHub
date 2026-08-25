"""
Views de gerenciamento de equipamentos, fotos, etiquetas e exportações.
"""

import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from app.forms import EquipamentoForm
from app.models import Equipamento
from app.services.etiqueta_service import gerar_etiqueta_png, gerar_etiquetas_zip
from .common import is_admin_aprovado, is_usuario_aprovado


@login_required
def equipamentos(request):
    """Listagem e filtros de equipamentos."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = is_admin_aprovado(request.user)
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
    """Cadastro ou edição de equipamento."""
    if not is_admin_aprovado(request.user):
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
    """Edição de equipamento mantendo parâmetros de filtro de busca."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    equipamento = get_object_or_404(Equipamento, pk=pk) if pk else None

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

            base_url = reverse('equipamentos')
            query_params = {}
            if q:
                query_params['q'] = q
            if cat:
                query_params['cat'] = cat

            redirect_url = f'{base_url}?{urlencode(query_params)}' if query_params else base_url
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
    """Retorna os bytes da imagem do equipamento."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    equip = get_object_or_404(Equipamento, id=equip_id)
    if not equip.foto_dados:
        raise Http404('Equipamento sem foto.')

    return HttpResponse(
        bytes(equip.foto_dados),
        content_type=equip.foto_mime or 'image/jpeg'
    )


@login_required
def equipamento_excluir(request, equip_id):
    """Exclui um equipamento preservando os filtros atuais."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

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


@login_required
def etiqueta_equipamento(request, equip_id):
    """Baixa a etiqueta PNG individual de um equipamento."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    equip = get_object_or_404(Equipamento, id=equip_id)
    img = gerar_etiqueta_png(equip)

    response = HttpResponse(content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="etiqueta_{equip.apelido}.png"'
    img.save(response, 'PNG')
    return response


@login_required
def etiquetas_lote(request):
    """Baixa as etiquetas de múltiplos equipamentos em um arquivo ZIP."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    ids = request.GET.getlist('ids')
    equips = list(Equipamento.objects.filter(id__in=ids))

    if not equips:
        messages.warning(request, 'Selecione pelo menos um equipamento para baixar a etiqueta.')
        return redirect('equipamentos')

    if len(equips) == 1:
        return etiqueta_equipamento(request, equips[0].id)

    buffer = gerar_etiquetas_zip(equips)
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="etiquetas.zip"'
    return response


@login_required
def exportar_equipamentos(request):
    """Exporta a lista de equipamentos filtrados para um arquivo CSV formatado."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()

    lista = Equipamento.objects.defer('foto_dados').select_related('sala')
    if q:
        lista = lista.filter(apelido__icontains=q)
    if cat:
        lista = lista.filter(categoria=cat)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="equipamentos.csv"'
    response.write('\ufeff')  # BOM para Excel reconhecer UTF-8

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
