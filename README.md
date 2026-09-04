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
