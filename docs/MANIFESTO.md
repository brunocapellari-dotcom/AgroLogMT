# AgroLog MT — Manifesto Mestre

**Versão vigente:** 1.1 — 2026-08-12

Este documento é a referência consolidada do AgroLog MT. Decisões explícitas posteriores substituem decisões antigas conflitantes.

## Fontes de verdade

- **BigQuery:** fonte única de verdade analítica.
- **GitHub:** código, schemas, SQL, contratos, testes, prompts e conhecimento Markdown.
- **Google Drive:** documentos, relatórios, fontes recebidas manualmente e bases resumidas para consulta humana.
- **Google Cloud Storage:** arquivos brutos imutáveis, snapshots e vintages.
- **Obsidian:** interface de conhecimento conectado sobre `knowledge/` versionado neste repositório.

## Arquitetura

`Fontes -> raw/GCS -> staging BigQuery -> DQ -> MERGE/append -> curated BigQuery -> AgroLog Gateway -> ChatGPT/Claude -> relatórios/alertas`

Nenhuma IA deve receber acesso irrestrito ao banco. O AgroLog Gateway deve fornecer contratos semânticos, filtros, limites, logs e permissões mínimas.

## Campos temporais obrigatórios

Quando aplicáveis, todas as tabelas devem possuir:

- `data_referencia`
- `data_publicacao`
- `data_coleta`
- `competencia`

## Evidência

Classes oficiais:

- `OBSERVADO`
- `DECLARADO`
- `INFERIDO`
- `ESTIMADO`
- `PROJETADO`
- `NEGOCIADO_CONFIRMADO`

Nunca apresentar estimativa como observação. Dados públicos não permitem afirmar frete real pago, contratação individual, disponibilidade real de caminhão ou volume por trading sem fonte autorizada.

## BigQuery

- criar tabelas sob demanda;
- preferir particionamento por `data_referencia`;
- clusterizar pelas chaves reais de consulta;
- usar staging antes da camada final;
- carga idempotente;
- preservar histórico e snapshots;
- não transportar conceitos de índices de PostgreSQL para BigQuery.

## Prioridade de implantação

1. CONAB Armazéns ponta a ponta no BigQuery real.
2. AgroLog Gateway conectado à primeira tabela.
3. IMEA.
4. Comex Stat.
5. Portos/line-up.
6. ANP.
7. NOAA/INMET/ANA.
8. IBGE/BCB/USDA/Argentina.
9. Indicadores proprietários e backtest.
10. Scheduler somente após fontes reais estáveis, DQ, logs, IAM mínimo e monitoramento de custo.

## Nome e escopo

O nome oficial é **AgroLog MT**. Nomes técnicos legados contendo `360` podem permanecer quando a mudança gerar risco de compatibilidade.

O módulo de **gado de corte é separado** e não deve aparecer no relatório agrícola/logístico principal, nem como alerta, resumo ou impacto cruzado.

## Obsidian

O Vault lógico é `knowledge/`. GitHub é a fonte de verdade dos Markdown; Obsidian é a interface de navegação/edição. Não sincronizar a mesma pasta simultaneamente por Google Drive e GitHub.

## Execução por IA

- ChatGPT/OpenAI: governança, requisitos, semântica, pacotes determinísticos, auditoria funcional e relatórios.
- Claude Code: implementação, testes, pipelines, Cloud Run, BigQuery, migrações e observabilidade.
- Gemini: validação independente/pesquisa/multimodal quando necessário.
- decisão final de publicação/alteração crítica: humana.
