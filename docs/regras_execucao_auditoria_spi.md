# Regras de execucao, retestes, SPI e auditoria

Decisoes de 22/10/2026. Substituem as regras anteriores conflitantes.

## Issues de Cutover

- Cutover aceita somente issues impeditivas, tanto na API quanto no servico de criacao.
- No formulario, Impeditivo fica fixo em Sim para Cutover; UAT continua aceitando Sim e Nao.
- A obrigatoriedade de evidencia ainda depende da configuracao do projeto. Ser impeditiva nao implica obrigatoriedade de anexo quando a configuracao estiver desligada.
- Issues antigas nao impeditivas nao sao convertidas silenciosamente. A restricao vale para a criacao daqui em diante.

## Retestes e inicio real

- Abrir issue impeditiva ou bloquear manualmente NAO incrementa reteste.
- O contador incrementa uma vez quando uma atividade com issue muda de BLOQUEADO para LIBERADO.
- Duas issues bloqueadoras nao geram dois retestes: a primeira solucao nao libera a atividade; a ultima permite liberar e gera um reteste.
- Repetir uma chamada depois da liberacao nao incrementa novamente. Validacoes de estado e bloqueios transacionais evitam reprocessamento da mesma transicao.
- Cancelar atividade nao conta reteste. Se a retirada do bloqueio levar a AGUARDANDO por predecessoras pendentes, nao ocorreu BLOQUEADO -> LIBERADO e o contador nao aumenta nessa transicao.
- Criar qualquer issue, impeditiva ou nao, registra inicio real se ainda nao existir, usando a data local da primeira issue. Bloquear manualmente tambem registra inicio real. Se nenhuma execucao anterior existir, a conclusao registra inicio e fim reais juntos. Liberacao por predecessoras, cancelamento e abrir a pagina nao iniciam a execucao por si so. Nao foi recriado Em execucao.
- A migration reconcilia contadores antigos somente quando todas as entradas de bloqueio registradas explicam exatamente o contador anterior e existe issue vinculada. A correcao gera um novo evento, sem reescrever o historico. Casos sem evidencia suficiente nao sao estimados.

## SPI = EV / PV, pesos iguais por atividade

Atividades canceladas sao excluidas de ambos os lados.

EV (valor realizado):
- 100% para atividade concluida.
- 50% para atividade ainda nao concluida com inicio real no dia de referencia ou antes, inclusive bloqueada.
- 0% quando nao ha inicio real ate o dia de referencia.

PV (valor planejado):
- 100% quando a conclusao planejada chegou ou passou.
- 50% quando o inicio planejado chegou, mas a conclusao planejada ainda nao chegou.
- 0% antes do inicio planejado.

SPI e a soma de EV dividida pela soma de PV. Com PV zero, retorna null (sem valor), nao zero nem infinito. Pode ultrapassar 1 em situacao de adiantamento. Uma atividade planejada para iniciar e terminar no mesmo dia conta 100% de PV nesse dia.

O backend usa a mesma regra na listagem/detalhe do projeto e no dashboard; o calculo local dos mocks tambem foi atualizado. A Curva S agora usa os mesmos pesos 0/50/100: planejado pelas datas planejadas, realizado pelas datas reais, ambos divididos pela quantidade de atividades nao canceladas. Esta decisao substitui a curva anterior de conclusoes acumuladas. No dia de referencia, EV/PV dos pontos da curva coincide com o SPI; percentuais arredondados na tela podem produzir pequena diferenca se forem divididos manualmente.

O realizado nao e projetado depois do dia de referencia; o planejado continua ate a ultima conclusao planejada. Cada atividade vale 0,5 ponto no inicio e mais 0,5 na conclusao. Tooltip mostra pontos, sem denominador, nao uma quantidade fracionaria de atividades. Uma atividade iniciada e liberada apos reteste continua com 50% de EV, nao volta a zero.

Datas inconsistentes: uma atividade marcada Concluido mas sem conclusao real nao fornece prova da data historica da conclusao. A curva conserva os 50% do inicio comprovado e reflete 100% somente na fotografia do dia de referencia, sem gravar uma data ficticia. Uma conclusao real futura em um registro ja concluido recebe o mesmo tratamento. O caminho normal de conclusao sempre grava a data real; esses fallbacks sao defensivos para dados externos/antigos. Atividade nao concluida nao recebe 100% apenas por ter uma data final indevida.

Para dados antigos sem inicio real, `python manage.py reconciliar_inicio_real` simula a recuperacao por primeira issue, bloqueio registrado ou conclusao real. Com `--apply`, preenche apenas datas ausentes e acrescenta evento de auditoria de correcao. Reexecucao nao sobrescreve datas nem duplica eventos. Sem prova consistente, nao estima datas.

## Auditoria de atividades

- ActivityStatusEvent e a trilha oficial de criacao e transicoes executadas pelos servicos da aplicacao, importacao e Django Admin.
- Cada registro contem data/hora, estado anterior/novo, texto, origem, motivo, autor e snapshots de nome/email do autor e nome da atividade. Renomear usuario ou atividade nao reescreve esses snapshots.
- O salvamento da atividade e o append do evento ficam na mesma transacao; falha no evento reverte a mudanca de estado.
- Eventos nao possuem operacao de edicao/exclusao na API ou no Admin. O banco rejeita UPDATE e DELETE por triggers; PostgreSQL tambem rejeita TRUNCATE da tabela.
- historico_status permanece somente como coluna legada congelada no banco; nao e mais alimentada nem usada como fonte da interface.
- A migration preserva textos/datas anteriores como eventos legados. Autor desconhecido e identificado como tal, sem atribuir retrospectivamente a acao a alguem.
- A interface mostra a trilha persistida recebida da API; nao reconstrui eventos reais a partir do status atual, das issues ou dos responsaveis atuais.
- FKs protegidas impedem apagar atividades/autores que tenham eventos associados. Cancelamento/desativacao continuam sendo os fluxos normais.

Limite de seguranca: triggers nao impedem um DBA/proprietario do esquema de desabilitar a protecao ou alterar o esquema. Em producao, separar a conta de migrations da conta de execucao, que nao deve ter privilegios de DDL. Operacoes SQL externas nos dados da atividade nao devem substituir os servicos de dominio; os registros de auditoria existentes continuam protegidos.

Migrations: activities.0007_activitystatusevent e activities.0008_freeze_activity_audit.
