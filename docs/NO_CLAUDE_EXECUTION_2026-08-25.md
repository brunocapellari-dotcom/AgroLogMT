# AgroLog MT — Execução sem Claude Code — 25/08/2026

Objetivo: avançar tudo que pode ser concluído via GitHub, Google Drive, pesquisa em fontes públicas e testes de CI, deixando como blockers apenas operações que exigem credenciais/runtime autenticado do GCP ou segredos de fonte.

## Concluído sem Claude Code

1. PR #107 incorporado à `main` com PTAX fail-closed, multiporto, lifecycle portuário, hidrologia, taxonomia editorial e Scheduler opt-in.
2. PTAX: fechamento atual só é aceito com `tipoBoletim=Fechamento`; intraday e fechamento anterior não substituem o dia corrente.
3. Portos: Santos isolado não satisfaz gate multiporto; gate exige Santos + Paranaguá/Antonina + Arco Norte.
4. Portos: estados canônicos `PROGRAMADO -> ATRACADO -> DESATRACADO -> CONCLUIDO`; regressão bloqueada.
5. Portos: volume programado jamais é promovido a realizado por passagem de tempo ou mudança de status.
6. Hidrologia: deltas observados 1/3/7/15 dias sem interpolação.
7. Hidrologia: climatologia P01/P05/P10/P25/P50/P75/P90/P95/P99 com histórico mínimo explícito.
8. Hidrologia: nível de rio não gera automaticamente uma restrição de navegação.
9. ANA pública: boletins Madeira e Amazonas de 24/08/2026 foram localizados; a telemetria live autenticada continua separada.
10. MDIC/SECEX: release da 3ª semana de agosto/2026 confirmado como preliminar; números não devem ser promovidos sem detalhe primário materializado.
11. `NEWS_SIGNAL v0.5`: produtores determinísticos adicionados para PTAX, revisão de produção CONAB, delta hidrológico e transição portuária.
12. `NEWS_SIGNAL`: PTAX produtor exige dois fechamentos oficiais distintos.
13. `NEWS_SIGNAL`: revisão CONAB exige dois `release_id` distintos da mesma safra/geografia/produto; comparação entre safras dentro do mesmo workbook é bloqueada.
14. `NEWS_SIGNAL`: hidrologia exige `OBSERVED_DELTA` sem interpolação.
15. `NEWS_SIGNAL`: replay portuário sem avanço de estado não gera sinal.
16. Writer `NEWS_SIGNAL`: corrigida falsa colisão quando a única diferença entre duas execuções é `data_coleta`; primeiro artefato permanece imutável.
17. Writer `NEWS_SIGNAL`: divergências de conteúdo para a mesma identidade continuam fail-closed.
18. Materialidade continua externa ao adapter; produtores não inventam limiar editorial.
19. Evidência `estimado` permanece distinta de `observado` na revisão CONAB.
20. Testes adicionados para todos os comportamentos acima.

## Em validação de CI desta onda

- suíte completa de unit tests;
- produtores `NEWS_SIGNAL`;
- recollection/idempotência;
- serialização e contratos já existentes;
- compatibilidade com PTAX, CONAB, hidrologia e lifecycle portuário.

## Blockers reais que permanecem

### GCP autenticado

1. Preflight do projeto/serviços/IAM.
2. CONAB Armazéns #1 no BigQuery real.
3. Manifesto/RAW/readback real.
4. CONAB Armazéns #2 e prova de idempotência no ambiente real.
5. Deploy do AgroLog Gateway no Cloud Run.
6. Comparação Gateway x BigQuery.
7. Materialização dos Data Marts somente após QA real das tabelas requeridas.
8. Ativação produtiva de CONAB Safra e IMEA após P0/P1.

### Segredos/runtime de fonte

9. ANA HidroWebService/telemetria autenticada via Secret Manager ou runtime seguro.
10. Qualquer credencial de fonte privada/licenciada, sem persistir segredo em GitHub, Drive ou Obsidian.

### Fonte pública ainda parcial

11. Multiporto só passa quando houver observações operacionais recentes e verificáveis nos três sistemas geográficos requeridos.
12. Comex microdados dependem de materialização/QA do acesso operacional; não criar tabela fictícia para fechar gate.

## Regra de promoção

Nenhum item `DONE_CODE`, `READY_GCP`, `SOURCE_LAG` ou `PARTIAL_MULTI_PORT` pode ser convertido para `PRODUCTION_READY` apenas por documentação. A promoção exige evidência produzida pelo runtime correspondente e readback verificável.

## Próximo comando no ambiente autenticado

```bash
PROJECT_ID=<projeto> MANAGE_SCHEDULER=0 bash scripts/homologate_n6_core.sh
```

Esse comando é o principal ponto em que Claude Code, um operador humano ou outro executor com `gcloud` autenticado passa a agregar valor. O restante da arquitetura, código, revisão, pesquisa pública e testes continua independente dele.
