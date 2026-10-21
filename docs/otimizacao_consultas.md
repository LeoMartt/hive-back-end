# Carregamento de dados por tela

Implementado em 21/10/2026, sem alterar layout, filtros, agrupamentos ou regras de negocio.

## Contratos

- GET activities/ e issues/ continuam completos por padrao, mantendo compatibilidade.
- Com view=summary, as listas omitem textos de detalhe, evidencias e historico. Os campos de tabela, filtros, datas e identificadores permanecem.
- GET activities/<id>/ e issues/<id>/ continuam completos. A tela de atividade busca somente o registro, sua primeira predecessora quando existe (painel e anexos herdados), e as issues vinculadas com activityId.
- A tela de issue busca a issue individual e a atividade vinculada. Nao busca as listas completas do projeto.
- Exportacoes carregam registros completos somente ao clicar, com ids numericos do filtro atual. O cliente preserva a ordem e divide selecoes grandes em blocos sequenciais de ate 200 IDs.
- GET projects/<id>/dashboard/?today=YYYY-MM-DD entrega cards, SPI, distribuicao, pontos da curva S e ate sete registros recentes. A data opcional permite manter o mesmo dia local do navegador; sem ela, usa a data local do servidor.
- O dashboard respeita dashboard_view e data_view. Os demais endpoints mantem suas verificacoes de acesso.

## Consultas

- Quantidade de issues abertas das atividades calculada por agregacao, sem uma consulta por atividade.
- Quantidade de atividades/concluidas dos projetos anotada na consulta, sem repetir count para cada campo.
- Predecessoras da listagem carregadas somente com seus IDs; campos pesados de detalhe nao sao lidos nas respostas resumidas.
- Resposta da importacao reutiliza o queryset otimizado para serializar os registros criados.
- Dashboard usa contagens/agregacoes e apenas datas para a curva; nao carrega evidencias, descricoes ou historicos completos. A curva usa contadores por dia e soma acumulada, sem filtrar todas as atividades novamente para cada dia.
- As sete alteracoes recentes mantem a semantica anterior: ultimos registros atualizados de atividades/issues, nao um novo log de eventos.

## Frontend

- Dentro de um projeto, useProjects busca o projeto atual pelo ID, nao todos os projetos.
- Requisicoes GET simultaneas iguais de usuario, projeto e resumos sao compartilhadas por conta autenticada. Nao existe cache duradouro de permissoes. Apos terminar a requisicao, a proxima leitura pode buscar dados atuais.
- Escritas invalidam o compartilhamento de leituras em andamento, evitando que uma leitura posterior reutilize uma requisicao anterior a mudanca.
- Tipos e schemas separam resumos de detalhes. Campos omitidos nao sao preenchidos com conteudo ficticio.
- Mocks continuam locais. Banco real nao recebe fixtures de verificacao.

## Verificacao e limites

- Testes cobrem contratos, filtro de exportacao, permissoes, valores da curva/indicadores, projeto vazio e quantidade constante de consultas ao aumentar registros.
- Testes de interface com transporte simulado cobrem dashboard sem listas completas, detalhes, filtro/exportacao XLSX e conclusao com atualizacao da issue vinculada.
- Preservadas as formulas atuais, inclusive o SPI calculado pelo front anteriormente: concluidas / atividades nao canceladas. Nao houve redefinicao de indicador nesta otimizacao.
- Sem migrations novas, indices novos, paginacao de atividades ou mudancas no processamento em lote.
- Ainda ha trafego proporcional a quantidade de linhas na tabela. Paginacao/carregamento por modulo e medicao com carga representativa ficam para uma etapa posterior.
