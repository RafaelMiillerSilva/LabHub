from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Perfil(models.Model):
    CHOICES_TIPO = (
        ('PROFESSOR', 'Professor'),
        ('ADMINISTRADOR', 'Administrador'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    tipo = models.CharField(max_length=20, choices=CHOICES_TIPO, default='PROFESSOR')
    aprovado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.tipo} ({'Aprovado' if self.aprovado else 'Pendente'})"


class HistoricoAcao(models.Model):
    CHOICES_ACAO = (
        ('APROVADO', 'Aprovado'),
        ('NEGADO', 'Negado'),
    )

    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='acoes_admin'
    )
    acao = models.CharField(max_length=10, choices=CHOICES_ACAO)
    # Guarda os dados do usuário mesmo após deletar
    username_solicitante = models.CharField(max_length=150)
    email_solicitante = models.CharField(max_length=254, blank=True)
    tipo_solicitado = models.CharField(max_length=20)
    data_acao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_acao']

    def __str__(self):
        return f"{self.acao} - {self.username_solicitante} por {self.admin} em {self.data_acao:%d/%m/%Y %H:%M}"


# ---------------------------------------------------------------------------
# Salas de aula (cadastradas pelo administrador)
# ---------------------------------------------------------------------------
class Sala(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    localizacao = models.CharField(max_length=100, blank=True, verbose_name='Localização')
    capacidade = models.PositiveIntegerField(default=0, help_text='Número de alunos')
    ativo = models.BooleanField(default=True, verbose_name='Ativa')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Sala'
        verbose_name_plural = 'Salas'

    def __str__(self):
        return self.nome


# ---------------------------------------------------------------------------
# Equipamentos móveis (notebooks, tablets, celulares, projetores...)
# ---------------------------------------------------------------------------
class Equipamento(models.Model):
    CHOICES_TIPO = (
        ('NOTEBOOK', 'Notebook'),
        ('TABLET', 'Tablet'),
        ('CELULAR', 'Celular'),
        ('PROJETOR', 'Projetor'),
        ('OUTRO', 'Outro'),
    )

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=CHOICES_TIPO, default='NOTEBOOK')
    quantidade = models.PositiveIntegerField(default=1, help_text='Quantidade total disponível')
    descricao = models.CharField(max_length=200, blank=True, verbose_name='Descrição')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tipo', 'nome']
        verbose_name = 'Equipamento'
        verbose_name_plural = 'Equipamentos'

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


# Sinais para criar o perfil automaticamente quando um usuário for criado
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.perfil.save()