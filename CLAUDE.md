# HIVE Backend — Contexto para Claude Code

> Este arquivo é lido automaticamente pelo Claude Code a cada sessão nesta pasta.
> Mantenha-o atualizado conforme o projeto avança — é a principal fonte de contexto do agente.

## O que é o HIVE

Sistema para gestão de atividades focado nas fases de **Homologação (UAT)** e **Cutover** de projetos de TI. Uma mesma iniciativa pode ter uma frente em UAT e uma frente em Cutover — mas isso são **dois `Project` totalmente distintos e sem nenhum vínculo no banco** (hierarquia, equipe, atividades e issues de um não têm nada a ver com o outro), que só podem coincidir no nome por convenção de quem cria (ver "Arquitetura de apps" → `projects/`). TCC de Ciência da Computação (EEP/FUMEP).

Este repositório é **só o backend** (Django + DRF). O frontend (React) vive em repositório separado, no mesmo workspace. Integração entre os dois será detalhada depois — por enquanto, trabalhe assumindo que o frontend consome esta API via REST/JSON.

## Estado atual do repositório

Projeto Django iniciado, com `config/settings/` separado em `base.py`/`local.py`/`production.py`. `requirements.txt` já tem `Django`, `djangorestframework`, `django-cors-headers`, `django-environ`, `psycopg2-binary`, `django-storages`, `azure-storage-blob` e `PyJWT[crypto]` (validação de token do Entra ID — decidido usar PyJWT, não MSAL, já que MSAL é biblioteca de aquisição de token do lado do frontend).

Primeiro app de domínio criado: **`apps/accounts`** — model `Usuario` (`AUTH_USER_MODEL`, estende `AbstractUser`, UUID como PK, `email` único, `entra_object_id` UUID nullable/unique, `iniciais`), autenticação DRF via `EntraIDAuthentication` (auto-provisiona o usuário no primeiro acesso a partir dos claims do Access Token), endpoint `GET /api/accounts/me/` como smoke test. A validação do token em si (assinatura via JWKS, issuer, audience, expiração) fica em `integrations/microsoft/entra/validator.py::EntraTokenValidator`. `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES` já aponta pra essa classe, então todo endpoint novo já nasce protegido por padrão (`DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`).

`apps/accounts` propositalmente **não guarda papel nem vínculo com projeto** — isso é `apps/projects::Membership`.

**Branch atual:** `dev`.

`apps/projects` foi iniciado com `Project`, `NoHierarquia`, `Papel` e `Membership`. As rotas reais usam o padrão Django com barra final (`GET /api/projects/`). `Project.mode` é único e fixo na criação, exatamente como o front já implementa, e "UAT + Cutover coexistindo" significa dois `Project` sem vínculo entre si. Projeto não é apagado fisicamente: usa desativação lógica (`ativo=False`) e some da API/lista do frontend. A lista de projetos retorna apenas ativos, ordenados por `criado_em DESC`, e pagina com 10 itens apenas quando houver mais de 10 projetos visíveis. Nomes de projeto podem se repetir somente em modos diferentes; dois projetos ativos com mesmo `nome + modo` são bloqueados. **Não usar `HierarchyLevel`**; a hierarquia oficial do backend é `NoHierarquia` recursivo com `parent_id`. `NoHierarquia` não pode ser apagado depois de criado; pode ser editado por Gestor enquanto não houver regra futura bloqueando vínculos com `Activity`. **`CustomField` foi descartado em 2026-08-26** (decisão do usuário) — campos que antes seriam "customizáveis por projeto" agora são campos fixos direto no model do domínio dono (ver `Activity — campos fixos`, abaixo).

