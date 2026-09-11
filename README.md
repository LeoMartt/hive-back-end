# HIVE Backend

Backend do projeto HIVE desenvolvido com Django e Django REST Framework.

O backend será responsável pela API da aplicação, regras de negócio, acesso ao banco de dados, permissões e validação da autenticação utilizando Microsoft Entra ID.

O frontend da aplicação é desenvolvido separadamente em React.

## Tecnologias

* Python 
* Django
* Django REST Framework
* django-cors-headers
* Microsoft Entra ID
* Azure

## Pré-requisitos

Antes de iniciar o projeto, é necessário possuir:

* Python 3.14.x
* Git
* Visual Studio Code

Para verificar a instalação do Python:

```powershell
python --version
```

ou:

```powershell
py --version
```

## Clonar o projeto

Clone o repositório:

```powershell
git clone https://github.com/LeoMartt/hive-back-end.git
```

Entre na pasta:

```powershell
cd hive-back-end
```

Abra no Visual Studio Code:

```powershell
code .
```

## Criar o ambiente virtual

No PowerShell integrado do VS Code:

```powershell
py -m venv .venv
```

Ative o ambiente virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

Quando estiver ativo, o terminal deverá apresentar algo semelhante a:

```text
(.venv) PS C:\...\hive-back-end>
```

## Instalar as dependências

Com o ambiente virtual ativado:

```powershell
pip install -r requirements.txt
```

Esse comando instalará todas as bibliotecas necessárias para executar o backend.

## Variáveis de ambiente

O arquivo `.env` não deve ser enviado para o GitHub.

Quando o projeto possuir variáveis de ambiente, utilize o arquivo `.env.example` como referência.

Exemplo:

```env
DJANGO_SECRET_KEY=
DEBUG=
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
```

Cada desenvolvedor deverá criar seu próprio arquivo `.env`.

## Executar o projeto

Com o ambiente virtual ativado:

```powershell
python manage.py runserver
```

O backend ficará disponível normalmente em:

```text
http://127.0.0.1:8000/
```

## Estrutura do projeto

```text
hive-back-end/
├── apps/
│   ├── accounts/
│   └── projects/
├── common/
│   ├── exceptions/
│   ├── pagination/
│   ├── permissions/
│   ├── utils/
│   └── validators/
├── config/
├── integrations/
│   └── microsoft/
│       └── entra/
├── tests/
├── .gitignore
├── README.md
├── requirements.txt
└── manage.py
```

## Responsabilidade das pastas

### `apps/`

Contém os módulos principais do sistema.

Cada domínio da aplicação deverá possuir seu próprio app Django.

Exemplos futuros:

```text
apps/
├── accounts/
├── projects/
└── activities/
```

### `common/`

Contém recursos reutilizados por diferentes apps.

* `exceptions/`: tratamento de exceções.
* `pagination/`: paginações reutilizáveis.
* `permissions/`: permissões compartilhadas.
* `utils/`: funções auxiliares.
* `validators/`: validações compartilhadas.

### `config/`

Contém as configurações principais do Django, como:

* settings;
* URLs principais;
* configuração do banco;
* Django REST Framework;
* CORS;
* ASGI;
* WSGI.

### `integrations/`

Contém integrações com serviços externos.

A integração relacionada ao Microsoft Entra ID deverá ficar em:

```text
integrations/microsoft/entra/
```

### `tests/`

Contém testes gerais e testes de integração do projeto.

## Autenticação

O frontend realiza o login com Microsoft Entra ID utilizando MSAL.

O backend valida os Access Tokens enviados pelo frontend antes de permitir acesso aos endpoints protegidos.

A validação é feita por `EntraIDAuthentication`, usando `EntraTokenValidator` para verificar assinatura RS256 via JWKS, issuer, audience e expiração.

Endpoint de validação da identidade autenticada:

```text
GET /api/accounts/me/
```

O fluxo esperado é:

```text
Microsoft Entra ID
        ↓
      React
        ↓
Access Token
        ↓
      Django
        ↓
Validação do Token
        ↓
Endpoint protegido
```

## Projects

O app `apps/projects` contém o primeiro bloco do domínio de projetos:

* `Project`;
* `NoHierarquia`;
* `Papel`;
* `Membership`.

Rotas iniciais:

```text
GET /api/projects/
POST /api/projects/
GET /api/projects/<project_id>/
PATCH /api/projects/<project_id>/
DELETE /api/projects/<project_id>/
GET /api/projects/roles/
GET /api/projects/<project_id>/hierarchy/
POST /api/projects/<project_id>/hierarchy/
PATCH /api/projects/<project_id>/hierarchy/<node_id>/
GET /api/projects/<project_id>/memberships/
POST /api/projects/<project_id>/memberships/
DELETE /api/projects/<project_id>/memberships/<membership_id>/
```

