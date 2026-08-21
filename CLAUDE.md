# HIVE Backend — Contexto para Claude Code

> Este arquivo é lido automaticamente pelo Claude Code a cada sessão nesta pasta.
> Mantenha-o atualizado conforme o projeto avança — é a principal fonte de contexto do agente.

## O que é o HIVE

Sistema para gestão de atividades focado nas fases de **Homologação (UAT)** e **Cutover** de projetos de TI. Um projeto pode ter UAT, Cutover, ou os dois modos coexistindo, de forma independente. TCC de Ciência da Computação (EEP/FUMEP).

Este repositório é **só o backend** (Django + DRF). O frontend (React) vive em repositório separado, no mesmo workspace. Integração entre os dois será detalhada depois — por enquanto, trabalhe assumindo que o frontend consome esta API via REST/JSON.

## Estado atual do repositório

**Esqueleto puro.** Ainda não existe projeto Django iniciado: não há `manage.py`, nem `config/settings`, nem nenhum app criado dentro de `apps/`. As pastas existem vazias (`.gitkeep`) representando a convenção de onde cada coisa vai morar. `requirements.txt` só tem `Django`, `djangorestframework`, `django-cors-headers` — ainda faltam `psycopg2`/`psycopg`, `django-storages`, biblioteca de validação de token do Entra ID (MSAL/PyJWT), entre outras que serão necessárias.

**Primeira tarefa real do backend:** rodar `django-admin startproject config .` (ou equivalente), estruturar `config/settings/` (base/local/production) e criar o primeiro app.

## Stack confirmada

- **Linguagem:** Python 3.14.x
- **Framework:** Django + Django REST Framework
- **Banco:** PostgreSQL (Azure Database for PostgreSQL em produção)
- **Autenticação:** Microsoft Entra ID (nome atual do Azure AD) via OAuth2/OpenID Connect — login feito pelo frontend com MSAL, backend valida o Access Token recebido
- **Armazenamento de evidências:** Azure Blob Storage via `django-storages`
- **CORS:** `django-cors-headers` (frontend em origem separada)
- **Hospedagem:** Azure App Service (um único App Service serve a API e o build do React)

## Estrutura de pastas (real, hoje)

```text
hive-back-end/
├── apps/                    # vazio — apps de domínio entram aqui, um por entidade de negócio
├── common/                  # recursos compartilhados por 2+ apps
│   ├── exceptions/          # tratamento de exceções da API
│   ├── pagination/          # paginação reutilizável
│   ├── permissions/         # permissions DRF compartilhadas (papéis: Gestor/Tester/Dev)
│   ├── utils/                # funções auxiliares
│   └── validators/          # validações compartilhadas
├── config/                  # settings, urls, wsgi/asgi — vazio, ainda não iniciado
├── integrations/
│   └── microsoft/
│       └── entra/            # validação de token / integração com Microsoft Entra ID
├── tests/                    # testes gerais e de integração
├── requirements.txt
└── .env.example (a criar — .env nunca é commitado)
```

Regras de responsabilidade das pastas (do README): `common/` é só para código compartilhado por 2+ apps, não é entidade própria. `integrations/` é para serviços externos — a integração com Microsoft Entra ID fica especificamente em `integrations/microsoft/entra/`. `apps/` recebe um app Django por domínio de negócio, nunca por camada técnica.

## Arquitetura de apps — PLANEJADA (ainda não criada no código)

Convenção validada: **um app Django por domínio de negócio**, não por camada técnica. Views finas (validação no serializer, decisão de negócio em `services.py` do app dono). Toda transição de status relevante grava trilha de auditoria via `apps/audit/services.py`, chamada a partir do app de origem — nunca direto da view.

Domínios previstos em `apps/`:

- **`accounts/`** — identidade do usuário (perfil + vínculo Microsoft Entra ID) e autenticação DRF via token OIDC. NÃO guarda papel nem vínculo com projeto.
- **`projects/`** — `Project` (modos UAT/Cutover independentes), `HierarchyLevel` (nomes configuráveis; UAT = 3 níveis fixos, Cutover = 2 níveis fixos, nível final sempre "Atividade"), `Membership` (usuário + projeto + papel: Gestor de Projetos / Tester / Desenvolvedor — um usuário pode ter múltiplos papéis), `CustomField` (schema de campos customizáveis por projeto).
- **`activities/`** — `Activity` e `CustomFieldValue`. `services.py` = liberação por predecessores (E lógico — todos os predecessores precisam estar Concluído) e transições de status. `management/commands/` = importação em massa via Excel (template padrão, coluna temporária de predecessores resolvida na importação, IDs únicos imutáveis após importar).
- **`issues/`** — `Issue` vinculada a `Activity`. `services.py` = transições de status e efeito sobre a Activity.
- **`audit/`** — `AuditTrail` genérico (GenericForeignKey, status_anterior/novo, data_hora, usuário). Fonte da Curva S e do tempo médio de resolução.
- **`dashboards/`** — sem `models.py`, só agrega `Activity`/`Issue`/`AuditTrail`: SPI, Curva S, cards, donuts, barras, ranking.

Nomenclatura de campos/models em **português**, alinhada ao vocabulário já fixado nas regras de negócio (RN01–RN44).

## Regras de negócio essenciais

### Activity — campos fixos
ID (auto), Nome, Status (auto), Tester, Desenvolvedor, Data Início Planejada, Data Conclusão Planejada, Data Início Real (auto), Data Conclusão Real (auto), Predecessores (múltiplos IDs separados por `;`), Evidência de aprovação, Observação de aprovação, `numero_retest` (auto, incrementa a cada Bloqueado→Liberado).

Campos customizáveis por projeto: Área, Sistema, Observações, Resultado Esperado, WBS, Transação, outros.

### Status da Activity
```
Aguardando → Liberado → Em execução → Concluído
                                     → Bloqueado (issue impeditiva) → Liberado (reteste)
                                     → Cancelado (só Gestor)
```

### Issue — campos fixos
ID (auto), Título*, Tipo*, Impeditivo*, Desenvolvedor*, Descrição (opcional se não impeditiva), Anexo (opcional se não impeditiva), Status (auto), Categorização de Impacto, Solução Proposta, Atividade vinculada (auto).

Tipos: Requisito | Performance | Dados | Integração | Interface | Configuração | Outro.

### Status da Issue
```
Aberta → Em análise (auto ao Dev acessar) → Solução proposta → Concluída (auto)
Aberta ← Solução proposta (reteste falhou, observação obrigatória)
Cancelada (auto quando atividade é cancelada)
```

### Regras críticas de negócio
- Issue impeditiva → Activity vai para Bloqueada, exige reteste.
- Issue não impeditiva → Activity continua Em execução, sem reteste.
- **Issue não impeditiva não existe no modo Cutover** — no Cutover, toda issue é impeditiva.
- Activity só sai de Bloqueado quando TODAS as issues impeditivas vinculadas estiverem em Solução proposta.
- Issues em Solução proposta são concluídas automaticamente quando a Activity é concluída.
- Aprovação simples: evidência obrigatória, observação opcional. Aprovação em lote: múltiplas atividades, uma evidência para o lote.
- Reteste reprovado: issue volta para Aberta, observação obrigatória.

### SPI (RN41–RN44)
Variante "0/50/100" do Fixed Formula Method (PMI, 2011): Aguardando=0%, Liberado=0%, Em execução=50%, Bloqueado=0%, Concluído=100%, Cancelado=excluído do cálculo.

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

Repositório separado (React), no mesmo workspace, ao lado deste. **Detalhamento de como o Claude Code deve acessar/consultar o frontend a partir daqui será adicionado em uma próxima etapa** — por ora, este arquivo cobre só o backend.
