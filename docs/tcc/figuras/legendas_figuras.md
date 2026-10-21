# Figuras tecnicas do HIVE para o TCC

Base: documento HIVE Modelagem do banco de dados e regras de negocio e codigo correspondente. Referencia: 20/10/2026.

Cada figura foi gerada em SVG vetorial e PNG com metadado de 300 dpi. O tamanho em pixels consta abaixo. O SVG permite ampliacao sem perda de qualidade; o PNG pode ser inserido no Word.

A numeracao abaixo e sugestiva e deve acompanhar a ordem final do TCC. Fonte sugerida para todas: Elaborado pelos autores a partir da implementacao do HIVE (2026).

## Figura 1

Modelo entidade-relacionamento do banco de dados do HIVE.

Nove tabelas de domínio, 100 campos e 19 FKs. Todos os campos concretos dos modelos são exibidos; tabelas auxiliares do Django não são incluídas. O SVG é indicado para ampliar detalhes.

Arquivos: 01_modelo_entidade_relacionamento.svg e 01_modelo_entidade_relacionamento.png.
Resolucao do PNG: 6171 x 9000 pixels.

## Figura 2

Diagrama de estados das atividades e condições de transição.

Considera predecessoras concluídas ou canceladas como resolvidas. Não há estado Em execução. As linhas de cancelamento partem somente de estados não terminais.

Arquivos: 02_estados_atividades.svg e 02_estados_atividades.png.
Resolucao do PNG: 4200 x 3283 pixels.

## Figura 3

Diagrama de estados das issues e cancelamento vinculado à atividade.

Distingue cancelamento direto, permitido apenas Em análise, do efeito do cancelamento da atividade pelo Gestor. A transição para análise é manual.

Arquivos: 03_estados_issues.svg e 03_estados_issues.png.
Resolucao do PNG: 4083 x 4200 pixels.

## Figura 4

Fluxo integrado de bloqueio e liberação de uma atividade por issues impeditivas.

Solução proposta pode remover o bloqueio, mas não conclui a atividade. Outras issues e predecessoras são consideradas. A resolução das issues após concluir a atividade é solicitada por chamadas separadas da página de detalhe.

Arquivos: 04_fluxo_integrado_atividade_issue.svg e 04_fluxo_integrado_atividade_issue.png.
Resolucao do PNG: 2318 x 4200 pixels.

## Figura 5

Arquitetura lógica do HIVE e suas integrações.

Apresenta React, API Django e DRF, PostgreSQL, Entra ID e Azure Blob Storage. É uma visão lógica, sem afirmar topologia de hospedagem ou recursos efetivamente implantados.

Arquivos: 05_arquitetura_logica.svg e 05_arquitetura_logica.png.
Resolucao do PNG: 4200 x 2705 pixels.

## Figura 6

Fluxo de importação em massa de atividades por arquivo CSV ou XLSX.

Distingue validação, criação de atividades, associação de predecessoras e commit atômico. Não representa detecção de ciclos indiretos, inexistente no código analisado.

Arquivos: 06_importacao_em_massa.svg e 06_importacao_em_massa.png.
Resolucao do PNG: 3304 x 4200 pixels.

## Figura 7

Fluxo de evidências e geração do pacote de auditoria do projeto.

Arquivos ficam no storage e metadados no PostgreSQL. O ZIP contém DOCX com links, sem incluir os binários. O anexo da solução é opcional. A validade padrão de 180 dias conta do upload, sem renovação automática na exportação.

Arquivos: 07_evidencias_auditoria.svg e 07_evidencias_auditoria.png.
Resolucao do PNG: 4200 x 3565 pixels.

## Observacoes de uso

- A figura 1 e densa por incluir todos os campos e relacionamentos. Para impressao, considere uma pagina ampliada ou um anexo; mantenha o SVG para consulta com zoom. A legenda nao transforma esse desenho em uma auditoria do banco implantado.
- Linhas tracejadas possuem significados locais explicados em cada figura, e nao uma unica semantica global.
- A matriz de papeis e por projeto. Tester proprio e Dev atribuido dependem do vinculo e da responsabilidade; papeis acumulados combinam permissoes. Administradores Django possuem excecoes no backend.
- As figuras representam a implementacao documentada, inclusive suas limitacoes. Nao significam que o SPI seja o indice EV/PV nem que existam auditoria imutavel, verificacao antivirus ou transacao distribuida com o storage.
