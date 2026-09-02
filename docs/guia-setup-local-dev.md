# Guia De Setup Local Para Devs - HIVE Backend

## 1. Objetivo

Este guia explica como um desenvolvedor deve preparar o ambiente local para rodar o backend do HIVE.

O backend usa:

1. Python 3.14.x.
2. Django + Django REST Framework.
3. PostgreSQL Server local.
4. Microsoft Entra ID para validação de token.

## 2. Pré-requisitos

Instalar:

1. Git.
2. Python 3.14.x.
3. PostgreSQL Server para Windows.
4. pgAdmin 4.
5. Visual Studio Code ou editor equivalente.

Observação:

1. O pgAdmin é apenas a interface visual.
2. É necessário instalar também o PostgreSQL Server.
3. Se `Get-Service *postgres*` não retornar nada no PowerShell, o PostgreSQL Server provavelmente não está instalado como serviço.

## 3. Instalar PostgreSQL Server

1. Acesse:

```text
https://www.postgresql.org/download/windows/
```

2. Baixe o instalador para Windows.
3. Execute o instalador.
4. Mantenha os componentes básicos:
   - PostgreSQL Server;
   - pgAdmin 4;
   - Command Line Tools.
5. Quando pedir senha do usuário `postgres`, defina uma senha e anote.
6. Mantenha a porta padrão:

```text
5432
```

7. No final da instalação, o Stack Builder pode ser ignorado.

Não precisa instalar Stack Builder para rodar o HIVE localmente.

## 4. Conferir Se PostgreSQL Está Rodando

Abra o PowerShell e rode:

```powershell
Get-Service *postgres*
```

Deve aparecer algo como:

```text
postgresql-x64-17
```

Se o serviço aparecer, mas estiver parado:

```powershell
Start-Service postgresql-x64-17
```

O nome pode mudar conforme a versão instalada.

## 5. Registrar Servidor No pgAdmin

Abra o pgAdmin.

1. Clique com botão direito em `Servers`.
2. Selecione `Register > Server...`.
3. Na aba `General`:

```text
Name: Local PostgreSQL
```

4. Na aba `Connection`:

```text
Host name/address: localhost
Port: 5432
Maintenance database: postgres
Username: postgres
Password: senha definida na instalação
```

5. Clique em `Save`.

## 6. Criar Usuário E Banco Do HIVE

No pgAdmin, abra o Query Tool conectado como usuário `postgres`.

Rode primeiro só o usuário:

```sql
CREATE USER hive_user WITH PASSWORD 'SUA_SENHA';
```

Depois rode só o banco:

```sql
CREATE DATABASE hive_db
OWNER hive_user;
```

Importante:

1. `CREATE DATABASE` não pode rodar dentro de transaction block.
2. Por isso, rode o `CREATE USER` separado do `CREATE DATABASE`.
3. Troque `SUA_SENHA` por uma senha local sua.

Se o usuário já existir, rode apenas:

```sql
CREATE DATABASE hive_db
OWNER hive_user;
```

## 7. Permitir Que Testes Criem Banco Temporário

O Django cria um banco temporário ao rodar:

```powershell
python manage.py test
```

Por isso, no ambiente local, dê permissão para `hive_user` criar banco:

```sql
ALTER USER hive_user CREATEDB;
```

Isso é recomendado apenas para desenvolvimento local.

Em produção, o usuário da aplicação não precisa desse privilégio.

## 8. Clonar O Repositório

No PowerShell:

```powershell
cd C:\Users\marti\OneDrive\Desktop\Faculdade\HIVE
git clone https://github.com/LeoMartt/hive-back-end.git hive-back
cd hive-back
```

Se o repositório já existir:

```powershell
cd C:\Users\marti\OneDrive\Desktop\Faculdade\HIVE\hive-back
```

## 9. Criar Ambiente Virtual

Dentro da pasta do backend:

```powershell
py -m venv .venv
```

Ative:

```powershell
.\.venv\Scripts\Activate.ps1
```

O terminal deve ficar parecido com:

```text
(.venv) PS C:\Users\marti\OneDrive\Desktop\Faculdade\HIVE\hive-back>
```

## 10. Instalar Dependências

Com a `.venv` ativa:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 11. Criar Arquivo `.env`

Na raiz do backend, crie:

```text
.env
```

Exemplo:

```env
DJANGO_SECRET_KEY=dev-hive-local-2026-nao-usar-em-producao-uma-chave-bem-grande-123456789
DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgresql://hive_user:SUA_SENHA@localhost:5432/hive_db

CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

AZURE_TENANT_ID=4c330174-b463-400c-a84b-ee3c6b705c62
AZURE_CLIENT_ID=40796f28-4c73-4ba7-a267-68118451a05c

AZURE_ACCOUNT_NAME=
AZURE_ACCOUNT_KEY=
AZURE_CONTAINER=
```

Troque:

```text
SUA_SENHA
```

pela senha criada para `hive_user`.

Importante:

1. O `.env` é local.
2. Não commitar `.env`.
3. Para dev local, `DJANGO_SECRET_KEY` pode ser uma string grande qualquer.
4. Para produção, a chave precisa ser segura e gerenciada como segredo.

## 12. Rodar Checks E Migrations

