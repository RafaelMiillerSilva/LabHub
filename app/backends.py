"""
Backend de autenticação customizado para o LabHub.
Permite login tanto por e-mail quanto por nome de usuário.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q


class EmailBackend(ModelBackend):
    """
    Permite autenticação com username ou email de forma segura.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        # Tenta buscar o usuário pelo e-mail ou username (case-insensitive)
        users = User.objects.filter(
            Q(email__iexact=username) | Q(username__iexact=username)
        )

        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None
