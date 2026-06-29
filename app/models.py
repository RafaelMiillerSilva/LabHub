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
    CATEGORIA_CHOICES = (
        ('NOTEBOOK', 'Notebook'),
        ('CHROMEBOOK', 'Chromebook'),
        ('DESKTOP', 'Desktop'),
        ('TABLET', 'Tablet'),
        ('SMARTPHONE', 'Smartphone'),
    )
    STATUS_CHOICES = (
        ('ATIVO', 'Ativo'),
        ('MANUTENCAO', 'Em manutenção'),
        ('QUEBRADO', 'Quebrado'),
        ('DESATIVADO', 'Desativado'),
    )
    # Categorias que possuem chip (e portanto IMEI)
    CATEGORIAS_COM_CHIP = ('TABLET', 'SMARTPHONE')

    # Foto guardada no próprio banco (bytes), não em arquivo no disco
    foto_dados = models.BinaryField(blank=True, null=True, editable=False)
    foto_mime = models.CharField(max_length=50, blank=True, default='')
    tem_foto = models.BooleanField(default=False)
    categoria = models.CharField(max_length=15, choices=CATEGORIA_CHOICES, default='NOTEBOOK')
    apelido = models.CharField(max_length=30, unique=True, default='',
                               help_text='Ex: C01, CH03')
    identificacao_escola = models.CharField('Identificação da escola', max_length=60, blank=True, default='')
    numero_patrimonio = models.CharField('Número de patrimônio', max_length=60, blank=True, default='')
    numero_serie = models.CharField('Número de série', max_length=80, blank=True, default='')
    imei = models.CharField('IMEI', max_length=20, blank=True, null=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ATIVO')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['categoria', 'apelido']
        verbose_name = 'Equipamento'
        verbose_name_plural = 'Equipamentos'

    @property
    def disponivel_para_agendamento(self):
        return self.status == 'ATIVO'

    def __str__(self):
        return f"{self.apelido} ({self.get_categoria_display()})"


# ---------------------------------------------------------------------------
# Turmas (cadastradas pelo administrador)
# ---------------------------------------------------------------------------
class Turma(models.Model):
    TURNO_CHOICES = (
        ('MANHA', 'Manhã'),
        ('TARDE', 'Tarde'),
        ('INTEGRAL', 'Integral'),
        ('NOITE', 'Noite'),
    )

    nome = models.CharField(max_length=50, help_text='Ex: 6º B')
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES, default='MANHA')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome', 'turno']
        # Permite "6º B - Manhã" e "6º B - Tarde", mas não duas iguais
        unique_together = ('nome', 'turno')
        verbose_name = 'Turma'
        verbose_name_plural = 'Turmas'

    @property
    def total_alunos(self):
        return self.alunos.count()

    def __str__(self):
        return f"{self.nome} ({self.get_turno_display()})"


# ---------------------------------------------------------------------------
# Alunos (vinculados a uma turma)
# ---------------------------------------------------------------------------
class Aluno(models.Model):
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name='alunos')
    nome = models.CharField(max_length=120)
    ra = models.CharField(max_length=30, unique=True, verbose_name='RA (registro)')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Aluno'
        verbose_name_plural = 'Alunos'

    def __str__(self):
        return f"{self.nome} - RA {self.ra}"


# ---------------------------------------------------------------------------
# Agendamento: uma reserva de UMA aula, em um dia, por um professor,
# para uma turma. Pode ser de Sala (aponta para uma Sala) ou de
# Dispositivos (ganha vários ItemDispositivo — isso entra na Etapa 4).
# ---------------------------------------------------------------------------
class Agendamento(models.Model):
    TIPO_CHOICES = (
        ('SALA', 'Sala de Aula'),
        ('DISPOSITIVO', 'Equipamentos Móveis'),
    )

    data = models.DateField()
    aula = models.PositiveSmallIntegerField()  # 1 a 9
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)

    professor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='agendamentos'
    )
    turma = models.ForeignKey(
        Turma, on_delete=models.CASCADE, related_name='agendamentos'
    )
    # Só preenchido quando tipo == 'SALA'
    sala = models.ForeignKey(
        Sala, on_delete=models.CASCADE, null=True, blank=True,
        related_name='agendamentos'
    )
    observacao = models.TextField(blank=True, verbose_name='Observação')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data', 'aula']
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'

    def __str__(self):
        return f"{self.data:%d/%m/%Y} - {self.aula}ª aula - {self.get_tipo_display()}"


# ---------------------------------------------------------------------------
# Item de um agendamento de dispositivos: qual equipamento e quantos.
# Um Agendamento de dispositivos pode ter vários destes (um por tipo/aparelho).
# ---------------------------------------------------------------------------
class ItemDispositivo(models.Model):
    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.CASCADE, related_name='itens'
    )
    # Reserva é por categoria (conta unidades disponíveis daquele tipo)
    categoria = models.CharField(
        max_length=15, choices=Equipamento.CATEGORIA_CHOICES, default='NOTEBOOK'
    )
    quantidade = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.get_categoria_display()} x{self.quantidade}"


# ---------------------------------------------------------------------------
# Relação aluno x equipamento dentro de um agendamento.
# O professor registra qual equipamento (ex.: "C13") ficou com cada aluno.
# ---------------------------------------------------------------------------
class RelacaoAlunoEquipamento(models.Model):
    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.CASCADE, related_name='relacoes'
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.CASCADE, related_name='relacoes'
    )
    equipamento = models.CharField(
        max_length=100, blank=True,
        help_text='Identificação do equipamento com o aluno (ex.: C13)'
    )

    class Meta:
        unique_together = ('agendamento', 'aluno')
        verbose_name = 'Relação aluno/equipamento'
        verbose_name_plural = 'Relações aluno/equipamento'

    def __str__(self):
        return f"{self.aluno.nome} -> {self.equipamento or '—'}"


# Sinais para criar o perfil automaticamente quando um usuário for criado
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.perfil.save()