`apps/activities` foi iniciado com `Activity` e `ActivityPredecessor`, rotas aninhadas em projeto e serializer compatível com os campos amigáveis do front (`id` como `ATV-0001`, `module`, `process`, `tester`, `dev`). `Activity.id` é PK numérica sequencial global; `codigo_visivel` é derivado do próprio `id`, não é coluna editável e não reinicia por projeto. `NoHierarquia` não tem códigos visíveis `MOD-*`/`PRC-*`; módulo/processo vêm da relação `Activity.no_id -> NoHierarquia`. Em UAT, `Activity.no_id` aponta para nó nível 2; em Cutover, para nó nível 1. Status inicial: sem predecessores nasce `LIBERADO`; com predecessores nasce `AGUARDANDO`; quando todas as predecessoras forem concluídas, passa para `LIBERADO`. Ao concluir uma predecessora, dependentes que ficarem com todas as predecessoras concluídas são liberadas automaticamente. Status válidos: `AGUARDANDO`, `LIBERADO`, `CONCLUIDO`, `BLOQUEADO` e `CANCELADO`; não existe mais status `EM_EXECUCAO` nem transição automática ao abrir a tela. Predecessores ficam em tabela associativa; na importação CSV/Excel (`POST /api/projects/<id>/activities/import/`), os predecessores usam códigos temporários do próprio arquivo, resolvidos para IDs reais durante a importação. A carga usa a coluna `Sistema`, salva em `Activity.sistema`. Tester e Desenvolvedor são obrigatórios e precisam ter `Membership` no projeto com papel compatível (`TESTER` e `DEV`). Activity não é deletada; é cancelada e não volta. Permissões fechadas: `PATCH`/edição e `cancel` são somente `GESTOR`; `complete` e `block`/reprovar podem ser feitos pelo `GESTOR` ou pelo `TESTER` da própria atividade; `DEV` não bloqueia/reprova Activity, atua na Issue. Regra de edição: não pode trocar `NoHierarquia` depois da criação; não pode editar Activity `CONCLUIDO` ou `CANCELADO`; para todo o resto, o `GESTOR` pode editar. Conclusão de Activity exige evidência; o front envia `approvalFile` via multipart, o backend faz upload para Azure Blob, salva metadados em `evidencia_aprovacao` (`storagePath`, `url`, `urlExpiresAt`) e recusa áudio/vídeo.

## Stack confirmada

- **Linguagem:** Python 3.14.x
- **Framework:** Django + Django REST Framework
- **Banco:** PostgreSQL (Azure Database for PostgreSQL em produção)
- **Autenticação:** Microsoft Entra ID (nome atual do Azure AD) via OAuth2/OpenID Connect — login feito pelo frontend com MSAL, backend valida o Access Token recebido
- **Armazenamento de evidências:** Azure Blob Storage via SDK `azure-storage-blob`; o backend gera links SAS de leitura.
- **CORS:** `django-cors-headers` (frontend em origem separada)
- **Hospedagem:** Azure App Service (um único App Service serve a API e o build do React)

## Estrutura de pastas (real, hoje)

```text
hive-back-end/
├── apps/
│   ├── accounts/            # identidade do usuário + autenticação Entra ID
│   ├── projects/            # Project, NoHierarquia, Papel, Membership
│   └── activities/          # Activity, ActivityPredecessor
├── common/                  # recursos compartilhados por 2+ apps — ainda vazio, nenhum app usa hoje
│   ├── exceptions/          # tratamento de exceções da API
│   ├── pagination/          # paginação reutilizável
│   ├── permissions/         # permissions DRF compartilhadas (papéis: Gestor/Tester/Dev)
│   ├── utils/                # funções auxiliares
│   └── validators/          # validações compartilhadas
├── config/                  # settings (base/local/production), urls, wsgi/asgi
├── integrations/
│   └── microsoft/
│       └── entra/            # validação de token (EntraTokenValidator) — implementado
├── tests/
│   └── integrations/         # testes de integrations/, espelhando o módulo (ver "Convenções de código")
├── manage.py
├── requirements.txt
└── .env.example (.env nunca é commitado — cada dev cria o seu)
```

Regras de responsabilidade das pastas (do README): `common/` é só para código compartilhado por 2+ apps, não é entidade própria. `integrations/` é para serviços externos — a integração com Microsoft Entra ID fica especificamente em `integrations/microsoft/entra/`. `apps/` recebe um app Django por domínio de negócio, nunca por camada técnica.

## Arquitetura de apps

Convenção validada: **um app Django por domínio de negócio**, não por camada técnica. Views finas (validação no serializer, decisão de negócio em `services.py` do app dono). Toda transição de status relevante grava trilha de auditoria via `apps/audit/services.py`, chamada a partir do app de origem — nunca direto da view.

