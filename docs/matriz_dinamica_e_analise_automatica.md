# Permissoes por projeto e analise automatica

Decisoes implementadas em 21/10/2026. Aplicam-se a UAT e Cutover.

## Matriz

- A matriz deixa de ser informativa. O Gestor pode alterar permissoes de Tester e Dev, confirmar e salvar no projeto.
- O Gestor preserva todas as permissoes e o controle da matriz/equipe. Somente Gestor ou administrador pode editar a matriz; delegar configuracao de limiares/evidencias nao concede essa capacidade.
- A criacao de projeto nao pertence a uma matriz de projeto existente. A autorizacao global/manual de criacao permanece fora deste ajuste.
- Os valores padrao mantem as permissoes anteriores. Sem customizacao, Tester e Dev nao recebem poderes novos.
- Permissoes se acumulam quando o usuario tem mais de um papel. Nao se propagam para outros projetos.
- Acoes sobre registros continuam restritas aos responsaveis: Tester da atividade e Dev da atividade/issue, conforme o registro operado. O Gestor nao tem essa restricao de atribuicao.
- Permissao nao ignora estado: por exemplo, Cancelar issue continua exigindo Em analise. Nao existe Em execucao nem mudanca automatica ao abrir atividade.
- Ler atividades/issues, acessar dashboard e exportar tem controles especificos. Visualizar dashboard exige poder visualizar os dados; a interface ajusta essa dependencia e a API rejeita configuracao contraditoria.
- Ocultar exportacao no frontend nao impede alguem autorizado a ler dados de produzir um arquivo por conta propria; a exportacao de auditoria no backend tem sua propria autorizacao.
- A configuracao usa Project.matriz_permissoes e a lista efetiva vem em permissionMatrix. A API rejeita chaves desconhecidas, valores nao booleanos e retirada de permissoes do Gestor.
- Alteracoes da matriz e do modo automatico pela API registram autor, data, antes e depois em Project.historico_politicas, visivel no Admin como somente leitura. Escrita SQL direta nao tem esse registro.
- Frontend recarrega configuracoes ao navegar entre paginas do projeto; a API aplica a matriz persistida a cada requisicao, inclusive se uma tela antiga ainda mostrar um botao.

## Analise automatica

- issueAutoAnalysis mapeia Project.issue_analise_automatica. Padrao: desligado.
- Ligado: novas issues entram diretamente em EM_ANALISE, com analise_iniciada_em preenchida pelo sistema.
- Desligado: novas issues entram ABERTA e o usuario autorizado precisa acionar Iniciar analise.
- Alterar o modo nao move issues ja existentes. Nao ha cobranca retroativa de anexos.
- O formulario exibe Ativado/Desativado e Alteracoes nao salvas. Ao salvar uma mudanca do modo, solicita confirmacao; Edições Salvas so aparece depois da resposta de sucesso.

## Conclusao e dashboard

- Concluir atividade agora conclui tambem todas as issues SOLUCAO_PROPOSTA da mesma atividade, na mesma transacao. O Tester autorizado nao precisa de outra chamada de resolucao.
- Issues de outras atividades e issues ja canceladas nao sao alteradas por essa conclusao.
- A pagina recarrega a lista de issues depois da conclusao, em vez de tentar conclui-las uma a uma no frontend.
- Para dados antigos inconsistentes, usar `python manage.py reconciliar_issues_concluidas` primeiro. Com `--apply`, fecha apenas issues SOLUCAO_PROPOSTA de atividades CONCLUIDO, registrando a data atual da reconciliacao, sem inventar uma data historica. `--project UUID` limita o escopo.
- O dashboard separa Total, Abertas, Em analise, Solucao proposta, Concluidas e Canceladas. Os cinco estados somam o total; indicadores de subconjuntos nao fazem parte dessa soma.
- Tempo medio de resolucao usa somente issues concluidas, com duracao valida e nao negativa. Canceladas nao entram na media.

Migration: projects.0006_project_permission_matrix_and_auto_analysis.

Os documentos Word e figuras produzidos com referencia em 20/10/2026 descrevem a versao anterior. Ao atualizar o TCC, considerar estes campos e regras: a analise manual passa a ser o padrao configuravel, a matriz passa a persistir e a conclusao de atividade/issues passa a ser atomica no backend.
