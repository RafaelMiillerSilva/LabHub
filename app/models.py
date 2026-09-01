from typing import TYPE_CHECKING
from django.db import models
from django.contrib.auth.models import User

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class Perfil(models.Model):
    CHOICES_TIPO = (
        ('PROFESSOR', 'Professor'),
        ('ADMINISTRADOR', 'Administrador'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    tipo = models.CharField(max_length=20, choices=CHOICES_TIPO, default='PROFESSOR')
    aprovado = models.BooleanField(default=False)

    # Foto de perfil guardada no banco (bytes), mesmo padrão de Equipamento
    foto_dados = models.BinaryField(blank=True, null=True, editable=False)
    foto_mime = models.CharField(max_length=50, blank=True, default='')
    tem_foto = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'
        indexes = [
            models.Index(fields=['aprovado', 'tipo']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.tipo} ({'Aprovado' if self.aprovado else 'Pendente'})"

    @property
    def iniciais(self):
        """Retorna as iniciais do usuário para uso como avatar fallback."""
        nome = self.user.get_full_name() or self.user.username
        partes = nome.split()
        if len(partes) >= 2:
            return (partes[0][0] + partes[-1][0]).upper()
        return nome[:2].upper()


class HistoricoAcao(models.Model):
    CHOICES_ACAO = (
        ('APROVADO', 'Aprovado'),
        ('NEGADO', 'Negado'),
        ('ATIVADO', 'Conta ativada'),
        ('DESATIVADO', 'Conta desativada'),
        ('PROMOVIDO', 'Promovido a admin'),
        ('REBAIXADO', 'Rebaixado a professor'),
        ('REDEFINIDO', 'Senha redefinida'),
        ('SENHA_CANCELADA', 'Pedido de senha cancelado'),
        ('AGENDOU', 'Agendamento realizado'),
        ('ALTEROU_AGENDAMENTO', 'Agendamento alterado'),
        ('CANCELOU_AGENDAMENTO', 'Agendamento cancelado'),
    )

    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='acoes_admin'
    )
    acao = models.CharField(max_length=25, choices=CHOICES_ACAO)
    username_solicitante = models.CharField(max_length=150)
    email_solicitante = models.CharField(max_length=254, blank=True)
    tipo_solicitado = models.CharField(max_length=20)
    data_acao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_acao']
        verbose_name = 'Histórico de Ação'
        verbose_name_plural = 'Histórico de Ações'
        indexes = [
            models.Index(fields=['-data_acao']),
            models.Index(fields=['acao']),
        ]

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
        indexes = [
            models.Index(fields=['ativo', 'nome']),
        ]

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
    modelo = models.CharField('Modelo', max_length=100, blank=True, default='')
    identificacao_escola = models.CharField('Identificação da escola', max_length=60, blank=True, default='')
    numero_patrimonio = models.CharField('Número de patrimônio', max_length=60, blank=True, default='')
    numero_serie = models.CharField('Número de série', max_length=80, blank=True, default='')
    imei = models.CharField('IMEI 1', max_length=20, blank=True, null=True)
    imei_2 = models.CharField('IMEI 2', max_length=20, blank=True, null=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ATIVO')
    fixo = models.BooleanField('Fixo', default=False, help_text='Indica se o equipamento é fixo em uma sala')
    sala = models.ForeignKey(
        Sala,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipamentos_fixos',
        verbose_name='Sala onde é fixo',
        help_text='Selecione a sala caso o equipamento seja fixo'
    )
    observacao = models.TextField('Observação', blank=True, default='',
                                  help_text='Anotações sobre o equipamento, histórico de problemas, etc.')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['categoria', 'apelido']
        verbose_name = 'Equipamento'
        verbose_name_plural = 'Equipamentos'
        indexes = [
            models.Index(fields=['status', 'fixo', 'categoria']),
            models.Index(fields=['apelido']),
        ]

    @property
    def disponivel_para_agendamento(self):
        return self.status == 'ATIVO' and not self.fixo

    def __str__(self):
        return f"{self.apelido} ({self.get_categoria_display()})"


# ---------------------------------------------------------------------------
# Turmas (cadastradas pelo administrador)
# ---------------------------------------------------------------------------
class Turma(models.Model):
    if TYPE_CHECKING:
        alunos: RelatedManager

    TURNO_CHOICES = (
        ('MANHA', 'Manhã'),
        ('TARDE', 'Tarde'),
        ('INTEGRAL', 'Integral'),
        ('NOITE', 'Noite'),
    )

    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=50, help_text='Ex: 6º B')
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES, default='MANHA')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome', 'turno']
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
        indexes = [
            models.Index(fields=['turma', 'nome']),
            models.Index(fields=['ra']),
        ]

    def __str__(self):
        return f"{self.nome} - RA {self.ra}"


# ---------------------------------------------------------------------------
# Agendamento: uma reserva de UMA aula, em um dia, por um professor,
# para uma turma. Pode ser de Sala ou de Dispositivos.
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
    fixo = models.BooleanField(default=False, help_text='Agendamento fixo semanal')
    fixo_grupo_id = models.CharField(
        max_length=36, blank=True, default='',
        help_text='UUID que agrupa agendamentos fixos do mesmo conjunto'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data', 'aula']
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'
        indexes = [
            models.Index(fields=['data', 'aula', 'tipo']),
            models.Index(fields=['professor', 'data']),
            models.Index(fields=['fixo_grupo_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['data', 'aula', 'sala'],
                condition=models.Q(tipo='SALA'),
                name='unique_reserva_sala_aula_data'
            )
        ]

    def __str__(self):
        return f"{self.data:%d/%m/%Y} - {self.aula}ª aula - {self.get_tipo_display()}"


# ---------------------------------------------------------------------------
# Item de um agendamento de dispositivos: qual equipamento e quantos.
# ---------------------------------------------------------------------------
class ItemDispositivo(models.Model):
    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.CASCADE, related_name='itens'
    )
    categoria = models.CharField(
        max_length=15, choices=Equipamento.CATEGORIA_CHOICES, default='NOTEBOOK'
    )
    quantidade = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Item de Dispositivo'
        verbose_name_plural = 'Itens de Dispositivos'
        indexes = [
            models.Index(fields=['agendamento', 'categoria']),
        ]

    def __str__(self):
        return f"{self.get_categoria_display()} x{self.quantidade}"


# ---------------------------------------------------------------------------
# Relação aluno x equipamento dentro de um agendamento.
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


# ---------------------------------------------------------------------------
# Pedido de redefinição de senha (fluxo "esqueci minha senha" mediado por admin)
# ---------------------------------------------------------------------------
class PedidoRedefinicaoSenha(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='pedidos_senha'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)
    atendido_em = models.DateTimeField(null=True, blank=True)
    atendido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='redefinicoes_feitas'
    )

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Pedido de redefinição de senha'
        verbose_name_plural = 'Pedidos de redefinição de senha'
        indexes = [
            models.Index(fields=['atendido', '-criado_em']),
        ]

    def __str__(self):
        estado = 'atendido' if self.atendido else 'pendente'
        return f"Redefinição de {self.user.username} ({estado})"


# ---------------------------------------------------------------------------
# Notificações do sistema para os professores
# ---------------------------------------------------------------------------
class Notificacao(models.Model):
    destinatario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notificacoes'
    )
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        indexes = [
            models.Index(fields=['destinatario', 'lida', '-criada_em']),
        ]

    def __str__(self):
        status = 'lida' if self.lida else 'nova'
        return f"Notificação para {self.destinatario.username} ({status})"


# ---------------------------------------------------------------------------
# Chat entre Usuários
# ---------------------------------------------------------------------------
class MensagemChat(models.Model):
    remetente = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mensagens_enviadas'
    )
    destinatario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mensagens_recebidas'
    )
    texto = models.TextField()
    data_envio = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ['data_envio']
        verbose_name = 'Mensagem de Chat'
        verbose_name_plural = 'Mensagens de Chat'
        indexes = [
            models.Index(fields=['remetente', 'destinatario']),
            models.Index(fields=['destinatario', 'lida']),
            models.Index(fields=['data_envio']),
        ]

    def __str__(self):
        return f"De {self.remetente.username} para {self.destinatario.username} em {self.data_envio:%d/%m/%Y %H:%M}"