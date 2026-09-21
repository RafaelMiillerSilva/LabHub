"""
Testes unitários e de integração para o LabHub.
Cobre regras de equipamentos, autenticação por email, segurança de senhas e concorrência de agendamentos.
"""

from datetime import date, timedelta
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from app.backends import EmailBackend
from app.forms import CadastroForm, EquipamentoForm
from app.models import (
    Agendamento, Aluno, Equipamento, ItemDispositivo,
    Ocorrencia, OcorrenciaFoto, Relacao, RelacaoAlunoEquipamento, Sala, Turma
)


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


class ChatReativoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='professor1',
            email='p1@escola.com',
            password='SenhaSegura@123'
        )
        self.user1.perfil.tipo = 'PROFESSOR'
        self.user1.perfil.aprovado = True
        self.user1.perfil.save()

        self.user2 = User.objects.create_user(
            username='coordenador',
            email='coord@escola.com',
            password='SenhaSegura@123'
        )
        self.user2.perfil.tipo = 'ADMINISTRADOR'
        self.user2.perfil.aprovado = True
        self.user2.perfil.save()

    def test_chat_inbox_html(self):
        """Testa que a view chat_inbox renderiza HTML com a lista de contatos."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'coordenador')
        self.assertContains(response, 'chatApp')

    def test_chat_inbox_ajax_retorna_json(self):
        """Testa que chat_inbox com header AJAX devolve JSON com contatos."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_inbox'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertTrue(len(data['contatos']) >= 1)
        self.assertEqual(data['contatos'][0]['username'], 'coordenador')

    def test_chat_conversa_html(self):
        """Testa que chat_conversa acessado diretamente via GET renderiza a conversa ativa."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_conversa', args=[self.user2.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'coordenador')
        self.assertEqual(response.context['contato_ativo'], self.user2)

    def test_chat_conversa_ajax_retorna_json(self):
        """Testa que chat_conversa via AJAX devolve JSON para carga reativa sem refresh."""
        self.client.force_login(self.user1)
        response = self.client.get(
            reverse('chat_conversa', args=[self.user2.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['contato']['id'], self.user2.id)
        self.assertEqual(data['contato']['username'], 'coordenador')
        self.assertIn('mensagens', data)

    def test_api_chat_contatos_json(self):
        """Testa endpoint api_chat_contatos para atualização em segundo plano."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('api_chat_contatos'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['contatos'][0]['id'], self.user2.id)

    def test_api_chat_enviar_e_buscar(self):
        """Testa envio de mensagem e busca via API AJAX."""
        self.client.force_login(self.user1)
        import json
        response = self.client.post(
            reverse('api_chat_enviar', args=[self.user2.id]),
            data=json.dumps({'texto': 'Olá Coordenador!'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['mensagem']['texto'], 'Olá Coordenador!')

        # Agora user2 busca mensagens novas
        self.client.force_login(self.user2)
        response_busca = self.client.get(
            reverse('api_chat_buscar', args=[self.user1.id]) + '?ultimo_id=0'
        )
        self.assertEqual(response_busca.status_code, 200)
        data_busca = response_busca.json()
        self.assertTrue(data_busca['sucesso'])
        self.assertEqual(len(data_busca['mensagens']), 1)
        self.assertEqual(data_busca['mensagens'][0]['texto'], 'Olá Coordenador!')


class AgendamentoFixoCancelamentoEdicaoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prof1 = User.objects.create_user(username='prof1', email='prof1@teste.com', password='Password@123')
        self.prof1.perfil.tipo = 'PROFESSOR'
        self.prof1.perfil.aprovado = True
        self.prof1.perfil.save()

        self.prof2 = User.objects.create_user(username='prof2', email='prof2@teste.com', password='Password@123')
        self.prof2.perfil.tipo = 'PROFESSOR'
        self.prof2.perfil.aprovado = True
        self.prof2.perfil.save()

        self.admin = User.objects.create_user(username='admin', email='admin@teste.com', password='Password@123', is_staff=True)
        self.admin.perfil.tipo = 'ADMINISTRADOR'
        self.admin.perfil.aprovado = True
        self.admin.perfil.save()

        self.turma1 = Turma.objects.create(nome='Turma A', turno='MANHA')
        self.turma2 = Turma.objects.create(nome='Turma B', turno='MANHA')
        self.sala1 = Sala.objects.create(nome='Laboratório 1', capacidade=30, ativo=True)
        self.sala2 = Sala.objects.create(nome='Laboratório 2', capacidade=30, ativo=True)

    def test_cancelar_agendamento_simples_e_permissoes(self):
        """Valida que professor cancela sua reserva, admin pode cancelar, e outro professor não pode."""
        ag = Agendamento.objects.create(
            data=date.today() + timedelta(days=1),
            aula=1,
            tipo='SALA',
            professor=self.prof1,
            turma=self.turma1,
            sala=self.sala1
        )

        # Prof2 tenta cancelar a reserva de Prof1 -> Deve falhar
        self.client.force_login(self.prof2)
        resp = self.client.post(reverse('cancelar_reserva', args=[ag.id]))
        self.assertTrue(Agendamento.objects.filter(id=ag.id).exists())

        # Prof1 cancela sua própria reserva -> Deve excluir
        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('cancelar_reserva', args=[ag.id]))
        self.assertFalse(Agendamento.objects.filter(id=ag.id).exists())

    def test_cancelar_agendamento_fixo_apenas_hoje(self):
        """Ao cancelar fixo com cancelar_tipo='hoje', apenas aquela reserva específica é removida."""
        grupo_id = 'test-grupo-fixo-uuid'
        d1 = date.today() + timedelta(days=1)
        d2 = date.today() + timedelta(days=8)
        d3 = date.today() + timedelta(days=15)

        ag1 = Agendamento.objects.create(data=d1, aula=2, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id)
        ag2 = Agendamento.objects.create(data=d2, aula=2, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id)
        ag3 = Agendamento.objects.create(data=d3, aula=2, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id)

        self.client.force_login(self.prof1)
        self.client.post(reverse('cancelar_reserva', args=[ag1.id]), {'cancelar_tipo': 'hoje'})

        self.assertFalse(Agendamento.objects.filter(id=ag1.id).exists())
        self.assertTrue(Agendamento.objects.filter(id=ag2.id).exists())
        self.assertTrue(Agendamento.objects.filter(id=ag3.id).exists())

    def test_cancelar_agendamento_fixo_todos_futuros(self):
        """Ao cancelar fixo com cancelar_tipo='todos', remove todas as ocorrências a partir daquela data."""
        grupo_id = 'test-grupo-todos-uuid'
        d1 = date.today() + timedelta(days=1)
        d2 = date.today() + timedelta(days=8)
        d3 = date.today() + timedelta(days=15)

        ag1 = Agendamento.objects.create(data=d1, aula=3, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id)
        ag2 = Agendamento.objects.create(data=d2, aula=3, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id)
        ag3 = Agendamento.objects.create(data=d3, aula=3, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id)

        self.client.force_login(self.prof1)
        self.client.post(reverse('cancelar_reserva', args=[ag2.id]), {'cancelar_tipo': 'todos'})

        # d1 anterior a d2 deve permanecer, d2 e d3 devem ser removidos
        self.assertTrue(Agendamento.objects.filter(id=ag1.id).exists())
        self.assertFalse(Agendamento.objects.filter(id=ag2.id).exists())
        self.assertFalse(Agendamento.objects.filter(id=ag3.id).exists())

    def test_editar_agendamento_fixo_apenas_este(self):
        """Editar com editar_tipo='apenas_este' altera somente o agendamento atual."""
        grupo_id = 'test-editar-grupo-uuid'
        d1 = date.today() + timedelta(days=2)
        d2 = date.today() + timedelta(days=9)

        ag1 = Agendamento.objects.create(data=d1, aula=4, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id, observacao='Obs inicial')
        ag2 = Agendamento.objects.create(data=d2, aula=4, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id, observacao='Obs inicial')

        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('relacao_agendamento', args=[ag1.id]), {
            'acao': 'editar',
            'editar_tipo': 'apenas_este',
            'turma': self.turma1.id,
            'sala': self.sala1.id,
            'observacao': 'Obs alterada só hoje',
        })
        self.assertEqual(resp.status_code, 302)

        ag1.refresh_from_db()
        ag2.refresh_from_db()
        self.assertEqual(ag1.observacao, 'Obs alterada só hoje')
        self.assertEqual(ag2.observacao, 'Obs inicial')

    def test_editar_agendamento_fixo_todos_futuros(self):
        """Editar com editar_tipo='todos' propaga as mudanças para os futuros da série fixa."""
        grupo_id = 'test-propagar-uuid'
        d1 = date.today() + timedelta(days=3)
        d2 = date.today() + timedelta(days=10)

        ag1 = Agendamento.objects.create(data=d1, aula=5, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id, observacao='Antiga')
        ag2 = Agendamento.objects.create(data=d2, aula=5, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1, fixo=True, fixo_grupo_id=grupo_id, observacao='Antiga')

        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('relacao_agendamento', args=[ag1.id]), {
            'acao': 'editar',
            'editar_tipo': 'todos',
            'turma': self.turma2.id,
            'sala': self.sala2.id,
            'observacao': 'Obs propagada para toda a série',
        })
        self.assertEqual(resp.status_code, 302)

        ag1.refresh_from_db()
        ag2.refresh_from_db()
        self.assertEqual(ag1.observacao, 'Obs propagada para toda a série')
        self.assertEqual(ag2.observacao, 'Obs propagada para toda a série')
        self.assertEqual(ag1.turma, self.turma2)
        self.assertEqual(ag2.turma, self.turma2)
        self.assertEqual(ag1.sala, self.sala2)
        self.assertEqual(ag2.sala, self.sala2)

    def test_icone_lixeira_agenda_semanal_visibilidade(self):
        """Na agenda semanal, admin vê ícone de lixeira em todos os agendamentos e professor só nos seus."""
        d = date.today()
        ag_prof1 = Agendamento.objects.create(data=d, aula=1, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1)
        ag_prof2 = Agendamento.objects.create(data=d, aula=2, tipo='SALA', professor=self.prof2, turma=self.turma2, sala=self.sala2)

        # Prof1 acessa agendamentos
        self.client.force_login(self.prof1)
        resp_prof1 = self.client.get(reverse('agendamentos'))
        self.assertEqual(resp_prof1.status_code, 200)
        content1 = resp_prof1.content.decode('utf-8')
        # Prof1 deve ver o botão de cancelar no ag_prof1, mas NÃO no ag_prof2
        self.assertIn(f'data-id="{ag_prof1.id}"', content1)
        self.assertNotIn(f'data-id="{ag_prof2.id}"', content1)

        # Admin acessa agendamentos -> Deve ver botões de cancelar para ambos
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('agendamentos'))
        self.assertEqual(resp_admin.status_code, 200)
        content_admin = resp_admin.content.decode('utf-8')
        self.assertIn(f'data-id="{ag_prof1.id}"', content_admin)
        self.assertIn(f'data-id="{ag_prof2.id}"', content_admin)


class PainelDiarioHomeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prof1 = User.objects.create_user(username='prof1', email='prof1@teste.com', password='Password@123')
        self.prof1.perfil.tipo = 'PROFESSOR'
        self.prof1.perfil.aprovado = True
        self.prof1.perfil.save()

        self.prof2 = User.objects.create_user(username='prof2', email='prof2@teste.com', password='Password@123')
        self.prof2.perfil.tipo = 'PROFESSOR'
        self.prof2.perfil.aprovado = True
        self.prof2.perfil.save()

        self.admin = User.objects.create_user(username='admin', email='admin@teste.com', password='Password@123', is_staff=True)
        self.admin.perfil.tipo = 'ADMINISTRADOR'
        self.admin.perfil.aprovado = True
        self.admin.perfil.save()

        self.turma1 = Turma.objects.create(nome='3º Ano A', turno='MANHA')
        self.turma2 = Turma.objects.create(nome='2º Ano B', turno='TARDE')
        self.sala1 = Sala.objects.create(nome='Laboratório 1', capacidade=30, ativo=True)
        self.sala2 = Sala.objects.create(nome='Laboratório 2', capacidade=30, ativo=True)

    def test_painel_diario_renderizacao_basica(self):
        """Home deve carregar com a grade_diaria contendo 9 aulas, salas ativas e coluna de equipamentos."""
        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['dashboard'])
        self.assertTrue(resp.context['is_hoje'])
        self.assertEqual(len(resp.context['grade_diaria']), 9)
        self.assertEqual(len(resp.context['salas']), 2)

        # Checar estrutura da linha de aula
        linha1 = resp.context['grade_diaria'][0]
        self.assertEqual(linha1['aula'], 1)
        self.assertEqual(len(linha1['colunas_salas']), 2)
        self.assertIn('coluna_equip', linha1)

    def test_painel_diario_navegacao_data(self):
        """Navegação via ?data=YYYY-MM-DD deve carregar o painel para a data indicada."""
        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('home') + '?data=2026-09-15')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['data_atual'], date(2026, 9, 15))
        self.assertEqual(resp.context['dia_ant'], date(2026, 9, 14))
        self.assertEqual(resp.context['dia_prox'], date(2026, 9, 16))
        self.assertFalse(resp.context['is_hoje'])

    def test_painel_diario_agrupamento_duas_aulas_sala(self):
        """Duas aulas seguidas com mesmo professor, turma e sala devem ter rowspan=2 e a segunda linha skip=True."""
        hoje = date.today()
        ag1 = Agendamento.objects.create(
            data=hoje, aula=1, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1
        )
        ag2 = Agendamento.objects.create(
            data=hoje, aula=2, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1
        )

        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)

        linha1 = resp.context['grade_diaria'][0]
        col_sala1_l1 = next(c for c in linha1['colunas_salas'] if c['sala'].id == self.sala1.id)
        self.assertTrue(col_sala1_l1['dupla'])
        self.assertEqual(col_sala1_l1['rowspan'], 2)
        self.assertFalse(col_sala1_l1['skip'])
        self.assertEqual(col_sala1_l1['reserva'], ag1)
        self.assertEqual(col_sala1_l1['reserva_segunda'], ag2)

        linha2 = resp.context['grade_diaria'][1]
        col_sala1_l2 = next(c for c in linha2['colunas_salas'] if c['sala'].id == self.sala1.id)
        self.assertTrue(col_sala1_l2['skip'])

        content = resp.content.decode('utf-8')
        self.assertIn('2 aulas', content)
        self.assertIn(f'data-id-segunda="{ag2.id}"', content)

    def test_painel_diario_agrupamento_duas_aulas_equipamentos(self):
        """Duas aulas seguidas com mesmos itens de equipamentos, professor e turma devem ter rowspan=2 na coluna de equipamentos."""
        hoje = date.today()
        ag1 = Agendamento.objects.create(
            data=hoje, aula=3, tipo='DISPOSITIVO', professor=self.prof1, turma=self.turma1
        )
        ItemDispositivo.objects.create(agendamento=ag1, categoria='NOTEBOOK', quantidade=10)

        ag2 = Agendamento.objects.create(
            data=hoje, aula=4, tipo='DISPOSITIVO', professor=self.prof1, turma=self.turma1
        )
        ItemDispositivo.objects.create(agendamento=ag2, categoria='NOTEBOOK', quantidade=10)

        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)

        linha3 = resp.context['grade_diaria'][2]
        self.assertTrue(linha3['coluna_equip']['dupla'])
        self.assertEqual(linha3['coluna_equip']['rowspan'], 2)
        self.assertFalse(linha3['coluna_equip']['skip'])

        linha4 = resp.context['grade_diaria'][3]
        self.assertTrue(linha4['coluna_equip']['skip'])

        content = resp.content.decode('utf-8')
        self.assertIn('Notebook: <strong>10</strong>', content)

    def test_painel_diario_lixeira_cancelamento_permissoes(self):
        """Admin deve ver botão de cancelar em todas as reservas do painel; professor vê apenas nas suas."""
        hoje = date.today()
        ag_prof1 = Agendamento.objects.create(
            data=hoje, aula=1, tipo='SALA', professor=self.prof1, turma=self.turma1, sala=self.sala1
        )
        ag_prof2 = Agendamento.objects.create(
            data=hoje, aula=1, tipo='SALA', professor=self.prof2, turma=self.turma2, sala=self.sala2
        )

        # Prof1 acessa o painel diário na home
        self.client.force_login(self.prof1)
        resp_prof1 = self.client.get(reverse('home'))
        content_prof1 = resp_prof1.content.decode('utf-8')
        self.assertIn(f'data-id="{ag_prof1.id}"', content_prof1)
        self.assertNotIn(f'data-id="{ag_prof2.id}"', content_prof1)

        # Admin acessa o painel diário na home
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('home'))
        content_admin = resp_admin.content.decode('utf-8')
        self.assertIn(f'data-id="{ag_prof1.id}"', content_admin)
        self.assertIn(f'data-id="{ag_prof2.id}"', content_admin)


class AgendamentosRelacaoExportTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prof1 = User.objects.create_user(username='prof_rel1', email='prof1@rel.com', password='Password@123')
        self.prof1.perfil.tipo = 'PROFESSOR'
        self.prof1.perfil.aprovado = True
        self.prof1.perfil.save()

        self.prof2 = User.objects.create_user(username='prof_rel2', email='prof2@rel.com', password='Password@123')
        self.prof2.perfil.tipo = 'PROFESSOR'
        self.prof2.perfil.aprovado = True
        self.prof2.perfil.save()

        self.admin = User.objects.create_user(username='admin_rel', email='admin@rel.com', password='Password@123', is_staff=True)
        self.admin.perfil.tipo = 'ADMINISTRADOR'
        self.admin.perfil.aprovado = True
        self.admin.perfil.save()

        self.turma = Turma.objects.create(nome='1º Ano EM', turno='MANHA')
        self.sala = Sala.objects.create(nome='Lab Multiuso')

        self.d1 = date(2026, 9, 1)
        self.d2 = date(2026, 9, 5)
        self.d3 = date(2026, 9, 10)

        self.r1 = Relacao.objects.create()
        self.r2 = Relacao.objects.create()
        self.r3 = Relacao.objects.create()

        self.ag1 = Agendamento.objects.create(data=self.d1, aula=1, tipo='SALA', professor=self.prof1, turma=self.turma, sala=self.sala, observacao='Obs 1', relacao=self.r1)
        self.ag2 = Agendamento.objects.create(data=self.d2, aula=2, tipo='SALA', professor=self.prof2, turma=self.turma, sala=self.sala, observacao='Obs 2', relacao=self.r2)
        self.ag3 = Agendamento.objects.create(data=self.d3, aula=3, tipo='SALA', professor=self.prof1, turma=self.turma, sala=self.sala, observacao='Obs 3', relacao=self.r3)

    def test_navbar_possui_calendario_e_relacao(self):
        """Navbar possui itens separados para Calendário e Relação com suas respectivas rotas."""
        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn(f'<a href="{reverse("agendamentos")}">Calendário</a>', content)
        self.assertIn(f'<a href="{reverse("relacoes_lista")}">Relação</a>', content)

    def test_calendario_sem_aba_relacao(self):
        """Página do Calendário contém apenas a visualização de agendamentos, sem aba Relação."""
        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('agendamentos'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertNotIn('id="tab-relacao"', content)
        self.assertNotIn('role="tablist"', content)

    def test_tela_relacoes_listagem_e_ordenacao_por_preenchimento(self):
        """Nova tela de Relação ordena relações preenchidas recentemente no topo e vazias depois."""
        from django.utils import timezone
        agora = timezone.now()
        self.r2.preenchido_em = agora - timedelta(hours=1)
        self.r2.save()
        self.r1.preenchido_em = agora
        self.r1.save()
        self.r3.preenchido_em = None
        self.r3.save()

        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('relacoes_lista'))
        self.assertEqual(resp.status_code, 200)
        relacoes_retornadas = [item['rel'].id for item in resp.context['relacoes']]
        # Ordenação esperada: r1 (preenchido agora), r2 (preenchido 1h atrás), r3 (pendente)
        self.assertEqual(relacoes_retornadas, [self.r1.id, self.r2.id, self.r3.id])

    def test_tela_relacoes_filtros(self):
        """Filtros por período, aula e professor funcionam na tela dedicada de relações."""
        self.client.force_login(self.prof1)

        # Filtro por professor prof1
        resp_prof = self.client.get(reverse('relacoes_lista'), {'usuario': str(self.prof1.id)})
        self.assertEqual(resp_prof.context['total_relacoes'], 2)

        # Filtro por aula 2
        resp_aula = self.client.get(reverse('relacoes_lista'), {'aula': '2'})
        self.assertEqual(resp_aula.context['total_relacoes'], 1)
        self.assertEqual(resp_aula.context['relacoes'][0]['rel'].id, self.r2.id)

        # Filtro por período
        resp_periodo = self.client.get(reverse('relacoes_lista'), {
            'data_inicio': '2026-09-02',
            'data_fim': '2026-09-06'
        })
        self.assertEqual(resp_periodo.context['total_relacoes'], 1)
        self.assertEqual(resp_periodo.context['relacoes'][0]['rel'].id, self.r2.id)

    def test_vinculo_obrigatorio_e_compartilhamento_aulas_consecutivas(self):
        """Aulas seguidas com mesmo professor e mesma turma compartilham a mesma instância de Relacao."""
        d_nova = date.today() + timedelta(days=2)
        # 1ª aula agendada via detalhe
        self.client.force_login(self.prof1)
        self.client.post(reverse('agendamento_detalhe', args=[d_nova.year, d_nova.month, d_nova.day]), {
            'tipo': 'sala',
            'turma': self.turma.id,
            'reserva': [f'1:{self.sala.id}'],
        })
        ag_aula1 = Agendamento.objects.get(data=d_nova, aula=1, professor=self.prof1, turma=self.turma)
        self.assertIsNotNone(ag_aula1.relacao)

        # 2ª aula (consecutiva) agendada
        self.client.post(reverse('agendamento_detalhe', args=[d_nova.year, d_nova.month, d_nova.day]), {
            'tipo': 'sala',
            'turma': self.turma.id,
            'reserva': [f'2:{self.sala.id}'],
        })
        ag_aula2 = Agendamento.objects.get(data=d_nova, aula=2, professor=self.prof1, turma=self.turma)
        self.assertIsNotNone(ag_aula2.relacao)

        # Ambas devem compartilhar a mesma instância de Relacao
        self.assertEqual(ag_aula1.relacao.id, ag_aula2.relacao.id)
        self.assertEqual(ag_aula1.relacao.aulas_formatadas(), '1ª e 2ª Aula')

    def test_alerta_visual_preencher_relacao_no_calendario(self):
        """Card do agendamento exibe badge 'preencher relação!' se a aula já encerrou e a relação está pendente."""
        # Data no passado (horário de término garantidamente já passou)
        data_passada = date(2026, 9, 1)
        ag_passado = Agendamento.objects.get(id=self.ag1.id)
        ag_passado.data = data_passada

        # Agendamento em SALA não deve exibir alerta
        ag_passado.tipo = 'SALA'
        ag_passado.save()
        self.assertFalse(ag_passado.deve_exibir_alerta_relacao)

        # Agendamento em DISPOSITIVOS com relação vazia DEVE exibir alerta
        ag_passado.tipo = 'DISPOSITIVO'
        ag_passado.save()
        ItemDispositivo.objects.create(agendamento=ag_passado, categoria='NOTEBOOK', quantidade=1)
        self.assertTrue(ag_passado.relacao_pendente)
        self.assertTrue(ag_passado.aula_ja_passou)
        self.assertTrue(ag_passado.deve_exibir_alerta_relacao)

        # Na tela inicial (index.html), no calendário do dia correspondente:
        # 1) Deve exibir o alerta para o professor dono do agendamento (prof1)
        self.client.force_login(self.prof1)
        resp_index = self.client.get(reverse('home') + f'?data={data_passada:%Y-%m-%d}')
        self.assertEqual(resp_index.status_code, 200)
        self.assertContains(resp_index, 'badge-alerta-relacao')
        self.assertContains(resp_index, 'preencher relação!')

        # 2) Deve exibir o alerta para administradores
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('home') + f'?data={data_passada:%Y-%m-%d}')
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, 'badge-alerta-relacao')
        self.assertContains(resp_admin, 'preencher relação!')

        # 3) NÃO deve exibir o alerta para outro usuário que não seja dono nem administrador (prof2)
        self.client.force_login(self.prof2)
        resp_outro = self.client.get(reverse('home') + f'?data={data_passada:%Y-%m-%d}')
        self.assertEqual(resp_outro.status_code, 200)
        self.assertNotContains(resp_outro, '<span class="badge-alerta-relacao"')
        self.assertNotContains(resp_outro, 'preencher relação!')

        # Verifica que a coluna 'Equipamentos Móveis' aparece ANTES do nome da sala (colunas invertidas)
        conteudo = resp_index.content.decode('utf-8')
        pos_equip = conteudo.find('Equipamentos Móveis')
        pos_sala = conteudo.find(self.sala.nome)
        self.assertNotEqual(pos_equip, -1)
        self.assertNotEqual(pos_sala, -1)
        self.assertLess(pos_equip, pos_sala)

        # Na tela do calendário mensal (agendamentos.html), o alerta NÃO deve ser exibido
        resp_cal = self.client.get(reverse('agendamentos') + f'?ano={data_passada.year}&mes={data_passada.month}')
        self.assertEqual(resp_cal.status_code, 200)
        self.assertNotContains(resp_cal, 'badge-alerta-relacao')

        # Preenche a relação
        aluno = Aluno.objects.create(nome='Lucas Lima', ra='999', turma=self.turma)
        RelacaoAlunoEquipamento.objects.create(
            agendamento=ag_passado, aluno=aluno, equipamento='NOTE-01', relacao=ag_passado.relacao
        )
        ag_passado.relacao.atualizar_status_preenchimento()

        # Agora não deve mais exibir o alerta
        self.assertFalse(ag_passado.relacao_pendente)
        self.assertFalse(ag_passado.deve_exibir_alerta_relacao)

        # E na tela index não deve mais exibir o alerta para esta aula
        resp_index2 = self.client.get(reverse('home') + f'?data={data_passada:%Y-%m-%d}')
        self.assertEqual(resp_index2.status_code, 200)
        self.assertNotContains(resp_index2, 'preencher relação!')

    def test_exportar_relacoes_sem_selecao(self):
        """Tentar exportar sem registros selecionados redireciona para relacoes_lista com aviso."""
        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('exportar_relacoes'), {'formato': 'csv'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('relacoes_lista'), resp['Location'])

    def test_exportar_relacoes_csv(self):
        """Exportação para CSV gera arquivo válido com delimitador ';' e BOM UTF-8."""
        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('exportar_relacoes'), {
            'formato': 'csv',
            'ids': [str(self.ag1.id), str(self.ag3.id)],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="relacao_agendamentos_', resp['Content-Disposition'])

        conteudo = resp.content.decode('utf-8')
        self.assertTrue(conteudo.startswith('\ufeff'))
        self.assertIn('Espaço / Equipamentos;Turma;Turno', conteudo)
        self.assertIn('Obs 1', conteudo)
        self.assertIn('Obs 3', conteudo)
        self.assertNotIn('Obs 2', conteudo)

    def test_exportar_relacoes_pdf(self):
        """Exportação para PDF gera arquivo application/pdf válido com ReportLab."""
        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('exportar_relacoes'), {
            'formato': 'pdf',
            'ids': [str(self.ag1.id), str(self.ag2.id)],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="relacao_agendamentos_', resp['Content-Disposition'])
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_sincronizacao_equipamentos_aulas_consecutivas(self):
        """Salvar equipamentos em uma aula consecutiva sincroniza os registros na mesma relação."""
        d_nova = date(2026, 9, 21)
        r_comp = Relacao.objects.create()
        ag_c1 = Agendamento.objects.create(data=d_nova, aula=1, tipo='SALA', professor=self.prof1, turma=self.turma, sala=self.sala, relacao=r_comp)
        ag_c2 = Agendamento.objects.create(data=d_nova, aula=2, tipo='SALA', professor=self.prof1, turma=self.turma, sala=self.sala, relacao=r_comp)

        aluno = Aluno.objects.create(nome='Marina Santos', ra='333', turma=self.turma)

        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('relacao_agendamento', args=[ag_c1.id]), {
            'acao': 'relacao',
            f'equip_{aluno.id}': 'NOTE-55',
        })
        self.assertEqual(resp.status_code, 302)

        # Verifica se ambos os agendamentos e a relação possuem o equipamento
        self.assertTrue(RelacaoAlunoEquipamento.objects.filter(agendamento=ag_c1, aluno=aluno, equipamento='NOTE-55').exists())
        self.assertTrue(RelacaoAlunoEquipamento.objects.filter(agendamento=ag_c2, aluno=aluno, equipamento='NOTE-55').exists())
        self.assertTrue(RelacaoAlunoEquipamento.objects.filter(relacao=r_comp, aluno=aluno, equipamento='NOTE-55').exists())
        self.assertTrue(r_comp.esta_preenchida)

    def test_salvar_relacao_atualiza_sem_duplicar_e_limpa_vazios(self):
        """Salvar a relação de alunos atualiza os registros existentes e remove entradas vazias sem criar duplicatas."""
        aluno1 = Aluno.objects.create(nome='Bruno Dias', ra='111', turma=self.turma)
        aluno2 = Aluno.objects.create(nome='Carla Lima', ra='222', turma=self.turma)

        self.client.force_login(self.prof1)
        # Primeira gravação
        resp1 = self.client.post(reverse('relacao_agendamento', args=[self.ag1.id]), {
            'acao': 'relacao',
            f'equip_{aluno1.id}': 'NOTE-10',
            f'equip_{aluno2.id}': 'NOTE-20',
        })
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(RelacaoAlunoEquipamento.objects.filter(agendamento=self.ag1).count(), 2)

        # Segunda gravação: altera aluno1 para NOTE-15 e esvazia aluno2
        resp2 = self.client.post(reverse('relacao_agendamento', args=[self.ag1.id]), {
            'acao': 'relacao',
            f'equip_{aluno1.id}': 'NOTE-15',
            f'equip_{aluno2.id}': '',
        })
        self.assertEqual(resp2.status_code, 302)
        # Deve haver apenas 1 registro (aluno1 atualizado e aluno2 removido)
        self.assertEqual(RelacaoAlunoEquipamento.objects.filter(agendamento=self.ag1).count(), 1)
        r1 = RelacaoAlunoEquipamento.objects.get(agendamento=self.ag1, aluno=aluno1)
        self.assertEqual(r1.equipamento, 'NOTE-15')

    def test_agendamento_dispositivo_atualiza_existente_sem_duplicar(self):
        """Submeter reserva de dispositivos na mesma aula e turma atualiza o agendamento em vez de criar um novo."""
        Equipamento.objects.create(apelido='NOTE-01', categoria='NOTEBOOK', status='ATIVO', fixo=False)
        Equipamento.objects.create(apelido='NOTE-02', categoria='NOTEBOOK', status='ATIVO', fixo=False)
        d = date.today() + timedelta(days=1)

        self.client.force_login(self.prof1)
        # Primeira submissão
        resp1 = self.client.post(reverse('agendamento_detalhe', args=[d.year, d.month, d.day]), {
            'tipo': 'dispositivo',
            'turma': self.turma.id,
            'observacao': 'Obs inicial',
            'qtd_1_NOTEBOOK': '1',
        })
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(Agendamento.objects.filter(data=d, aula=1, professor=self.prof1, tipo='DISPOSITIVO').count(), 1)

        # Segunda submissão na mesma aula e data: altera observação e quantidade
        resp2 = self.client.post(reverse('agendamento_detalhe', args=[d.year, d.month, d.day]), {
            'tipo': 'dispositivo',
            'turma': self.turma.id,
            'observacao': 'Obs atualizada',
            'qtd_1_NOTEBOOK': '2',
        })
        self.assertEqual(resp2.status_code, 302)
        # Continua existindo apenas 1 agendamento, devidamente atualizado
        qs = Agendamento.objects.filter(data=d, aula=1, professor=self.prof1, tipo='DISPOSITIVO')
        self.assertEqual(qs.count(), 1)
        ag = qs.first()
        self.assertEqual(ag.observacao, 'Obs atualizada')
        self.assertEqual(ag.itens.get(categoria='NOTEBOOK').quantidade, 2)

    def test_salvar_relacao_fixo_nao_propaga_para_futuros(self):
        """Salvar a relação em um agendamento fixo não deve propagar a relação para datas futuras da série."""
        aluno = Aluno.objects.create(nome='Diego Santos', ra='333', turma=self.turma)
        ag_futuro = Agendamento.objects.create(
            data=date.today() + timedelta(days=7),
            aula=1,
            tipo='DISPOSITIVO',
            professor=self.prof1,
            turma=self.turma,
            fixo=True,
            fixo_grupo_id='grupo-fixo-teste-123',
        )
        self.ag1.fixo = True
        self.ag1.fixo_grupo_id = 'grupo-fixo-teste-123'
        self.ag1.save()

        self.client.force_login(self.prof1)
        resp = self.client.post(reverse('relacao_agendamento', args=[self.ag1.id]), {
            'acao': 'relacao',
            f'equip_{aluno.id}': 'NOTE-55',
        })
        self.assertEqual(resp.status_code, 302)
        # self.ag1 deve ter a relação
        self.assertTrue(RelacaoAlunoEquipamento.objects.filter(agendamento=self.ag1, aluno=aluno, equipamento='NOTE-55').exists())
        # ag_futuro NÃO deve ter recebido a relação
        self.assertFalse(RelacaoAlunoEquipamento.objects.filter(agendamento=ag_futuro).exists())

    def test_tela_relacoes_exclui_placeholders_fixos_futuros_sem_relacao(self):
        """A tela Relação sem filtros exclui agendamentos fixos futuros que não possuem relação preenchida."""
        hoje = date.today()
        # Agendamento de hoje
        rel_hoje = Relacao.objects.create()
        ag_hoje = Agendamento.objects.create(
            data=hoje,
            aula=2,
            tipo='SALA',
            sala=self.sala,
            professor=self.prof1,
            turma=self.turma,
            relacao=rel_hoje,
        )
        # Agendamento fixo futuro vazio (placeholder)
        rel_futuro = Relacao.objects.create()
        ag_fixo_futuro = Agendamento.objects.create(
            data=hoje + timedelta(days=30),
            aula=2,
            tipo='SALA',
            sala=self.sala,
            professor=self.prof1,
            turma=self.turma,
            fixo=True,
            fixo_grupo_id='grupo-placeholder',
            relacao=rel_futuro,
        )

        self.client.force_login(self.prof1)
        resp = self.client.get(reverse('relacoes_lista'))
        self.assertEqual(resp.status_code, 200)
        rel_ids = [item['rel'].id for item in resp.context['relacoes']]
        # rel_hoje deve estar na listagem
        self.assertIn(rel_hoje.id, rel_ids)
        # rel_futuro (sem relação preenchida) NÃO deve poluir a listagem padrão
        self.assertNotIn(rel_futuro.id, rel_ids)


class OcorrenciasTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Admin
        self.admin = User.objects.create_user(
            username='admin_oco',
            email='admin_oco@teste.com',
            password='senha_admin_123'
        )
        self.admin.perfil.tipo = 'ADMINISTRADOR'
        self.admin.perfil.aprovado = True
        self.admin.perfil.save()

        # Professor comum
        self.prof = User.objects.create_user(
            username='prof_oco',
            email='prof_oco@teste.com',
            password='senha_prof_123'
        )
        self.prof.perfil.tipo = 'PROFESSOR'
        self.prof.perfil.aprovado = True
        self.prof.perfil.save()

        # Sala e Turma
        self.sala = Sala.objects.create(nome='Sala Info 1', capacidade=30, ativo=True)
        self.turma = Turma.objects.create(nome='7º B', turno='MANHA')
        self.aluno1 = Aluno.objects.create(nome='Lucas Silva', ra='111222', digito='1', uf='SP', turma=self.turma)
        self.aluno2 = Aluno.objects.create(nome='Mariana Lima', ra='333444', digito='2', uf='SP', turma=self.turma)

        # Equipamentos
        self.equip1 = Equipamento.objects.create(apelido='NOTE-01', categoria='NOTEBOOK', status='ATIVO')
        self.equip2 = Equipamento.objects.create(apelido='NOTE-02', categoria='NOTEBOOK', status='ATIVO')

        # Agendamento
        self.relacao = Relacao.objects.create()
        self.ag = Agendamento.objects.create(
            data=date.today(),
            aula=3,
            tipo='DISPOSITIVO',
            professor=self.prof,
            turma=self.turma,
            relacao=self.relacao,
        )
        # Associa alunos e equipamentos na relação
        RelacaoAlunoEquipamento.objects.create(
            agendamento=self.ag,
            relacao=self.relacao,
            aluno=self.aluno1,
            equipamento='NOTE-01'
        )

    def _gerar_foto_teste(self, nome='evidencia.jpg'):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='orange')
        img.save(buf, 'JPEG')
        buf.seek(0)
        return SimpleUploadedFile(nome, buf.read(), content_type='image/jpeg')

    def test_permissao_acesso_bloqueia_nao_admin(self):
        """Usuário comum ou deslogado não pode acessar views ou APIs de ocorrências."""
        # Não logado
        resp = self.client.get(reverse('ocorrencia_criar'))
        self.assertEqual(resp.status_code, 302)

        # Logado como professor
        self.client.force_login(self.prof)
        resp_lista = self.client.get(reverse('ocorrencias_lista'))
        self.assertEqual(resp_lista.status_code, 302)  # Redireciona para home

        resp_criar = self.client.get(reverse('ocorrencia_criar'))
        self.assertEqual(resp_criar.status_code, 302)

        # API bloqueada para professor
        resp_api = self.client.get(reverse('api_agendamentos_por_data') + f'?data={date.today():%Y-%m-%d}')
        self.assertEqual(resp_api.status_code, 403)

        resp_ctx = self.client.get(reverse('api_agendamento_contexto', args=[self.ag.id]))
        self.assertEqual(resp_ctx.status_code, 403)

    def test_cenario_a_abrir_com_agendamento(self):
        """Cenário A: Admin abre o formulário a partir de um agendamento pré-existente."""
        self.client.force_login(self.admin)
        url = reverse('ocorrencia_criar') + f'?agendamento_id={self.ag.id}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['ag_selecionado'].id, self.ag.id)
        self.assertEqual(len(resp.context['alunos_disponiveis']), 2)
        # Equipamento da relação NOTE-01 deve estar na lista de relacionados
        apelidos_rel = [e.apelido for e in resp.context['equipamentos_relacionados']]
        self.assertIn('NOTE-01', apelidos_rel)

    def test_cenario_b_api_e_selecao_dinamica(self):
        """Cenário B: Admin consulta agendamentos por data e contexto assíncrono."""
        self.client.force_login(self.admin)
        # 1. API agendamentos por data
        url_api = reverse('api_agendamentos_por_data') + f'?data={self.ag.data:%Y-%m-%d}'
        resp_api = self.client.get(url_api)
        self.assertEqual(resp_api.status_code, 200)
        data_json = resp_api.json()
        self.assertTrue(data_json['sucesso'])
        self.assertEqual(len(data_json['agendamentos']), 1)
        self.assertEqual(data_json['agendamentos'][0]['id'], self.ag.id)

        # 2. API contexto do agendamento
        url_ctx = reverse('api_agendamento_contexto', args=[self.ag.id])
        resp_ctx = self.client.get(url_ctx)
        self.assertEqual(resp_ctx.status_code, 200)
        ctx_json = resp_ctx.json()
        self.assertTrue(ctx_json['sucesso'])
        self.assertEqual(ctx_json['agendamento']['professor_id'], self.prof.id)
        # Aluno 1 deve ter NOTE-01 indicado
        aluno1_json = next(a for a in ctx_json['alunos'] if a['id'] == self.aluno1.id)
        self.assertEqual(aluno1_json['equipamento'], 'NOTE-01')

    def test_criar_ocorrencia_com_multiplas_fotos_e_envolvidos(self):
        """Criação completa de ocorrência com múltiplos alunos, equipamentos e fotos."""
        self.client.force_login(self.admin)
        foto1 = self._gerar_foto_teste('dano_tela.jpg')
        foto2 = self._gerar_foto_teste('teclado_quebrado.jpg')

        dados = {
            'agendamento': self.ag.id,
            'data_hora_fato': f'{self.ag.data:%Y-%m-%d}T08:40',
            'professor': self.prof.id,
            'descricao': 'Queda acidental do notebook durante a troca de exercícios.',
            'alunos': [self.aluno1.id],
            'equipamentos': [self.equip1.id],
            'fotos': [foto1, foto2],
        }

        resp = self.client.post(reverse('ocorrencia_criar'), dados)
        self.assertEqual(resp.status_code, 302)

        # Verifica no banco de dados
        oco = Ocorrencia.objects.filter(agendamento=self.ag).first()
        self.assertIsNotNone(oco)
        self.assertEqual(oco.professor, self.prof)
        self.assertEqual(oco.criado_por, self.admin)
        self.assertIn(self.aluno1, oco.alunos.all())
        self.assertIn(self.equip1, oco.equipamentos.all())
        # Verifica fotos vinculadas
        self.assertEqual(oco.fotos.count(), 2)

        # Detalhe da ocorrência
        resp_detalhe = self.client.get(reverse('ocorrencia_detalhe', args=[oco.id]))
        self.assertEqual(resp_detalhe.status_code, 200)
        self.assertContains(resp_detalhe, 'Queda acidental')
        self.assertContains(resp_detalhe, self.aluno1.nome)
        self.assertContains(resp_detalhe, self.equip1.apelido)

    def test_excluir_ocorrencia_admin(self):
        """Admin pode excluir uma ocorrência registrada."""
        self.client.force_login(self.admin)
        oco = Ocorrencia.objects.create(
            data_hora_fato=timezone.now(),
            descricao='Teste exclusao',
            professor=self.prof,
            criado_por=self.admin
        )
        self.assertEqual(Ocorrencia.objects.filter(id=oco.id).count(), 1)

        resp = self.client.post(reverse('ocorrencia_excluir', args=[oco.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Ocorrencia.objects.filter(id=oco.id).count(), 0)

    def test_visibilidade_gatilhos_ui_admin_vs_professor(self):
        """Verifica se os elementos visuais aparecem para admin e não aparecem para professor."""
        # 1. Admin na visualização do agendamento / relação
        self.client.force_login(self.admin)
        resp_rel_admin = self.client.get(reverse('relacao_agendamento', args=[self.ag.id]))
        self.assertEqual(resp_rel_admin.status_code, 200)
        self.assertContains(resp_rel_admin, 'Ocorrência')
        self.assertContains(resp_rel_admin, 'ocorrenciaIcon')

        # 2. Professor comum na visualização do agendamento
        self.client.force_login(self.prof)
        resp_rel_prof = self.client.get(reverse('relacao_agendamento', args=[self.ag.id]))
        self.assertEqual(resp_rel_prof.status_code, 200)
        # O botão Ocorrência NÃO deve aparecer no topo à direita para professor comum
        self.assertNotContains(resp_rel_prof, reverse('ocorrencia_criar') + f'?agendamento_id={self.ag.id}')
        self.assertNotContains(resp_rel_prof, 'id="ocorrenciaIcon"')

    def test_editar_ocorrencia_permissao(self):
        """Apenas administradores aprovados podem acessar a tela de edição."""
        oco = Ocorrencia.objects.create(
            data_hora_fato=timezone.now(),
            descricao='Dano inicial',
            professor=self.prof,
            criado_por=self.admin
        )

        # Não autenticado -> redirect login
        self.client.logout()
        resp_anon = self.client.get(reverse('ocorrencia_editar', args=[oco.id]))
        self.assertEqual(resp_anon.status_code, 302)

        # Professor comum -> redirect home
        self.client.force_login(self.prof)
        resp_prof = self.client.get(reverse('ocorrencia_editar', args=[oco.id]))
        self.assertEqual(resp_prof.status_code, 302)

        # Admin -> 200 OK
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('ocorrencia_editar', args=[oco.id]))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertTrue(resp_admin.context['editando'])
        self.assertEqual(resp_admin.context['ocorrencia'].id, oco.id)

    def test_editar_ocorrencia_campos_e_fotos(self):
        """Admin edita dados da ocorrência, remove foto antiga e anexa nova foto."""
        foto1 = self._gerar_foto_teste('foto1.jpg')
        foto2 = self._gerar_foto_teste('foto2.jpg')

        oco = Ocorrencia.objects.create(
            data_hora_fato=timezone.now(),
            descricao='Dano leve inicial',
            professor=self.prof,
            criado_por=self.admin
        )
        oco_foto1 = OcorrenciaFoto.objects.create(ocorrencia=oco, foto=foto1)
        oco_foto2 = OcorrenciaFoto.objects.create(ocorrencia=oco, foto=foto2)

        self.client.force_login(self.admin)
        nova_foto = self._gerar_foto_teste('foto3_nova.png')

        resp = self.client.post(reverse('ocorrencia_editar', args=[oco.id]), {
            'data_hora_fato': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'professor': self.prof.id,
            'descricao': 'Descrição editada com sucesso e novos detalhes.',
            'equipamentos': [self.equip1.id],
            'alunos': [self.aluno1.id],
            'remover_fotos': [oco_foto1.id],
            'fotos': [nova_foto],
        })
        self.assertEqual(resp.status_code, 302)

        oco.refresh_from_db()
        self.assertEqual(oco.descricao, 'Descrição editada com sucesso e novos detalhes.')
        self.assertIn(self.equip1, oco.equipamentos.all())
        self.assertIn(self.aluno1, oco.alunos.all())

        # Foto 1 deve ter sido removida, Foto 2 mantida, e uma nova foto adicionada
        self.assertFalse(oco.fotos.filter(id=oco_foto1.id).exists())
        self.assertTrue(oco.fotos.filter(id=oco_foto2.id).exists())
        self.assertEqual(oco.fotos.count(), 2)

    def test_botoes_editar_ocorrencia_na_ui(self):
        """Verifica se o botão de editar aparece no detalhe da ocorrência e na listagem."""
        oco = Ocorrencia.objects.create(
            data_hora_fato=timezone.now(),
            descricao='Teste botão editar',
            professor=self.prof,
            criado_por=self.admin
        )

        self.client.force_login(self.admin)

        # 1. Tela de Detalhes
        resp_detalhe = self.client.get(reverse('ocorrencia_detalhe', args=[oco.id]))
        self.assertEqual(resp_detalhe.status_code, 200)
        self.assertContains(resp_detalhe, reverse('ocorrencia_editar', args=[oco.id]))
        self.assertContains(resp_detalhe, 'Editar')

        # 2. Tela de Listagem
        resp_lista = self.client.get(reverse('ocorrencias_lista'))
        self.assertEqual(resp_lista.status_code, 200)
        self.assertContains(resp_lista, reverse('ocorrencia_editar', args=[oco.id]))

    def test_foto_ocorrencia_endpoint(self):
        """Endpoint foto_ocorrencia serve foto com cabeçalhos corretos para admin e restringe professor."""
        foto = self._gerar_foto_teste('foto_teste.jpg')
        oco = Ocorrencia.objects.create(
            data_hora_fato=timezone.now(),
            descricao='Teste foto endpoint',
            professor=self.prof,
            criado_por=self.admin
        )
        foto_obj = OcorrenciaFoto.objects.create(ocorrencia=oco, foto=foto)

        # Não logado -> redirect login
        self.client.logout()
        resp_anon = self.client.get(reverse('foto_ocorrencia', args=[foto_obj.id]))
        self.assertEqual(resp_anon.status_code, 302)

        # Professor comum -> 403 Forbidden
        self.client.force_login(self.prof)
        resp_prof = self.client.get(reverse('foto_ocorrencia', args=[foto_obj.id]))
        self.assertEqual(resp_prof.status_code, 403)

        # Admin -> 200 OK com content_type image/jpeg
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('foto_ocorrencia', args=[foto_obj.id]))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertEqual(resp_admin['Content-Type'], 'image/jpeg')

    def test_ocorrencia_pdf_download(self):
        """Geração e download de documento PDF oficial com ReportLab contendo dados e fotos."""
        foto = self._gerar_foto_teste('evidencia_pdf.jpg')
        oco = Ocorrencia.objects.create(
            agendamento=self.ag,
            data_hora_fato=timezone.now(),
            descricao='Cabo de carregador cortado e tela trincada no tablet durante atividade.',
            professor=self.prof,
            criado_por=self.admin
        )
        oco.alunos.add(self.aluno1)
        oco.equipamentos.add(self.equip1)
        OcorrenciaFoto.objects.create(ocorrencia=oco, foto=foto)

        # Professor comum -> redirect home
        self.client.force_login(self.prof)
        resp_prof = self.client.get(reverse('ocorrencia_pdf', args=[oco.id]))
        self.assertEqual(resp_prof.status_code, 302)

        # Admin -> 200 OK, application/pdf
        self.client.force_login(self.admin)
        resp_admin = self.client.get(reverse('ocorrencia_pdf', args=[oco.id]))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertEqual(resp_admin['Content-Type'], 'application/pdf')
        self.assertIn(f'ocorrencia_{oco.id}.pdf', resp_admin['Content-Disposition'])
        # Verifica se o arquivo gerado é um PDF válido
        self.assertTrue(resp_admin.content.startswith(b'%PDF'))


class ImagemServiceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='user_foto',
            email='foto@labhub.com',
            password='SenhaForte123!'
        )
        self.user.perfil.aprovado = True
        self.user.perfil.save()

    def _criar_imagem_png_transparente(self, largura=1200, altura=800):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        img = Image.new('RGBA', (largura, altura), color=(255, 0, 0, 128))
        img.save(buf, 'PNG')
        buf.seek(0)
        return SimpleUploadedFile('transparente.png', buf.read(), content_type='image/png')

    def test_processar_imagem_rgba_e_redimensionamento(self):
        """processar_imagem converte transparência para fundo branco e respeita max_lado."""
        from PIL import Image
        import io
        from app.services.imagem_service import processar_imagem
        arquivo = self._criar_imagem_png_transparente(largura=1200, altura=800)

        dados, mime = processar_imagem(arquivo, max_lado=400, qualidade=80, formato='JPEG')
        self.assertIsInstance(dados, bytes)
        self.assertEqual(mime, 'image/jpeg')

        img_result = Image.open(io.BytesIO(dados))
        self.assertEqual(img_result.format, 'JPEG')
        self.assertEqual(img_result.mode, 'RGB')
        self.assertLessEqual(max(img_result.size), 400)

    def test_processar_foto_para_storage(self):
        """processar_foto_para_storage retorna ContentFile pronto para salvar em ImageField."""
        from PIL import Image
        from django.core.files.base import ContentFile
        from app.services.imagem_service import processar_foto_para_storage
        arquivo = self._criar_imagem_png_transparente(largura=500, altura=500)

        conteudo = processar_foto_para_storage(arquivo, max_lado=500, qualidade=85)
        self.assertIsInstance(conteudo, ContentFile)
        self.assertTrue(conteudo.name.endswith('.jpg'))

        # Confirma que é legível pelo Pillow
        img = Image.open(conteudo)
        self.assertEqual(img.format, 'JPEG')

    def test_upload_foto_perfil_comprimida(self):
        """Upload de foto de perfil comprime via processar_imagem e foto_perfil serve bytes."""
        self.client.force_login(self.user)
        foto = self._criar_imagem_png_transparente(largura=800, altura=800)

        resp = self.client.post(reverse('minha_conta'), {
            'acao': 'foto',
            'foto': foto,
        })
        self.assertEqual(resp.status_code, 302)

        self.user.perfil.refresh_from_db()
        self.assertTrue(self.user.perfil.tem_foto)
        self.assertIsNotNone(self.user.perfil.foto_dados)
        self.assertEqual(self.user.perfil.foto_mime, 'image/jpeg')

        # Testar visualização da foto de perfil
        resp_foto = self.client.get(reverse('foto_perfil', args=[self.user.id]))
        self.assertEqual(resp_foto.status_code, 200)
        self.assertEqual(resp_foto['Content-Type'], 'image/jpeg')
        self.assertEqual(bytes(resp_foto.content), bytes(self.user.perfil.foto_dados))

    def test_processar_imagem_jpeg_progressivo_e_exif(self):
        """processar_imagem processa JPEGs progressivos com metadados EXIF sem corromper."""
        from PIL import Image
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from app.services.imagem_service import processar_imagem, processar_foto_para_storage

        # Cria JPEG progressivo com orientação EXIF
        buf = io.BytesIO()
        im = Image.new('RGB', (1600, 1200), color=(50, 100, 150))
        exif = im.getexif()
        exif[0x0112] = 6
        im.save(buf, 'JPEG', quality=90, progressive=True, exif=exif)
        buf.seek(0)

        upload_file = SimpleUploadedFile('foto_camera.jpg', buf.read(), content_type='image/jpeg')

        dados, mime = processar_imagem(upload_file, max_lado=1200, qualidade=85)
        self.assertIsInstance(dados, bytes)
        self.assertEqual(mime, 'image/jpeg')

        img_res = Image.open(io.BytesIO(dados))
        self.assertEqual(img_res.format, 'JPEG')
        self.assertLessEqual(max(img_res.size), 1200)

        # Testa também com processar_foto_para_storage preservando nome
        upload_file.seek(0)
        c_file = processar_foto_para_storage(upload_file, nome_original=upload_file.name)
        self.assertTrue(c_file.name.startswith('foto_camera'))
        self.assertTrue(c_file.name.endswith('.jpg'))