Domínios previstos em `apps/` (✅ = implementado, ⏳ = planejado):

- **✅ `accounts/`** — identidade do usuário (perfil + vínculo Microsoft Entra ID) e autenticação DRF via token OIDC (`EntraIDAuthentication`, auto-provisiona no primeiro acesso). NÃO guarda papel nem vínculo com projeto.
- **✅ `projects/`** — `Project` (`nome`, `modo` — UAT ou Cutover, único e fixo na criação; **duas frentes UAT+Cutover da mesma iniciativa são dois `Project` distintos, sem nenhum vínculo no banco, só podendo coincidir no nome**; `ativo` para desativação lógica, nunca delete físico), `NoHierarquia` recursivo com `parent_id` (cria/edita, mas não deleta), `Papel` lookup (`GESTOR`, `TESTER`, `DEV`) e `Membership` (usuário + projeto + papel: Gestor de Projetos / Tester / Desenvolvedor — um usuário pode ter múltiplos papéis, uma linha de `Membership` por papel). Projetos ativos não podem repetir `nome + modo`. Só `GESTOR` edita projeto, equipe e hierarquia; membros visualizam. **Sem `CustomField`** — descartado em 2026-08-26 (decisão do usuário); nenhum schema de campo customizável por projeto.
- **✅ `activities/`** — `Activity` e `ActivityPredecessor`. Model no mesmo padrão de `projects`, com campos em português. Diferente de `Project`/`Usuario`, `Activity.id` é numérico sequencial global e é usado na URL; `codigo_visivel` é calculado a partir dele (`ATV-0001`, mínimo 4 dígitos, crescendo naturalmente após `ATV-9999`). Não criar contador por projeto para atividades. `Activity.no_id` aponta para `NoHierarquia` folha conforme modo do projeto: UAT exige nível 2; Cutover exige nível 1. `services.py` = validações de hierarquia, membership Tester/Dev, predecessores, transições básicas (`complete`, `block`, `cancel`) e liberação automática de dependentes. Status inicial: sem predecessores `LIBERADO`, com predecessores `AGUARDANDO`. Status válidos: `AGUARDANDO`, `LIBERADO`, `CONCLUIDO`, `BLOQUEADO` e `CANCELADO`. Permissões: Gestor faz tudo; Tester da própria atividade pode concluir e bloquear/reprovar; Dev não bloqueia/reprova Activity. Edição por Gestor não permite trocar `NoHierarquia` nem editar Activity `CONCLUIDO`/`CANCELADO`; demais campos podem ser editados nos outros status. Importação em massa via Excel/CSV implementada em `POST /api/projects/<id>/activities/import/`; cada linha usa `Id lista sequencial (temporario)` para resolver `Predecessores` dentro do arquivo, valida todas as linhas antes de criar qualquer registro e salva a coluna `Sistema` no campo `sistema`. Activity não deleta, só cancela, e cancelada não volta. Conclusão exige evidência; `approvalFile` é enviado para Azure Blob e áudio/vídeo são recusados.
- **✅ `issues/`** — `Issue` vinculada obrigatoriamente a `Activity`. `Issue.id` é numérico sequencial global e `codigo_visivel` é derivado dele (`ISS-0001`). Status: `ABERTA`, `EM_ANALISE`, `SOLUCAO_PROPOSTA`, `CONCLUIDA`, `CANCELADA`. `ABERTA` → `EM_ANALISE` é manual via botão/rota `start-analysis`. Issue impeditiva bloqueia automaticamente apenas a atividade vinculada; issue não impeditiva não altera status da atividade. Se a última issue aberta da atividade bloqueada for resolvida, a Activity volta para `LIBERADO`. Cancelar Activity cancela suas issues abertas. Issues fazem upload real de evidência/anexo de abertura (`openingFile`) e solução (`solutionFile`) para Azure Blob; issue impeditiva exige evidência conforme configuração do projeto; áudio/vídeo são recusados.
- **⏳ `audit/`** — `AuditTrail` genérico (GenericForeignKey, status_anterior/novo, data_hora, usuário). Fonte da Curva S e do tempo médio de resolução.
- **⏳ `dashboards/`** — sem `models.py`, só agrega `Activity`/`Issue`/`AuditTrail`: SPI, Curva S, cards, donuts, barras, ranking.

