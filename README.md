# LabHub 🧪💻

> **Sistema Inteligente, Gratuito e Open Source para Gestão de Laboratórios e Equipamentos Escolares.**

O **LabHub** é uma plataforma web completa desenvolvida em **Python/Django** para modernizar o controle de ambientes e recursos pedagógicos em escolas públicas e privadas. O projeto elimina anotações manuais em papel e planilhas descentralizadas, centralizando a reserva de espaços, o controle de dispositivos móveis e a rastreabilidade patrimonial em uma interface intuitiva, segura e responsiva.

---

## 📋 Proposta do Projeto

Em muitas instituições de ensino, o compartilhamento de salas de informática, laboratórios e carrinhos com notebooks/tablets gera conflitos de horários, perda de aparelhos e falta de histórico sobre quem utilizou determinado recurso.

O **LabHub** foi concebido para resolver essas dores com simplicidade:
1. **Autonomia aos Professores:** O corpo docente solicita salas ou equipamentos com antecedência pelo computador ou celular.
2. **Controle à Gestão:** A coordenação e os responsáveis pelos laboratórios contam com aprovação de contas, relatórios de uso e controle em tempo real de estoque.
3. **Rastreabilidade Patrimonial:** Registro exato de qual aluno retirou e devolveu cada dispositivo durante a aula.
4. **Custo Zero & Liberdade (Open Source):** Sem mensalidades ou travas de fornecedor; a escola pode instalar em servidor próprio ou hospedar na nuvem gratuitamente.

---

## 🚀 Funcionalidades Principais

### 🏫 1. Reserva Inteligente de Salas e Laboratórios
- Grade horária organizada em **9 aulas diárias** padronizadas.
- Bloqueio automático contra choques de horário e conflitos de reserva simultânea.
- Visualização por **calendário mensal** e **grade semanal** interativa.

### 💻 2. Gestão de Inventário e Equipamentos
- Controle de notebooks, tablets, smartphones, projetores e kits de robótica.
- Cadastro detalhado com **número de série**, **número de patrimônio** e fotos reais dos aparelhos.
- Cálculo dinâmico do saldo disponível aula por aula.

### 📋 3. Relação Aluno × Aparelho na Aula
- Registro em sala de qual dispositivo específico foi entregue a cada estudante.
- Suporte ao padrão acadêmico completo: **Turma, Nome, RA, Dígito e UF**.
- Histórico transparente para preservação do patrimônio e rápida apuração de ocorrências.

### 👥 4. Gestão de Turmas e Importação por Planilhas
- Listagem automática de turmas em **ordem alfabética** e por turno.
- Importação em massa de alunos via arquivos **Excel (.xlsx)** ou **CSV**.
- Diagnóstico inteligente na importação, indicando exatamente quais alunos são duplicados ou possuem dados incompletos.

### 🏷️ 5. Etiquetas
- Geração de etiquetas prontas para impressoras térmicas (ex: Zebra, Elgin) e impressoras convencionais.
- Impressão individual ou em lote para etiquetagem física ágil dos aparelhos.

### 💬 6. Comunicação e Chat em Tempo Real
- Chat interno privativo entre professores e a equipe gestora.
- Sininho de notificações instantâneas sobre aprovação de reservas e avisos do sistema.

### 🛡️ 7. Painel do Gestor e Auditoria
- Fluxo de aprovação de novos cadastros de professores para segurança do ambiente.
- Redefinição de senhas com autorização da equipe gestora.
- Exportação de relatórios mensais completos de reservas em formato Excel (.xlsx).

### 🌓 8. Acessibilidade e Experiência do Usuário
- Alternância nativa entre **Modo Claro (Light)** e **Modo Escuro (Dark)** com salvamento automático de preferência.
- Layout 100% responsivo (**Mobile-First**), otimizado para celulares e tablets.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.10+
- **Framework Web:** Django 4.2+
- **Banco de Dados:** SQLite (padrão, sem dependências adicionais) ou PostgreSQL/MySQL
- **Frontend:** HTML5, Vanilla CSS com Design Tokens e variáveis personalizadas, Bootstrap e JavaScript
- **Processamento de Planilhas e PDFs:** OpenPyXL, ReportLab e Pillow

---

## 🌐 Guia Passo a Passo: Hospedando no PythonAnywhere e Cadastrando sua Escola

O **PythonAnywhere** é uma excelente plataforma para hospedar o LabHub, inclusive no plano gratuito (*Beginner*). Siga o roteiro abaixo para colocar o sistema no ar:

### Passo 1: Criar uma conta no PythonAnywhere
1. Acesse [pythonanywhere.com](https://www.pythonanywhere.com/) e clique em **Pricing & signup**.
2. Escolha o plano **Create a Beginner account** (Gratuito).
3. Defina seu nome de usuário (ex: `minhaescola`). O seu site ficará disponível no endereço `https://minhaescola.pythonanywhere.com`.

---

### Passo 2: Abrir o Bash Console e Clonar o Repositório
1. No painel do PythonAnywhere, vá na aba **Consoles** e abra um console **Bash**.
2. Clone o repositório do LabHub executando:
   ```bash
   git clone https://github.com/RafaelMiillerSilva/LabHub.git
   cd LabHub
   ```

---

### Passo 3: Criar e Ativar o Ambiente Virtual (Virtualenv)
No mesmo terminal Bash, crie o ambiente virtual com Python 3.10 ou superior:
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Passo 4: Instalar as Dependências
Com o ambiente ativado (você verá `(venv)` no início da linha de comando), instale os pacotes:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Passo 5: Configurar o Arquivo de Variáveis de Ambiente (`.env`)
Crie o arquivo `.env` a partir do modelo de exemplo:
```bash
cp .env.example .env
```

Para gerar uma chave secreta exclusiva e segura, no terminal Bash do PythonAnywhere, rode:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Abra o arquivo `.env` no PythonAnywhere (`nano .env` ou pelo editor de arquivos da aba "Files"):
```env
SECRET_KEY=<cole_a_chave_gerada_aqui>
DEBUG=False
ALLOWED_HOSTS=minhaescola.pythonanywhere.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://minhaescola.pythonanywhere.com
```
> *(Para salvar no nano: pressione `Ctrl + O`, depois `Enter`, e saia com `Ctrl + X`)*.

---

### Passo 6: Executar as Migrações e Criar o Usuário Administrador
Prepare o banco de dados e crie a conta de administrador principal:
```bash
python manage.py migrate
python manage.py createsuperuser
```
Informe o nome de usuário, e-mail e uma senha segura quando solicitado.

---

### Passo 7: Coletar os Arquivos Estáticos (Static Files)
Execute o comando para reunir os arquivos de estilo, scripts e ícones:
```bash
python manage.py collectstatic --noinput
```

---

### Passo 8: Configurar a Aba "Web" no PythonAnywhere
No topo do painel do PythonAnywhere, clique na aba **Web** e em **Add a new web app**:
1. Escolha **Manual configuration** e selecione a versão do Python (ex: **Python 3.10**).
2. Na tela de configurações da sua aplicação Web:
   - **Source code:** `/home/minhaescola/LabHub`
   - **Working directory:** `/home/minhaescola/LabHub`
   - **Virtualenv:** `/home/minhaescola/LabHub/venv`

3. Na seção **Static files**, adicione o mapeamento:
   | URL | Directory |
   | :--- | :--- |
   | `/static/` | `/home/minhaescola/LabHub/staticfiles` |
   | `/media/` | `/home/minhaescola/LabHub/media` |

4. Na seção **Code**, clique no link do arquivo **WSGI configuration file** para editá-lo. Apague todo o conteúdo padrão e cole o seguinte trecho:
   ```python
   import os
   import sys

   path = '/home/minhaescola/LabHub'
   if path not in sys.path:
       sys.path.append(path)

   os.environ['DJANGO_SETTINGS_MODULE'] = 'LabHub.settings'

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
   > *(Substitua `minhaescola` pelo seu usuário real do PythonAnywhere e clique em **Save** no topo direito).*

---

### Passo 9: Recarregar a Aplicação
Volte para a aba **Web** e clique no botão verde **"Reload minhaescola.pythonanywhere.com"**.

Pronto! Acesse `https://minhaescola.pythonanywhere.com` no seu navegador.

---

## 🏫 Cadastrando e Configurando sua Escola

Ao acessar o sistema pela primeira vez, siga esta ordem recomendada para colocar a escola em operação:

1. **Login do Administrador:**
   - Faça login com o usuário e senha cadastrados no comando `createsuperuser`.

2. **Cadastro de Salas e Laboratórios:**
   - Vá no menu **Salas** e adicione os espaços que podem ser reservados (ex: *Laboratório de Informática 1*, *Sala Maker / Robótica*, *Auditório*, *Sala de Vídeo*).

3. **Cadastro de Turmas e Alunos:**
   - Vá no menu **Turmas** e cadastre as turmas da instituição (ex: *6º A*, *9º B*, *3º EM* com seus respectivos turnos).
   - Clique na turma criada para cadastrar os alunos individualmente ou faça o download da planilha modelo (CSV) e envie a lista completa da turma com **Nome, RA, Dígito e UF**.

4. **Cadastro de Equipamentos Pedagógicos:**
   - Acesse o menu **Equipamentos** e adicione os aparelhos disponíveis na escola (Notebooks, Tablets, Smartphones ou Projetores), informando marca, modelo, número de série e patrimônio.
   - Use o botão de **Etiquetas** para gerar e imprimir as etiquetas de identificação com QR Code e código de barras para colar nos aparelhos.

5. **Cadastro dos Professores:**
   - Os professores podem acessar a página inicial da escola e clicar em **Criar conta**.
   - Por segurança, novos cadastros ficam pendentes de autorização. O administrador acessa o **Painel do Gestor** e clica em **Aprovar** para liberar o acesso do docente às reservas e ao chat interno.

---

## 📄 Licença

Este projeto é disponibilizado sob a licença **MIT** — livre para uso educacional, comercial, estudo e modificações.
