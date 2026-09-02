# Relatório de Trabalho - 2026-09-02

## 1. Contexto

Hoje o trabalho foi feito na branch:

```text
leo-first-routes
```

O foco foi consolidar a base inicial do backend do HIVE em dois blocos:

1. Ajuste definitivo do app `accounts`.
2. Implementação inicial do app `projects`.

Também houve configuração e validação do PostgreSQL local, porque o banco definitivo do projeto é PostgreSQL e não SQLite.

## 2. Decisões Usadas Como Base

1. O banco será implementado por blocos, não completo de uma vez.
2. `Usuario` deve usar UUID como chave primária.
3. `Usuario` mantém `AbstractUser`.
4. Campos herdados do `AbstractUser` devem ser aproveitados quando fizer sentido.
5. `email` deve ser único.
6. `entra_object_id` deve ser `UUIDField(unique=True, null=True, blank=True)`.
7. `iniciais` deve existir e ser preenchido automaticamente no auto-provisionamento.
8. O nome do usuário vem do login Microsoft e fica no campo herdado `first_name`.
9. A hierarquia de projeto usa `NoHierarquia`/`no_hierarquia`, não `HierarchyLevel`.
10. Não existe sistema de `CustomField`.
11. `permissao_papel` não entra agora.
12. Auditoria do MVP registra somente transições de status.

## 3. Alterações Em `accounts`

### 3.1. `apps/accounts/models.py`

Foi ajustado o model `Usuario`.

Criado/alterado:

1. `id` passou a ser UUID como PK:

```python
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```

Motivo:

1. A modelagem oficial define UUID como PK.
2. É melhor para API e evita expor IDs sequenciais.
3. Essa decisão precisa ser feita antes da primeira migration definitiva.

2. `email` passou a ser único:

```python
email = models.EmailField("e-mail", unique=True)
```

Motivo:

1. A modelagem oficial define e-mail único.
2. Usuários finais entrarão com conta Microsoft.
3. Contas locais ficam reservadas para dev/admin.

3. `entra_object_id` virou UUID:

```python
entra_object_id = models.UUIDField(
    "ID do objeto no Entra ID",
    unique=True,
    null=True,
    blank=True,
)
```

Motivo:

1. O claim `oid` do Microsoft Entra ID é UUID.
2. O banco passa a validar o formato.
3. Fica mais alinhado com a modelagem oficial.

4. Adicionado `iniciais`:

```python
iniciais = models.CharField("iniciais", max_length=4, blank=True, default="")
```

Motivo:

1. A modelagem prevê código de avatar.
2. O frontend já usa iniciais em avatares.
3. O valor pode ser preenchido automaticamente pelo backend.

### 3.2. `apps/accounts/authentication.py`

Foi ajustado o auto-provisionamento de usuário via Microsoft Entra ID.

Principais mudanças:

1. Validação de token vazio.
2. Conversão/validação do `oid` para UUID.
3. Exigência de e-mail no token.
4. Normalização do e-mail.
5. Tratamento de conflito quando já existe outro usuário com o mesmo e-mail.
6. Preenchimento de `first_name` com o claim `name`.
7. Geração automática de `iniciais`.
8. Usuário criado via Entra fica com senha local inutilizável.

Motivo:

1. Evitar dados inválidos no banco.
2. Evitar erro bruto de integridade quando o e-mail já existe.
3. Separar login Microsoft de login local do Django Admin.
4. Manter o cadastro local apenas como identidade interna para FKs do sistema.

## 4. Explicação: Usuário Microsoft vs Usuário Local

O HIVE terá dois cenários:

1. Usuário final:
   - entra pelo Microsoft Entra ID;
   - recebe token no frontend;
   - backend valida o token;
   - backend cria/atualiza um registro local em `Usuario`;
   - esse usuário não precisa ter senha Django.

2. Usuário local de dev/admin:
   - criado com `createsuperuser`;
   - usado para acessar `/admin/`;
   - tem senha local;
   - serve para administração em desenvolvimento.

O registro local sempre existe porque o banco precisa apontar FKs para usuário em projetos, atividades, issues, anexos e auditoria.

## 5. Alterações Em `accounts` Para API/Admin/Testes

### 5.1. `apps/accounts/serializers.py`

O endpoint `GET /api/accounts/me/` agora retorna também `iniciais`.

Campos retornados:

```text
id
nome
email
iniciais
entra_object_id
```

### 5.2. `apps/accounts/admin.py`

O Django Admin foi ajustado para mostrar e editar os campos do HIVE:

1. `iniciais`.
2. `entra_object_id`.

Também foi ajustada a listagem para mostrar dados úteis do usuário.

### 5.3. `apps/accounts/tests/test_authentication.py`

Foram adicionados testes para:

1. UUID no `id`.
2. UUID no `entra_object_id`.
3. retorno de `nome`.
4. retorno de `iniciais`.
5. senha inutilizável para usuário criado via Entra.
6. `oid` inválido retornando 401.
7. token sem e-mail retornando 401.
8. conflito de e-mail retornando 401 controlado.
9. geração de iniciais pelo e-mail quando o nome não vem no token.

## 6. Migration De `accounts`

Arquivo alterado:

```text
apps/accounts/migrations/0001_initial.py
```

A migration inicial foi regenerada para já nascer correta, porque ainda era a primeira migration oficial do `AUTH_USER_MODEL`.

Motivo:

1. Evitar uma base inicial errada com `BigAutoField`.
2. Evitar uma segunda migration corrigindo algo que ainda não tinha sido consolidado.
3. `AUTH_USER_MODEL` é caro de mudar depois.

## 7. Implementação De `projects`

Foi criado o app:

```text
apps/projects/
```

Arquivos criados:

```text
apps/projects/__init__.py
apps/projects/apps.py
apps/projects/models.py
apps/projects/serializers.py
apps/projects/views.py
apps/projects/urls.py
apps/projects/admin.py
apps/projects/migrations/__init__.py
apps/projects/migrations/0001_initial.py
apps/projects/migrations/0002_seed_papeis.py
apps/projects/tests/__init__.py
apps/projects/tests/test_models.py
apps/projects/tests/test_views.py
```

## 8. Models Criados Em `projects`

### 8.1. `Project`

Representa um projeto do HIVE.

Campos principais:

1. `id`: UUID.
2. `nome`.
3. `descricao`.
4. `modo`: `UAT` ou `CUTOVER`.
5. `nivel1_nome`.
6. `nivel2_nome`.
7. `aging_alerta_dias`.
8. `aging_risco_dias`.
9. `spi_saudavel`.
10. `spi_critico`.
11. `anexo_max_mb`.
12. `exigir_evidencia_atividade`.
13. `exigir_evidencia_issue`.
14. `proximo_codigo_atividade`.
15. `proximo_codigo_issue`.
16. `criado_por`.
17. `criado_em`.
18. `atualizado_em`.

Motivo:

1. Seguir a modelagem oficial.
2. Guardar configurações fixas do projeto no próprio projeto.
3. Evitar `CustomField`.
4. Preparar contadores por projeto para Activity e Issue.

### 8.2. `NoHierarquia`

Representa a hierarquia recursiva do projeto.

Campos principais:

1. `id`: UUID.
2. `projeto`.
3. `parent`.
4. `nivel`.
5. `nome`.
6. `ordem`.
7. `criado_em`.

Motivo:

1. Seguir a decisão de usar `no_hierarquia`.
2. Evitar `HierarchyLevel`.
3. Permitir estrutura recursiva com `parent_id`.
4. Deixar o backend mais flexível para o futuro.

### 8.3. `Papel`

Lookup de papéis de projeto.

Papéis criados:

1. `GESTOR` - Gestor de Projetos.
2. `TESTER` - Tester.
3. `DEV` - Desenvolvedor.

Motivo:

1. Papéis pertencem ao domínio de projetos.
2. Usuário não tem papel global.
3. Cada papel é atribuído por projeto.

### 8.4. `Membership`

Associação entre usuário, projeto e papel.

Campos principais:

1. `id`: UUID.
2. `usuario`.
3. `projeto`.
4. `papel`.
5. `convidado_por`.
6. `criado_em`.

Constraint:

```text
unique(usuario, projeto, papel)
```

Motivo:

1. Um usuário pode ter vários papéis no mesmo projeto.
2. O mesmo papel não deve ser duplicado para o mesmo usuário no mesmo projeto.
3. A autorização futura será baseada em membership.

## 9. Migrations De `projects`

### 9.1. `0001_initial.py`

Cria:

1. `Papel`.
2. `Project`.
3. `NoHierarquia`.
4. `Membership`.
5. Constraints de modo, níveis, contadores e unicidade.

### 9.2. `0002_seed_papeis.py`

Popula o lookup inicial de papéis:

1. `GESTOR`.
2. `TESTER`.
3. `DEV`.

Motivo:

1. Evitar cadastro manual desses valores fixos.
2. Garantir que qualquer ambiente local tenha os mesmos papéis.

## 10. Rotas Criadas

Foi criada a primeira rota real de projetos:

```text
GET /api/projects/
```

Também foi adicionada compatibilidade sem barra final:

```text
GET /api/projects
```

Motivo:

1. O frontend atual chama `httpClient.get("/projects")`.
2. Com `VITE_API_BASE_URL=http://127.0.0.1:8000/api`, isso vira `/api/projects`.
3. A rota com barra final também segue o padrão Django.

## 11. Resposta Da Listagem De Projetos

A resposta foi feita para bater com o schema atual do frontend.

Formato:

