"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class BootstrapAuthenticationForm(AuthenticationForm):
    """Formulário de autenticação que usa CSS do Bootstrap."""
    username = forms.CharField(
        label="E-mail",
        max_length=254,
        widget=forms.TextInput({
            'class': 'form-control', 
            'placeholder': 'seu.email@exemplo.com'
        })
    )
    password = forms.CharField(
        label=_("Senha"),
        widget=forms.PasswordInput({
            'class': 'form-control', 
            'placeholder': 'Senha'
        })
    )

from django.contrib.auth.models import User

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Tenta buscar o usuário tanto pelo e-mail quanto pelo username
            user = User.objects.get(Q(email__iexact=username) | Q(username__iexact=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(Q(email__iexact=username) | Q(username__iexact=username)).first()
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

class CadastroForm(forms.ModelForm):
    CHOICES_TIPO = (
        ('PROFESSOR', 'Professor'),
        ('ADMINISTRADOR', 'Administrador'),
    )
    
    tipo = forms.ChoiceField(
        choices=CHOICES_TIPO, 
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label=_("Senha"),
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Senha'})
    )
    password_confirm = forms.CharField(
        label=_("Confirme a Senha"),
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirme a senha'})
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome de Usuário'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'E-mail'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        # 1. Verifica se todos os campos foram digitados (Sem quebrar a aplicação)
        if not username:
            self.add_error('username', "Por favor, preencha o nome de usuário.")
        if not email:
            self.add_error('email', "Por favor, preencha o e-mail.")
        if not password:
            self.add_error('password', "Por favor, preencha a senha.")
        if not password_confirm:
            self.add_error('password_confirm', "Por favor, confirme a sua senha.")

        # 2. Corrige a mensagem em inglês do validador nativo do Django para o Username
        if username:
            import re
            if not re.match(r'^[\w.@+-]+$', username):
                self.add_error('username', "Introduza um nome de utilizador válido. Este valor pode conter apenas letras, números e os caracteres @/./+/-/_.")

        # 3. Tratativa para quando as senhas não coincidirem
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "As senhas não coincidem.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            # Atualiza o tipo no perfil que foi criado automaticamente pelo Signal
            perfil = user.perfil
            perfil.tipo = self.cleaned_data["tipo"]
            perfil.save()
        return user
