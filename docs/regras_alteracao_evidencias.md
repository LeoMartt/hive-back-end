# Alteracao das regras de evidencia do projeto

Decisao acordada em 20/10/2026. Aplica-se a UAT e Cutover.

## Regra de negocio

- O Gestor pode mudar as exigencias mesmo depois do inicio dos trabalhos.
- A configuracao vigente na acao determina a exigencia: conclusao da atividade ou abertura da issue impeditiva. Nao se congela a regra na criacao da atividade.
- Atividades ja concluidas e issues ja abertas nao sao invalidadas nem precisam receber anexos retroativamente.
- Atividades pendentes seguem a configuracao vigente quando forem concluidas, mesmo que tenham sido criadas com outra regra.
- Novas issues impeditivas seguem a configuracao vigente na abertura. Issues nao impeditivas continuam com anexo opcional.
- A exigencia de anexo da issue nao se aplica a proposta de solucao: o anexo da solucao continua opcional.
- Alterar configuracoes nao remove arquivos existentes. O limite de tamanho vale para novos envios, inclusive anexos opcionais e de solucao. Audio e video continuam proibidos.
- Propor solucao nao conclui a atividade. Ela pode ser liberada quando nao houver outras issues bloqueadoras; a conclusao/reteste e outra acao.

## Confirmacao no frontend

Em Papeis & Config, Salvar regras abre uma confirmacao antes do PATCH quando houver mudanca de exigencia ou tamanho maximo. A janela mostra os valores anteriores e novos, a ausencia de efeito retroativo e, quando a exigencia de atividade ou o limite muda, a quantidade de atividades pendentes.

Contagem: AGUARDANDO, LIBERADO e BLOQUEADO, excluindo CONCLUIDO e CANCELADO. E uma fotografia da consulta, nao um bloqueio de concorrencia. Falha na consulta impede a confirmacao; Voltar preserva o rascunho sem salvar. Somente Confirmar alteracao envia o PATCH. Falhas no salvamento nao exibem sucesso.

GET /api/projects/<id>/evidence-impact/ fornece a contagem e exige Gestor (ou administrador), com visibilidade restrita ao projeto. A API de PATCH continua utilizavel por clientes autorizados sem a janela: confirmacao e protecao de UX, nao nova permissao de acesso.

## Historico

EvidenceRuleChange registra data, usuario, identificacao do autor e os valores anteriores/novos dos campos exigir_evidencia_atividade, exigir_evidencia_issue e anexo_max_mb. O registro e transacional com a atualizacao do projeto pela API ou pelo formulario do Django Admin. Reenvio sem mudanca e tentativa rejeitada nao criam entradas.

Consulta pelo Django Admin em Alteracoes de regras de evidencia, somente leitura. Registros anteriores a esta implementacao nao recebem historico inventado. Escritas diretas via SQL, QuerySet.update ou scripts que ignoram o servico nao passam por este registro; scripts devem usar atualizar_projeto com usuario informado.

Migration necessaria: projects.0005_evidence_rule_change.

## Fora do escopo por decisao

Nao bloquear mudancas apos o inicio do projeto, nao exigir regularizacao de registros antigos e nao manter versao individual da regra por atividade. Uma futura necessidade de comprovar a regra exata aplicada em cada operacao pode exigir snapshot por registro.