Nomenclatura de campos/models em **português**, alinhada ao vocabulário já fixado nas regras de negócio (RN01–RN44).

## Regras de negócio essenciais

### Activity — campos fixos
ID numérico sequencial global (PK), código visível calculado a partir do ID (`ATV-0001`, mínimo 4 dígitos, sem reiniciar por projeto), Projeto, Nó de hierarquia, Nome, Status (auto), Tester, Desenvolvedor, Data Início Planejada, Data Conclusão Planejada, Data Início Real (auto), Data Conclusão Real (auto), Predecessores (tabela associativa; na importação CSV/Excel pode vir como código temporário do arquivo), Evidência de aprovação, Observação de aprovação, `numero_retest` (auto, incrementa a cada Bloqueado→Liberado).

`Activity.id` e o número do `codigo_visivel` representam a mesma sequência global. Ex.: `id=2` aparece como `ATV-0002`; `id=10000` aparece como `ATV-10000`. O código visível é estável e nunca muda. `NoHierarquia` não possui código visível de módulo/processo; a atividade fica amarrada a módulo/processo por `Activity.no_id`.

Regra de ligação com a hierarquia:
- Projeto UAT: `Activity.no_id` aponta para `NoHierarquia` nível 2 (filho de nível 1).
- Projeto Cutover: `Activity.no_id` aponta para `NoHierarquia` nível 1.

Tester e Desenvolvedor são obrigatórios e devem possuir `Membership` no projeto com papel compatível (`TESTER` e `DEV`).

Campos fixos opcionais da `Activity`: Área, Sistema, Observações, Resultado Esperado e Transação.

O HIVE não possui sistema de Custom Fields. Não criar `CustomField`, `CustomFieldValue` ou schema dinâmico de campos.

### Status da Activity
```
Aguardando → Liberado → Concluído
                       → Bloqueado (issue impeditiva) → Liberado (reteste)
                       → Cancelado (só Gestor)
```

Atividade sem predecessores nasce `Liberado`. Atividade com predecessores nasce `Aguardando` e só muda para `Liberado` quando todas as predecessoras estiverem `Concluído`. Activity não é apagada fisicamente; é cancelada, permanece no histórico e não volta para outro status.

Permissões de Activity: Gestor pode concluir, bloquear/reprovar, cancelar e editar. Tester da própria atividade pode concluir e bloquear/reprovar. Desenvolvedor não bloqueia/reprova Activity; atua nas Issues. Editar (`PATCH`) e cancelar continuam somente Gestor. Na edição, o Gestor não pode trocar o nó de hierarquia e não pode editar Activity `Concluído` ou `Cancelado`; para todo o resto, a edição é permitida.

### Issue — campos fixos
ID (auto), Título*, Tipo*, Impeditivo*, Desenvolvedor*, Descrição, Anexo/evidência de abertura, Status (auto), Categorização de Impacto, Solução Proposta, Anexo/evidência de solução proposta, Atividade vinculada.

Tipos: Requisito | Performance | Dados | Integração | Interface | Configuração | Outro.

### Status da Issue
```
Aberta → Em análise (manual pelo botão/rota) → Solução proposta → Concluída
Aberta ← Solução proposta (reteste falhou, observação obrigatória)
Cancelada (auto quando atividade é cancelada)
```

### Regras críticas de negócio
- Issue impeditiva → Activity vinculada vai para Bloqueada, sem afetar outras atividades do projeto.
- Issue não impeditiva → Activity permanece no status atual, sem reteste.
- Issue pode ser impeditiva ou não impeditiva em UAT e Cutover; o frontend decide pelo campo `impeditiva`.
- Activity bloqueada por issue volta para Liberado quando não houver mais nenhuma issue aberta vinculada a ela.
- Issues em Solução proposta são concluídas pelo Tester/Gestor via fluxo de resolução/reteste.
- Aprovação simples: evidência obrigatória, observação opcional. Aprovação em lote: múltiplas atividades, uma evidência para o lote.
- Evidências/anexos não podem ser áudio nem vídeo.
- Issue impeditiva exige evidência quando `Project.exigir_evidencia_issue=True`.
- Reteste reprovado: issue volta para Aberta, observação obrigatória.

