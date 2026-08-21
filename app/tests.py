"""
Testes unitários para o LabHub e a funcionalidade de Equipamentos Fixos.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from app.models import Sala, Equipamento, Perfil
from app.forms import EquipamentoForm


class EquipamentoFixoTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Usuário Admin aprovado
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password123'
        )
        self.admin.perfil.tipo = 'ADMINISTRADOR'
        self.admin.perfil.aprovado = True
        self.admin.perfil.save()

        # Sala de teste
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
            'sala': '',  # Sem sala
        }
        form = EquipamentoForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('sala', form.errors)

    def test_formulario_equipamento_movel_limpa_sala(self):
        """Testa que se fixo=False, qualquer sala enviada é limpa (None)."""
        data = {
            'apelido': 'NOTE-02',
            'categoria': 'NOTEBOOK',
            'status': 'ATIVO',
            'fixo': False,
            'sala': self.sala.id,  # Enviado por engano ou resquício
        }
        form = EquipamentoForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        equip = form.save()
        self.assertFalse(equip.fixo)
        self.assertIsNone(equip.sala)

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

        # Visualizar listagem
        response = self.client.get(reverse('equipamentos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PC-01')
        self.assertContains(response, 'Laboratório 1')

        # Visualizar formulário de novo equipamento
        response_novo = self.client.get(reverse('equipamento_novo'))
        self.assertEqual(response_novo.status_code, 200)
        self.assertContains(response_novo, 'id_fixo')
        self.assertContains(response_novo, 'grupo-sala')

        # Exportar CSV
        response_csv = self.client.get(reverse('exportar_equipamentos'))
        self.assertEqual(response_csv.status_code, 200)
        conteudo_csv = response_csv.content.decode('utf-8')
        self.assertIn('Fixo', conteudo_csv)
        self.assertIn('Sala', conteudo_csv)
        self.assertIn('Sim', conteudo_csv)
        self.assertIn('Laboratório 1', conteudo_csv)