A resposta da listagem segue o contrato atual do frontend para `projectsApi.list()` quando houver até 10 projetos visíveis. Acima de 10 projetos, a resposta passa a usar paginação com `count`, `next`, `previous` e `results`.

Regras consolidadas do bloco de projetos:

* projetos não são apagados fisicamente; `DELETE /api/projects/<project_id>/` apenas desativa o projeto;
* projetos desativados não aparecem na API de listagem nem nos detalhes;
* a listagem retorna apenas projetos ativos e ordena por data de criação mais recente;
* dois projetos ativos não podem ter o mesmo `nome + modo`;
* `UAT` e `Cutover` com o mesmo nome são permitidos porque são projetos distintos;
* somente `GESTOR` pode editar dados do projeto, equipe/memberships e nós de hierarquia;
* `NoHierarquia` não pode ser removido depois de criado; a API permite criar e editar, mas não deletar;
* convite de usuários continua recebendo os dados selecionados pelo frontend no Microsoft Graph;
* dados temporários de desenvolvimento podem ser criados com `python manage.py seed_dev_projects` e ficam marcados com `[DEV SEED]`.

## Activities

O app `apps/activities` contém o primeiro bloco do domínio de atividades:

* `Activity`;
* `ActivityPredecessor`.

Rotas iniciais:

```text
GET /api/projects/<project_id>/activities/
POST /api/projects/<project_id>/activities/
GET /api/projects/<project_id>/activities/<activity_id>/
PATCH /api/projects/<project_id>/activities/<activity_id>/
POST /api/projects/<project_id>/activities/<activity_id>/complete/
POST /api/projects/<project_id>/activities/<activity_id>/block/
POST /api/projects/<project_id>/activities/<activity_id>/cancel/
```

Regras consolidadas do bloco de atividades:

* `Activity` segue o mesmo padrão de organização do app `projects`, com model, serializers, views, services e tests dentro do app;
* os campos do model serão em português;
* `Activity.id` será numérico sequencial global e usado como PK;
* o código visível será calculado a partir do próprio `id`, no formato `ATV-0001`;
* o código visível terá no mínimo 4 dígitos e crescerá naturalmente depois de `ATV-9999`, por exemplo `ATV-10000`;
* o contador de atividades não reinicia por projeto;
* `NoHierarquia` não terá códigos visíveis como `MOD-*` ou `PRC-*`;
* a ligação da atividade com módulo/processo será feita por `Activity.no_id`;
* em projetos UAT, a atividade deve apontar para um `NoHierarquia` de nível 2;
* em projetos Cutover, a atividade deve apontar para um `NoHierarquia` de nível 1;
* atividade sem predecessores nasce com status `LIBERADO`;
* atividade com predecessores nasce com status `AGUARDANDO`;
* quando todas as predecessoras forem concluídas, a atividade passa para `LIBERADO`;
* a conclusão de uma atividade libera automaticamente dependentes que estavam `AGUARDANDO` e ficaram com todas as predecessoras `CONCLUIDO`;
* predecessores serão persistidos em tabela associativa, não como texto separado por `;`;
* na importação CSV/Excel, os predecessores podem usar códigos temporários do próprio arquivo, resolvidos para IDs reais durante a importação;
* `tester` e `desenvolvedor` são obrigatórios e devem ter `Membership` no projeto com papel compatível;
* atividade não será deletada fisicamente; será apenas cancelada;
* atividade cancelada não volta para outro status;
* permissões de atividades:
  * `PATCH`/edição e `cancel` são somente `GESTOR`;
  * `complete` e `block`/reprovar podem ser feitos pelo `GESTOR` ou pelo `TESTER` da própria atividade;
  * `DEV` não bloqueia/reprova atividade; `DEV` atua na issue;
* regra de edição:
  * não é permitido trocar o `NoHierarquia`/nó da atividade depois da criação;
  * não é permitido editar atividade `CONCLUIDO` ou `CANCELADO`;
  * nos demais status, o `GESTOR` pode editar os outros campos da atividade;
* os status válidos de atividade são `AGUARDANDO`, `LIBERADO`, `CONCLUIDO`, `BLOQUEADO` e `CANCELADO`;
* upload/evidência será tratado em bloco posterior.

## Git

O projeto utiliza duas branches permanentes:

```text
main → versão estável
dev  → desenvolvimento e integração
```

Toda funcionalidade ou correção deve ser desenvolvida em uma branch própria criada a partir da `dev`.

Exemplo:

```text
feature/login
feature/projects
fix/project-validation
```

As alterações devem entrar na `dev` por Pull Request e posteriormente na `main` por Pull Request.
