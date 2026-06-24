from django.contrib import admin
from .models import Perfil, Sala, Equipamento, Turma, Aluno

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'tipo', 'aprovado')  # Colunas que aparecem na lista
    list_filter = ('tipo', 'aprovado')           # Filtros na lateral direita
    search_fields = ('user__username', 'user__email') # Campo de busca


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'localizacao', 'capacidade', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'localizacao')


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'quantidade', 'ativo')
    list_filter = ('tipo', 'ativo')
    search_fields = ('nome', 'descricao')


class AlunoInline(admin.TabularInline):
    model = Aluno
    extra = 1


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'turno', 'total_alunos')
    list_filter = ('turno',)
    search_fields = ('nome',)
    inlines = [AlunoInline]


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ra', 'turma')
    list_filter = ('turma',)
    search_fields = ('nome', 'ra')