### SPI (RN41–RN44)
Variante "0/100" do Fixed Formula Method (PMI, 2011): Aguardando=0%, Liberado=0%, Bloqueado=0%, Concluído=100%, Cancelado=excluído do cálculo.

```
SPI = Σ(% das atividades ativas) / (qtd atividades não canceladas
      com Data Conclusão Planejada ≤ hoje × 100)
```

Atividades canceladas ficam fora do numerador e do denominador. Atividades com data planejada futura não entram no denominador. SPI é recalculado dinamicamente a cada acesso ao dashboard — não é persistido; histórico é reconstruído via trilha de auditoria.

### Trilha de auditoria
Tabela genérica: `entidade | status_anterior | status_novo | data_hora | usuario`. Alimentada por `activities` e `issues` a cada transição relevante, sempre via `apps/audit/services.py`. Base para Curva S e tempo médio de resolução.

## Autenticação

```
Microsoft Entra ID → React (MSAL, obtém Access Token) → Django (valida o token) → Endpoint protegido
```

O backend não faz login — só valida o Access Token enviado pelo frontend em cada requisição. Implementação da validação fica em `integrations/microsoft/entra/`.

## Convenções de código

- Views finas: validação no serializer, decisão de negócio em `services.py` do app dono.
- Toda transição de status grava trilha via `apps/audit/services.py`, nunca direto da view.
- Testes em `apps/<app>/tests/`, espelhando o módulo testado; testes gerais/integração em `tests/` na raiz.
- Nomenclatura de campos e models em português.
- `common/` só recebe código compartilhado por 2+ apps — se algo é específico de um domínio, vai no app, não em `common/`.

## Git

Duas branches permanentes: `main` (estável) e `dev` (integração). Toda funcionalidade/correção nasce de uma branch própria a partir de `dev` (`feature/...`, `fix/...`). Entra em `dev` por PR, depois em `main` por PR.

## Frontend

Repositório separado (React), no mesmo workspace, na pasta irmã `../hive-front-end` (mesmo nível de pasta que este repo). O Claude Code pode ler esse repositório diretamente do disco para consultar telas, specs (`docs/superpowers/specs/`) e modelos de dado mockados (`src/types/`, `src/hooks/`, `src/utils/*Indicators.ts`) — **mas nunca deve editar nada lá**; qualquer mudança no frontend é responsabilidade de outra sessão/pessoa. O `CLAUDE.md` daquele repositório tem o inventário completo de telas construídas vs. placeholder.

Estado do frontend (04 telas reais implementadas com dado mockado, sem API real ainda): lista de Projetos, Dashboard do projeto, lista de Atividades, lista de Issues. Login SSO via Entra ID (MSAL) e `ProtectedRoute` já funcionam no front. O backend já valida Access Token em `EntraIDAuthentication`; a integração real depende do front usar o scope da API própria em `VITE_API_SCOPE` e chamar o backend com `VITE_API_BASE_URL`. Auth real configurada em `hive-front-end/src/config/authConfig.ts` (tenant/client ID do Entra ID da FUMEP/EEP, scopes `User.Read` + `User.ReadBasic.All`).

### Divergências front-end vs. regras de negócio (pendências a resolver antes de modelar `projects`/`activities`/`issues`)

O front-end já fixou nomes de campo e comportamentos ao implementar as telas de Atividades/Issues/Dashboard a partir dos mockups HTML — antes de desenhar os models de `apps/activities` e `apps/issues`, os pontos abaixo precisam ser validados/decididos (idealmente com quem mantém o documento de RNs), para o backend não recriar um contrato que já diverge do que a tela consome:

1. **Hierarquia de Atividade fixada como 2 níveis, não configurável.** `Activity` (`hive-front-end/src/types/activity.ts`) tem campos fixos `module`/`process` (2 níveis + Atividade como folha), enquanto o backend usa `NoHierarquia` recursivo com `parent_id`. Decisão atual: manter `NoHierarquia` no backend e adaptar a API futura para o frontend sem recriar `HierarchyLevel`.
2. **`Issue.impact` (Categorização de Impacto) já tem um enum fechado no front, não documentado nas RNs que constam aqui:** `muito_alto | alto | medio | baixo` (`hive-front-end/src/types/issue.ts`, `src/utils/issueIndicators.ts`). O CLAUDE.md atual só cita "Categorização de Impacto" como campo livre — falta confirmar se esse enum de 4 níveis é a regra oficial.
3. **`Issue.area`** — campo de categorização de negócio livre (ex. "Fiscal", "Tesouraria"), independente do `module`/`process` da atividade vinculada. Não existe menção equivalente nas regras de negócio documentadas aqui — confirmar se é um campo fixo de `Issue` (já que `CustomField` foi descartado, não há mais opção de campo customizável por projeto).
4. **Cascata de atividades por Issue** (`Issue.cascadeActivityIds` — outras atividades impactadas pela mesma issue, além de `relatedActivityId`) não está descrita em nenhuma RN registrada aqui. Precisa decidir se isso é regra de negócio real (uma issue pode impactar múltiplas atividades) ou só um elemento visual do mockup sem base funcional ainda — afeta se `Issue`↔`Activity` é 1:N ou N:N.
~~5. **RN16 (transição Aberta→Em análise da Issue) implementada como manual no mockup, não automática.**~~ Resolvido em 2026-09-11: vale o comportamento do frontend. A transição `ABERTA` -> `EM_ANALISE` é manual, via botão/rota `start-analysis`, e não acontece automaticamente ao abrir a tela da issue.
~~6. **Limiares de Aging/Risco de Issue hardcoded no front** (`alerta: 2 dias, risco: 6 dias`, fixos para o modo UAT — `hive-front-end/src/utils/issueIndicators.ts`), sem equivalente nas RN01–RN44 aqui documentadas.~~ Resolvido: ficam como campos fixos de configuração em `Project` (`aging_alerta_dias`, `aging_risco_dias`), não em schema dinâmico.
7. **Papel do usuário (`Membership`) ainda não integrado no front — parcialmente resolvido.** `apps/accounts` já existe (`GET /api/accounts/me/` retorna a identidade validada via Entra ID) e `apps/projects::Membership` já existe para papéis por projeto. A listagem `GET /api/projects/` já retorna o `team` do projeto. Ainda falta uma rota/contrato específico caso o front precise substituir o `useCurrentUser`, que hoje continua retornando `"Gestor de Projetos"` hardcoded.
~~8. `Project.mode` único no front vs. regra de coexistência.~~ **RESOLVIDO em 2026-08-26, confirmado com o usuário.** Não era uma divergência de verdade — era uma leitura errada da regra de negócio por parte do agente. "UAT e Cutover coexistindo" nunca significou um `Project` só com as duas frentes ativas ao mesmo tempo: significa **dois `Project` totalmente distintos e independentes** (hierarquia, equipe, atividades, issues — nada em comum), que só podem coincidir no nome por escolha de quem cria, sem NENHUM vínculo no banco (nem FK, nem campo de agrupamento — decisão explícita do usuário). Ou seja, `Project.mode` único e fixo na criação, exatamente como o front já implementa (`hive-front-end/src/types/project.ts`, `NewProjectModal.tsx`), está correto. Os defaults por modo em `NewProjectModal.tsx::LEVEL_DEFAULTS` (UAT: 2 níveis configuráveis + "Atividade" fixo = 3; Cutover: 1 nível configurável + "Atividade" fixo = 2) devem ser mapeados para `Project.nivel1_nome`/`nivel2_nome` e `NoHierarquia`, não para `HierarchyLevel`.

Esses pontos vieram de uma leitura completa de `hive-front-end/CLAUDE.md`, das 6 specs em `docs/superpowers/specs/` e dos arquivos de tipo/indicadores citados acima (sessão de 2026-08-21, item 8 adicionado e resolvido em 2026-08-26). Ao resolver cada um, atualizar esta seção e, se a decisão mudar o contrato já consumido pelo front, sinalizar para quem mantém `hive-front-end`.