Com a `.venv` ativa:

```powershell
python manage.py check
python manage.py migrate
python manage.py test
```

Resultado esperado:

```text
System check identified no issues
Ran tests - OK
```

## 13. Criar Superusuário Local

Para acessar o Django Admin:

```powershell
python manage.py createsuperuser
```

Esse usuário é local e serve para administração/desenvolvimento.

Usuários finais entram pelo Microsoft Entra ID.

## 14. Rodar O Servidor

```powershell
python manage.py runserver
```

Servidor local:

```text
http://127.0.0.1:8000/
```

## 15. Testes Manuais Básicos

### 15.1. Django Admin

Abrir no navegador:

```text
http://127.0.0.1:8000/admin/login/
```

Resultado esperado:

1. Página de login abre.
2. Superusuário local consegue entrar.

### 15.2. Endpoint `accounts`

Abrir sem token:

```text
http://127.0.0.1:8000/api/accounts/me/
```

Resultado esperado:

```text
401 Unauthorized
```

Motivo:

1. O endpoint é protegido.
2. Sem Access Token válido do Entra ID, o backend deve negar acesso.

### 15.3. Endpoint `projects`

Abrir sem token:

```text
http://127.0.0.1:8000/api/projects/
```

Resultado esperado:

```text
401 Unauthorized
```

Motivo:

1. A API de projetos também é protegida.
2. Para testar com usuário autenticado real, o frontend precisa enviar Access Token da API própria.

## 16. Criar Dados De Teste Pelo Admin

Depois de entrar no Django Admin, é possível criar:

1. `Project`.
2. `NoHierarquia`.
3. `Membership`.

Os papéis já devem existir por migration:

1. `GESTOR`.
2. `TESTER`.
3. `DEV`.

Se não aparecerem, confira:

```powershell
python manage.py showmigrations projects
```

Esperado:

```text
projects
 [X] 0001_initial
 [X] 0002_seed_papeis
```

## 17. Configurar O Frontend Para Usar A API Real

No frontend, existe camada API preparada para projetos.

Arquivo esperado:

```text
C:\Users\marti\OneDrive\Desktop\Faculdade\HIVE\hive-front\.env
```

Para usar backend real, o frontend precisa sair dos mocks.

Exemplo:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api
VITE_USE_MOCKS=false
VITE_API_SCOPE=api://SEU_APP_ID_URI/SCOPE_DA_API
```

Observações:

1. `VITE_API_BASE_URL` aponta para o backend.
2. `VITE_USE_MOCKS=false` manda o front chamar a API.
3. `VITE_API_SCOPE` precisa ser o scope exposto pela App Registration da API do HIVE no Microsoft Entra ID.
4. Token de Microsoft Graph, como `User.Read`, não é automaticamente válido para a API Django.

## 18. Comandos Úteis

Ver branch atual:

```powershell
git branch --show-current
```

Ver alterações:

```powershell
git status --short
```

Ver migrations:

```powershell
python manage.py showmigrations
```

Criar migrations:

```powershell
python manage.py makemigrations
```

Ver se faltam migrations:

```powershell
python manage.py makemigrations --check --dry-run
```

Aplicar migrations:

```powershell
python manage.py migrate
```

Rodar testes:

```powershell
python manage.py test
```

## 19. Problemas Comuns

### 19.1. `ModuleNotFoundError: No module named 'django'`

Causa provável:

1. `.venv` não está ativa.
2. Dependências não foram instaladas.

Solução:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 19.2. `Set the DJANGO_SECRET_KEY environment variable`

Causa provável:

1. `.env` não existe.
2. `DJANGO_SECRET_KEY` está vazio.

Solução:

1. Criar `.env`.
2. Preencher `DJANGO_SECRET_KEY`.

### 19.3. `connection timeout expired` no pgAdmin

Causa provável:

1. PostgreSQL Server não está instalado.
2. Serviço do PostgreSQL está parado.
3. Porta está diferente de `5432`.

Solução:

```powershell
Get-Service *postgres*
```

Se existir e estiver parado:

```powershell
Start-Service postgresql-x64-17
```

### 19.4. `CREATE DATABASE cannot run inside a transaction block`

Causa:

1. `CREATE DATABASE` foi executado junto com outro comando dentro de uma transação.

Solução:

1. Rode `CREATE USER` sozinho.
2. Depois rode `CREATE DATABASE` sozinho.

### 19.5. `permissão negada ao criar banco de dados` ao rodar testes

Causa:

1. `hive_user` não tem permissão para criar banco temporário de teste.

Solução no pgAdmin, conectado como `postgres`:

```sql
ALTER USER hive_user CREATEDB;
```

## 20. Ordem Recomendada De Trabalho

1. Instalar PostgreSQL Server.
2. Criar `hive_user`.
3. Criar `hive_db`.
4. Dar `CREATEDB` para `hive_user` no ambiente local.
5. Criar `.env`.
6. Criar/ativar `.venv`.
7. Instalar dependências.
8. Rodar `python manage.py check`.
9. Rodar `python manage.py migrate`.
10. Rodar `python manage.py test`.
11. Criar superusuário.
12. Rodar `python manage.py runserver`.
13. Testar `/admin/login/`, `/api/accounts/me/` e `/api/projects/`.
