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


# Sinais para criar o perfil automaticamente quando um usuário for criado
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.perfil.save()