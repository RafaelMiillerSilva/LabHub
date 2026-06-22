from django.contrib import admin
from .models import Perfil

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'tipo', 'aprovado')  # Colunas que aparecem na lista
    list_filter = ('tipo', 'aprovado')           # Filtros na lateral direita
    search_fields = ('user__username', 'user__email') # Campo de busca
