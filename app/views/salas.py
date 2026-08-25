"""
Views de gerenciamento de salas de aula.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.forms import SalaForm
from app.models import Sala
from .common import is_admin_aprovado, is_ajax, is_usuario_aprovado


@login_required
def salas(request):
    """Listagem e cadastro/edição de salas."""
    if not is_usuario_aprovado(request.user):
        return redirect('home')

    is_admin = is_admin_aprovado(request.user)

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
    """Exclui uma sala de aula cadastrada."""
    if not is_admin_aprovado(request.user):
        return redirect('home')

    if request.method == 'POST':
        sala = get_object_or_404(Sala, id=sala_id)
        nome = sala.nome
        sala.delete()
        msg = f'Sala "{nome}" removida.'

        if is_ajax(request):
            restantes = Sala.objects.count()
            return JsonResponse({
                'ok': True, 'acao': 'remover_linha', 'message': msg,
                'restantes': restantes,
                'contador': {'seletor': '#cont-salas', 'valor': restantes},
                'vazio_html': (
                    '<tr><td colspan="5" class="text-center text-muted" style="padding: 30px;">'
                    '<em>Nenhuma sala cadastrada ainda. Cadastre a primeira ao lado.</em></td></tr>'
                ),
            })
        messages.warning(request, msg)

    return redirect('salas')
