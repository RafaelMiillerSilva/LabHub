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

from app.backends import EmailBackend
from app.forms import CadastroForm, EquipamentoForm
from app.models import Agendamento, Aluno, Equipamento, ItemDispositivo, Sala, Turma


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



