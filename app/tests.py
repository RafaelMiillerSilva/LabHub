"""
Testes unitários e de integração para o LabHub.
Cobre regras de equipamentos, autenticação por email, segurança de senhas e concorrência de agendamentos.
"""

from datetime import date
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from app.backends import EmailBackend
from app.forms import CadastroForm, EquipamentoForm
from app.models import Agendamento, Aluno, Equipamento, Sala, Turma


class EquipamentoFixoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password123'
        )
        self.admin.perfil.tipo = 'ADMINISTRADOR'
        self.admin.perfil.aprovado = True
        self.admin.perfil.save()

        self.sala = Sala.objects.create(
            nome='Laboratório 1',
            localizacao='Bloco A',
            capacidade=30,
            ativo=True
        )

    def test_criar_equipamento_fixo_model(self):
        """Testa criação direta no model de equipamento fixo com sala."""
        equip = Equipamento.objects.create(
            apelido='PC-01',
            categoria='DESKTOP',
            fixo=True,
            sala=self.sala,
            status='ATIVO'
        )
        self.assertTrue(equip.fixo)
        self.assertEqual(equip.sala, self.sala)
        self.assertIn(equip, self.sala.equipamentos_fixos.all())

    def test_criar_equipamento_movel_model(self):
        """Testa criação direta no model de equipamento móvel (não fixo)."""
        equip = Equipamento.objects.create(
            apelido='NOTE-01',
            categoria='NOTEBOOK',
            fixo=False,
            sala=None,
            status='ATIVO'
        )
        self.assertFalse(equip.fixo)
        self.assertIsNone(equip.sala)

    def test_formulario_equipamento_fixo_valido(self):
        """Testa validação de formulário com equipamento fixo e sala selecionada."""
        data = {
            'apelido': 'PC-02',
            'categoria': 'DESKTOP',
            'status': 'ATIVO',
            'fixo': True,
            'sala': self.sala.id,
            'identificacao_escola': 'Lab 1',
            'numero_patrimonio': '12345',
            'numero_serie': 'SN123',
            'observacao': 'Fixo no Lab 1'
        }
        form = EquipamentoForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        equip = form.save()
        self.assertTrue(equip.fixo)
        self.assertEqual(equip.sala, self.sala)

    def test_formulario_equipamento_fixo_sem_sala_invalido(self):
        """Testa que marcar fixo=True sem sala gera erro de validação."""
        data = {
            'apelido': 'PC-03',
            'categoria': 'DESKTOP',
            'status': 'ATIVO',
            'fixo': True,
            'sala': '',
        }
        form = EquipamentoForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('sala', form.errors)

    def test_view_equipamento_listagem_e_exportacao(self):
        """Testa listagem e exportação CSV de equipamentos."""
        Equipamento.objects.create(
            apelido='PC-01',
            categoria='DESKTOP',
            fixo=True,
            sala=self.sala,
            status='ATIVO'
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('equipamentos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PC-01')
        self.assertContains(response, 'Laboratório 1')

        response_novo = self.client.get(reverse('equipamento_novo'))
        self.assertEqual(response_novo.status_code, 200)
        self.assertContains(response_novo, 'id_fixo')

        response_csv = self.client.get(reverse('exportar_equipamentos'))
        self.assertEqual(response_csv.status_code, 200)
        conteudo_csv = response_csv.content.decode('utf-8')
        self.assertIn('Fixo', conteudo_csv)
        self.assertIn('Sala', conteudo_csv)


class AutenticacaoEmailBackendTest(TestCase):
    def setUp(self):
        self.backend = EmailBackend()
        self.user = User.objects.create_user(
            username='joaosilva',
            email='joao@exemplo.com',
            password='SenhaSegura@123'
        )

    def test_autenticar_por_email(self):
        """Testa login com sucesso usando endereço de e-mail."""
        user = self.backend.authenticate(None, username='joao@exemplo.com', password='SenhaSegura@123')
        self.assertEqual(user, self.user)

    def test_autenticar_por_username(self):
        """Testa login com sucesso usando username."""
        user = self.backend.authenticate(None, username='joaosilva', password='SenhaSegura@123')
        self.assertEqual(user, self.user)

    def test_autenticar_senha_incorreta(self):
        """Testa rejeição de login com senha incorreta."""
        user = self.backend.authenticate(None, username='joao@exemplo.com', password='SenhaErrada')
        self.assertIsNone(user)


class CadastroSegurancaTest(TestCase):
    def test_rejeitar_email_duplicado(self):
        """Garante que não é permitido cadastrar dois usuários com mesmo e-mail."""
        User.objects.create_user(
            username='user1',
            email='duplicado@exemplo.com',
            password='SenhaForte@123'
        )
        form = CadastroForm(data={
            'username': 'user2',
            'email': 'duplicado@exemplo.com',
            'tipo': 'PROFESSOR',
            'password': 'OutraSenhaForte@123',
            'password_confirm': 'OutraSenhaForte@123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_rejeitar_senhas_divergentes(self):
        """Testa rejeição de cadastro quando confirmação de senha não bate."""
        form = CadastroForm(data={
            'username': 'novousuario',
            'email': 'novo@exemplo.com',
            'tipo': 'PROFESSOR',
            'password': 'SenhaForte@123',
            'password_confirm': 'Diferente@123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password_confirm', form.errors)


class AgendamentoConcorrenciaUnicidadeTest(TestCase):
    def setUp(self):
        self.prof1 = User.objects.create_user(username='prof1', email='p1@teste.com', password='P1@123')
        self.prof2 = User.objects.create_user(username='prof2', email='p2@teste.com', password='P2@123')
        self.sala = Sala.objects.create(nome='Lab Química', ativo=True)
        self.turma = Turma.objects.create(nome='1º A', turno='MANHA')
        self.hoje = date.today()

    def test_impedir_duplicidade_reserva_mesma_sala_mesma_aula(self):
        """Garante que a constraint do banco impede dois agendamentos da mesma sala na mesma aula e data."""
        Agendamento.objects.create(
            data=self.hoje,
            aula=1,
            tipo='SALA',
            professor=self.prof1,
            turma=self.turma,
            sala=self.sala,
        )

        with self.assertRaises(IntegrityError):
            Agendamento.objects.create(
                data=self.hoje,
                aula=1,
                tipo='SALA',
                professor=self.prof2,
                turma=self.turma,
                sala=self.sala,
            )


class TurmaOtimizacaoQueriesTest(TestCase):
    def setUp(self):
        self.turma = Turma.objects.create(nome='3º C', turno='TARDE')
        Aluno.objects.create(turma=self.turma, nome='Aluno 1', ra='RA001')
        Aluno.objects.create(turma=self.turma, nome='Aluno 2', ra='RA002')

    def test_contagem_alunos_turma(self):
        """Valida que a contagem de alunos associados à turma funciona corretamente."""
        self.assertEqual(self.turma.total_alunos, 2)


class HomeDashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='prof_dash', email='dash@teste.com', password='Password@123')
        self.user.perfil.tipo = 'PROFESSOR'
        self.user.perfil.aprovado = True
        self.user.perfil.save()

    def test_home_dashboard_context_e_data(self):
        """Testa se a home para usuário aprovado inclui a data formatada, dia da semana e contadores."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('dia_semana', response.context)
        self.assertIn('mes_nome', response.context)
        self.assertIn('total_sala', response.context)
        self.assertIn('total_disp', response.context)
        self.assertTrue(response.context['dashboard'])
        
        hoje = date.today()
        # Garante que a data e o cabeçalho não estão vazios ou com formatação truncada
        self.assertContains(response, f"{response.context['dia_semana']}, {hoje.day} de {response.context['mes_nome']} de {hoje.year}")


class UsuarioEspacosTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_cadastro_com_espacos_no_username(self):
        """Testa que é permitido cadastrar usuário com espaços no nome de usuário."""
        form = CadastroForm(data={
            'username': 'Professor Carlos Silva',
            'email': 'carlos.silva@exemplo.com',
            'tipo': 'PROFESSOR',
            'password': 'SenhaForte@123',
            'password_confirm': 'SenhaForte@123',
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.username, 'Professor Carlos Silva')

    def test_cadastro_com_multiplos_espacos_e_trim(self):
        """Testa normalização de múltiplos espaços e remoção de espaços nas bordas."""
        form = CadastroForm(data={
            'username': '  Ana   Paula   Alves  ',
            'email': 'ana.alves@exemplo.com',
            'tipo': 'PROFESSOR',
            'password': 'SenhaForte@123',
            'password_confirm': 'SenhaForte@123',
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.username, 'Ana Paula Alves')

    def test_cadastro_rejeita_apenas_espacos(self):
        """Testa rejeição de username formado apenas por espaços."""
        form = CadastroForm(data={
            'username': '     ',
            'email': 'espacos@exemplo.com',
            'tipo': 'PROFESSOR',
            'password': 'SenhaForte@123',
            'password_confirm': 'SenhaForte@123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_cadastro_rejeita_caracteres_invalidos(self):
        """Testa que caracteres não permitidos como $ ou # são rejeitados."""
        form = CadastroForm(data={
            'username': 'Carlos$Silva',
            'email': 'carlos2@exemplo.com',
            'tipo': 'PROFESSOR',
            'password': 'SenhaForte@123',
            'password_confirm': 'SenhaForte@123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_autenticacao_com_username_com_espacos(self):
        """Testa login com username contendo espaços através do EmailBackend."""
        user = User.objects.create_user(
            username='Mariana dos Santos',
            email='mariana@exemplo.com',
            password='SenhaSegura@123'
        )
        backend = EmailBackend()
        autenticado = backend.authenticate(None, username='Mariana dos Santos', password='SenhaSegura@123')
        self.assertEqual(autenticado, user)

    def test_minha_conta_atualizar_username_com_espacos(self):
        """Testa atualização de username com espaços pela página Minha Conta."""
        user = User.objects.create_user(
            username='user_antigo',
            email='antigo@exemplo.com',
            password='SenhaSegura@123'
        )
        user.perfil.aprovado = True
        user.perfil.save()

        self.client.force_login(user)
        response = self.client.post(reverse('minha_conta'), {
            'acao': 'dados',
            'username': 'Nome Atualizado Com Espacos',
            'email': 'antigo@exemplo.com',
        })
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.username, 'Nome Atualizado Com Espacos')