```json
[
  {
    "id": "uuid",
    "name": "Nome do projeto",
    "mode": "uat",
    "activityCount": 0,
    "completedCount": 0,
    "hierarchyLevels": ["Área", "Cenário"],
    "progressPercent": 0,
    "spi": null,
    "team": [],
    "updatedAt": "2026-09-02T00:00:00-03:00"
  }
]
```

Campos de atividade ainda retornam zero/null porque `apps/activities` ainda não existe.

## 12. Regras Da Listagem

1. Usuário comum vê apenas projetos onde tem `Membership`.
2. Staff/superuser vê todos os projetos.
3. Endpoint continua protegido pela autenticação padrão do DRF.

Motivo:

1. Usuário autenticado não significa acesso a todos os projetos.
2. A autorização completa ainda virá depois.
3. Essa regra já evita vazamento básico de projetos entre usuários.

## 13. Testes Criados Para `projects`

### 13.1. Testes de model

Arquivo:

```text
apps/projects/tests/test_models.py
```

Cobre:

1. Defaults do `Project`.
2. UAT exigindo segundo nível.
3. Cutover não aceitando segundo nível.
4. `NoHierarquia` nível 1 sem parent.
5. `NoHierarquia` nível 2 exigindo parent.
6. Cutover não aceitando nó de nível 2.
7. Usuário com múltiplos papéis no mesmo projeto.

### 13.2. Testes de view

Arquivo:

```text
apps/projects/tests/test_views.py
```

Cobre:

1. Sem autenticação retorna 401.
2. Usuário comum lista apenas seus projetos.
3. Staff lista todos os projetos.
4. `/api/projects` sem barra final funciona para o frontend.
5. Payload retornado bate com o shape esperado pelo front.

## 14. Arquivos De Configuração Alterados

### 14.1. `config/settings/base.py`

Adicionado:

```python
"apps.projects",
```

Motivo:

1. Registrar o app Django.
2. Permitir migrations, admin e models.

### 14.2. `config/urls.py`

Adicionadas rotas:

```python
path("api/projects", ProjectListView.as_view(), name="projects-list-no-slash"),
path("api/projects/", include("apps.projects.urls")),
```

Motivo:

1. Expor a API de projetos.
2. Aceitar o caminho sem barra final usado pelo frontend.

## 15. Documentação Atualizada

Arquivos atualizados:

```text
CLAUDE.md
README.md
```

Motivo:

1. Registrar que `projects` já existe.
2. Remover orientação antiga de `HierarchyLevel`.
3. Reforçar que o backend usa `NoHierarquia`.
4. Remover texto antigo dizendo que validação de token ainda seria feita depois.
5. Documentar rotas iniciais de projetos.

## 16. PostgreSQL Local

Foi configurado PostgreSQL Server local.

Passos feitos:

1. Instalação do PostgreSQL Server.
2. Stack Builder não foi necessário.
3. Criação do usuário `hive_user`.
4. Criação do banco `hive_db`.
5. Concessão de `CREATEDB` para `hive_user`, necessária para `python manage.py test`.

Comando usado para permitir testes:

```sql
ALTER USER hive_user CREATEDB;
```

Motivo:

1. O Django cria banco temporário de teste.
2. Sem `CREATEDB`, o teste falha com permissão negada.
3. Isso é aceitável no ambiente local.
4. Em produção, esse privilégio não precisa existir.

## 17. Validações Executadas

Foram executados:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py migrate
python manage.py showmigrations projects
```

Resultados finais:

```text
System check identified no issues
No changes detected
Ran 23 tests - OK
projects.0001_initial - applied
projects.0002_seed_papeis - applied
```

## 18. O Que Ainda Não Foi Feito

1. Não foi criado `apps/activities`.
2. Não foi criado `apps/issues`.
3. Não foi criado `apps/audit`.
4. Não foi criado `apps/attachments`.
5. Não foi implementada criação real de projetos via API.
6. Não foi implementada edição de membros via API.
7. Não foi conectado o frontend ao backend em modo real.
8. Não foi feito commit.

## 19. Próximos Passos Recomendados

1. Revisar as migrations de `accounts` e `projects`.
2. Testar `GET /api/projects/` com dados reais criados pelo Django Admin.
3. Criar pelo Admin:
   - um `Project`;
   - alguns `NoHierarquia`;
   - `Membership` ligando usuário ao projeto.
4. Depois decidir o próximo bloco:
   - criação de projeto pela API;
   - integração do front com `GET /api/projects/`;
   - ou início de `apps/activities`.

## 20. Observação Sobre Git

As alterações ainda estão pendentes no working tree.

Arquivos modificados ou criados incluem:

```text
CLAUDE.md
README.md
apps/accounts/*
apps/projects/*
config/settings/base.py
config/urls.py
```

Nenhum commit foi feito automaticamente.
