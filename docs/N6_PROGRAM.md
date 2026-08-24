# Programa N6 — AgroLog MT

## Objetivo

Levar todos os domínios oficiais do AgroLog MT ao N6 — pós-doutorado aplicado — por evidência reproduzível, não por volume de material armazenado.

## Gates obrigatórios de promoção

Um domínio só recebe N6 quando todos os gates abaixo forem aprovados:

1. fundamentos científicos e literatura avançada;
2. estado da arte documentado;
3. fontes canônicas e direitos de uso identificados;
4. histórico estruturado e point-in-time quando necessário;
5. metodologia versionada;
6. modelo quantitativo ou procedimento formal adequado ao problema;
7. validação empírica e benchmark;
8. casos históricos e mudanças de regime;
9. causalidade ou mecanismo explicitamente tratado;
10. incerteza, limitações e alternativas explicativas;
11. aplicação operacional demonstrada;
12. auditoria independente aprovada.

Não existe média compensatória: um gate material reprovado limita o nível consolidado.

## Programas

- **N6-Foundation** — método científico, dados, governança, proveniência e engenharia de dados.
- **N6-Agro** — agronomia, produção, solo, nutrição, sementes, fitossanidade e mecanização.
- **N6-Markets** — economia agrícola, oferta/demanda, formação de preços, comercialização e derivativos.
- **N6-Climate** — meteorologia, agrometeorologia, climatologia e hidrologia.
- **N6-Logistics** — rodoviário, armazenagem, ferrovia, hidrovia, portos, line-up, AIS, shipping e chartering.
- **N6-Industry** — agroindústria, bioenergia, insumos e engenharia de processos.
- **N6-Corporate** — estratégia, finanças, valuation, M&A, crédito, covenants, procurement, S&OP e risco.
- **N6-Regulatory** — tributação, contratos, compliance, sanções, sustentabilidade, carbono, rastreabilidade e licenciamento.
- **N6-Quant** — estatística, econometria, forecasting, pesquisa operacional, GIS, sensoriamento remoto e ML.
- **N6-Integration** — grafo causal, biblioteca de eventos, agentes, auditoria e decisão interdisciplinar.

## Primeiro ciclo vertical: Foundation + Soja MT

A ordem executável é:

1. contrato canônico de dados;
2. dicionário de métricas;
3. CONAB Armazéns ponta a ponta;
4. CONAB Safra;
5. IMEA;
6. Comex Stat;
7. clima;
8. Data Mart Soja MT;
9. seis primeiros modelos;
10. backtests point-in-time;
11. primeiro relatório integrado N6;
12. exame e auditoria de promoção por domínio.

## Registro inicial de modelos

A fonte canônica do inventário de modelos é `models/registry.json`. Todo modelo precisa registrar objetivo, target, inputs, baseline, validação, métricas, limitações e status. O status `production_validated` só é permitido após validação temporal fora da amostra e auditoria independente.

## Critério point-in-time

Backtests, previsões e estudos de impacto devem reconstruir apenas informação que estava disponível na data de corte. `data_referencia` não substitui `data_publicacao` nem `data_coleta`. Revisões posteriores de safra, estoque ou indicadores não podem contaminar previsões históricas.

## Estado do ciclo N6-01

### Implementado no repositório

- contrato canônico de metadados de dados;
- dicionário inicial de métricas;
- especificação da fonte CONAB Armazéns;
- parser tolerante a encoding/delimitador e preservação do payload original;
- deduplicação intra-snapshot e identificadores estáveis;
- quality flags e quality score;
- loader BigQuery idempotente por snapshot;
- histórico de snapshots sem interpretar ausência como exclusão;
- tabela de auditoria de carga;
- view de snapshot mais recente;
- primeira superfície controlada do AgroLog Gateway para armazenagem;
- registro dos seis primeiros modelos;
- métricas e rolling-origin para backtests;
- testes unitários do parser, consultas e framework de backtest.

### Gate que continua obrigatoriamente aberto

A primeira carga real no BigQuery e o deploy do Gateway precisam ser executados em ambiente GCP autenticado e produzir evidência operacional. Código pronto não equivale a execução real. Nenhum módulo deve ser marcado N6 antes desses testes e das validações empíricas subsequentes.