class RelacaoKioskETravaSenhaTest(TestCase):
    def setUp(self):
        self.senha_padrao = 'SenhaForte123!'
        self.user = User.objects.create_user(
            username='prof_kiosk',
            email='kiosk@escola.com',
            password=self.senha_padrao
        )
        self.user.perfil.tipo = 'PROFESSOR'
        self.user.perfil.aprovado = True
        self.user.perfil.save()
        self.turma = Turma.objects.create(nome='3º Info', turno='MANHA')
        self.ag = Agendamento.objects.create(
            data=date(2026, 9, 20),
            aula=1,
            professor=self.user,
            turma=self.turma,
            tipo='DISPOSITIVO'
        )

    def test_verificar_senha_correta(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('verificar_senha'), {'senha': self.senha_padrao})
        self.assertEqual(resp.status_code, 200)
        dados = resp.json()
        self.assertTrue(dados.get('valida'))

    def test_verificar_senha_incorreta(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('verificar_senha'), {'senha': 'senha_errada'})
        self.assertEqual(resp.status_code, 400)
        dados = resp.json()
        self.assertFalse(dados.get('valida'))

    def test_verificar_senha_vazia(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('verificar_senha'), {'senha': ''})
        self.assertEqual(resp.status_code, 400)
        dados = resp.json()
        self.assertFalse(dados.get('valida'))

    def test_verificar_senha_metodo_get(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('verificar_senha'))
        self.assertEqual(resp.status_code, 405)

    def test_verificar_senha_anonimo(self):
        resp = self.client.post(reverse('verificar_senha'), {'senha': self.senha_padrao})
        self.assertEqual(resp.status_code, 302)

    def test_elementos_tela_cheia_e_cadeado_na_relacao(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('relacao_agendamento', args=[self.ag.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="btnModoTelaCheia"')
        self.assertContains(resp, 'id="btnCadeadoTrava"')
        self.assertContains(resp, 'id="modalDesbloquearRelacao"')
        self.assertContains(resp, 'id="bannerKioskTravado"')
        self.assertContains(resp, 'labhub_relacao_bloqueada_url')

    def test_trava_global_quiosque_no_layout(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'labhub_relacao_bloqueada_url')




