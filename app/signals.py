"""
Sinais do Django para gerenciamento automático do perfil do usuário.
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Perfil


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Cria automaticamente o perfil quando um novo usuário é cadastrado."""
    if created:
        Perfil.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Salva o perfil existente quando o usuário é atualizado."""
    if hasattr(instance, 'perfil'):
        instance.perfil.save()
