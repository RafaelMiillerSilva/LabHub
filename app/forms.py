"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Sala, Equipamento, Turma, Aluno

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
def _processar_imagem(arquivo, max_lado=800, qualidade=80):
    """Abre, reduz e comprime a imagem enviada; devolve (bytes, mime)."""
    from PIL import Image
    import io
    img = Image.open(arquivo)
    img = img.convert('RGB')                 # achata transparência / padroniza
    img.thumbnail((max_lado, max_lado))      # reduz mantendo proporção
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=qualidade)
    return buf.getvalue(), 'image/jpeg'


class EquipamentoForm(forms.ModelForm):
    # Campo de upload do formulário (não é coluna do model);
    # os bytes processados vão para foto_dados.
    foto = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )
    remover_foto = forms.BooleanField(required=False)

    class Meta:
        model = Equipamento
        fields = ['categoria', 'apelido', 'identificacao_escola',
                  'numero_patrimonio', 'numero_serie', 'imei', 'status', 'observacao']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-control', 'id': 'id_categoria'}),
            'apelido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: C01, CH03'}),
            'identificacao_escola': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Identificação da escola'}),
            'numero_patrimonio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº de patrimônio'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº de série'}),
            'imei': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas tablets/smartphones', 'id': 'id_imei'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Anotações sobre o equipamento, histórico de problemas, etc.'}),
        }

    def clean(self):
        cleaned = super().clean()
        categoria = cleaned.get('categoria')
        # IMEI só faz sentido para aparelhos com chip; nos demais, ignora
        if categoria not in Equipamento.CATEGORIAS_COM_CHIP:
            cleaned['imei'] = ''
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
        # se não enviou foto nem marcou remover, mantém a existente

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