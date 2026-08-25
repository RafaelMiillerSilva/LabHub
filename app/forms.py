"""
Definição dos formulários do LabHub.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Aluno, Equipamento, Sala, Turma


def _processar_imagem(arquivo, max_lado=800, qualidade=80):
    """Abre, reduz e comprime a imagem enviada; devolve (bytes, mime)."""
    import io
    from PIL import Image
    img = Image.open(arquivo)
    img = img.convert('RGB')
    img.thumbnail((max_lado, max_lado))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=qualidade)
    return buf.getvalue(), 'image/jpeg'


class BootstrapAuthenticationForm(AuthenticationForm):
    """Formulário de autenticação que usa classes do Bootstrap."""
    username = forms.CharField(
        label="E-mail ou Usuário",
        max_length=254,
        widget=forms.TextInput({
            'class': 'form-control',
            'placeholder': 'seu.email@exemplo.com ou usuário'
        })
    )
    password = forms.CharField(
        label=_("Senha"),
        widget=forms.PasswordInput({
            'class': 'form-control',
            'placeholder': 'Senha'
        })
    )


class CadastroForm(forms.ModelForm):
    """Formulário de cadastro com validação de unicidade de email e força de senha."""
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

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError('O e-mail é obrigatório.')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Este e-mail já está em uso por outro usuário.')
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            # Valida com as regras configuradas no settings.py
            validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "As senhas não coincidem.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            # Atualiza o tipo no perfil criado pelo Signal
            if hasattr(user, 'perfil'):
                user.perfil.tipo = self.cleaned_data["tipo"]
                user.perfil.save()
        return user


# ---------------------------------------------------------------------------
# Cadastro de Salas
# ---------------------------------------------------------------------------
class SalaForm(forms.ModelForm):
    class Meta:
        model = Sala
        fields = ['nome', 'localizacao', 'capacidade', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ex: Laboratório de Informática'
            }),
            'localizacao': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ex: Bloco B - 2º andar'
            }),
            'capacidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


# ---------------------------------------------------------------------------
# Cadastro de Equipamentos
# ---------------------------------------------------------------------------
class EquipamentoForm(forms.ModelForm):
    foto = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )
    remover_foto = forms.BooleanField(required=False)

    class Meta:
        model = Equipamento
        fields = [
            'categoria', 'apelido', 'identificacao_escola',
            'numero_patrimonio', 'numero_serie', 'imei',
            'fixo', 'sala', 'status', 'observacao'
        ]
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-control', 'id': 'id_categoria'}),
            'apelido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: C01, CH03'}),
            'identificacao_escola': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Identificação da escola'}),
            'numero_patrimonio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº de patrimônio'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº de série'}),
            'imei': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas tablets/smartphones', 'id': 'id_imei'}),
            'fixo': forms.CheckboxInput(attrs={'id': 'id_fixo'}),
            'sala': forms.Select(attrs={'class': 'form-control', 'id': 'id_sala'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Anotações sobre o equipamento, histórico de problemas, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sala_field = self.fields.get('sala')
        if isinstance(sala_field, forms.ModelChoiceField):
            sala_field.required = False
            sala_field.empty_label = 'Selecione a sala onde o equipamento está fixado...'

    def clean(self):
        cleaned = super().clean()
        categoria = cleaned.get('categoria')
        if categoria not in Equipamento.CATEGORIAS_COM_CHIP:
            cleaned['imei'] = ''

        fixo = cleaned.get('fixo')
        sala = cleaned.get('sala')
        if not fixo:
            cleaned['sala'] = None
        elif fixo and not sala:
            self.add_error('sala', 'Por favor, selecione a sala onde o equipamento está fixado.')

        return cleaned

    def save(self, commit=True):
        equip = super().save(commit=False)

        if self.cleaned_data.get('remover_foto'):
            equip.foto_dados = None
            equip.foto_mime = ''
            equip.tem_foto = False
        else:
            foto = self.cleaned_data.get('foto')
            if foto:
                dados, mime = _processar_imagem(foto)
                equip.foto_dados = dados
                equip.foto_mime = mime
                equip.tem_foto = True

        if commit:
            equip.save()
        return equip


# ---------------------------------------------------------------------------
# Cadastro de Turmas
# ---------------------------------------------------------------------------
class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['nome', 'turno']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ex: 6º B'
            }),
            'turno': forms.Select(attrs={'class': 'form-control'}),
        }


# ---------------------------------------------------------------------------
# Cadastro de Alunos
# ---------------------------------------------------------------------------
class AlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = ['nome', 'ra']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nome completo do aluno'
            }),
            'ra': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nº de registro (RA)'
            }),
        }
        labels = {
            'ra': 'RA (registro)',
        }