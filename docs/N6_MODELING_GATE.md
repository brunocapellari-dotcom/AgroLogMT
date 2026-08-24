# N6 — Gate de Data Mart e Modelagem

## Objetivo

Impedir que disponibilidade de codigo seja confundida com prontidao cientifica. O Data Mart Soja MT e os seis primeiros modelos N6 so avancam quando dados canonicos, historico, point-in-time e baselines estiverem materialmente prontos.

## Gate do Data Mart

O contrato executavel e `contracts/soy_mt_datamart.v1.json`. Os blocos obrigatorios da V1 sao:

1. producao;
2. armazenagem/geografia;
3. comercializacao;
4. comercio exterior;
5. clima.

Mercado, logistica, portos, hidrologia e industria continuam obrigatorios para a versao analitica completa, mas nao devem bloquear a primeira materializacao minima se ainda estiverem fora do gate produtivo.

Cada bloco requerido deve possuir fonte canonica com:

- `qa_status=pass`;
- metadados point-in-time suficientes para reconstruir o que era conhecido no cutoff;
- geografia canonica quando aplicavel;
- historico minimo definido no contrato;
- nenhuma tabela vazia criada apenas para satisfazer arquitetura.

`models/readiness.py` implementa o gate deterministico. O gate nao executa inferencias: ele recebe inventario de tabelas/series e retorna falhas explicitas.

## Gate dos modelos

`models/feature_contracts.json` define target, grao, historico minimo, features obrigatorias, baselines, validacao e leakage guards dos seis modelos iniciais.

Nenhum modelo pode ser promovido apenas porque conseguiu ajustar uma amostra. O minimo e:

1. target canonico;
2. features obrigatorias disponiveis;
3. historico minimo;
4. dataset point-in-time;
5. baseline executavel;
6. validacao temporal fora da amostra;
7. estabilidade por safra/regime/regiao quando aplicavel;
8. auditoria da interpretacao economica/operacional.

## Baselines obrigatorios

`models/baselines.py` implementa primitivas simples e auditaveis:

- media movel;
- tendencia linear;
- mesmo periodo do ano anterior;
- media sazonal;
- probabilidade climatologica;
- identidade deterministica de balanco;
- identidade deterministica de paridade.

Modelos sofisticados precisam superar ou agregar valor material a esses referenciais. Um modelo mais complexo que nao melhora baseline de forma estavel nao deve ser promovido.

## Anti-leakage

Regras permanentes:

- `data_referencia` nao e data de disponibilidade;
- revisao futura nao entra em treino/backtest de cutoff anterior;
- realizado posterior ao cutoff nao entra como feature;
- forecast deve preservar initialization/lead/valid time;
- reanalise posterior nao substitui forecast historico sem experimento separado;
- target da janela futura nunca entra como feature direta ou derivada;
- transformacoes precisam ser ajustadas apenas no conjunto de treino quando houver risco de leakage.

## Proximo passo operacional

Quando o GCP real estiver homologado, gerar inventario automatico das tabelas canonicas, executar `evaluate_datamart`, construir a primeira feature matrix point-in-time e somente entao iniciar treino real dos modelos elegiveis.
