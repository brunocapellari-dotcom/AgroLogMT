# AgroLog Intelligence — auditoria Sellable V1 — 07/10/2026

Issue: #191
Base auditada: `feat/full-source-activation-20261001`
Head inicial: `1e3565bd72f5d5a856a26e0ae7e26926ea6b78ef`

## Regra desta release

A expansão horizontal está congelada. O objetivo é fechar uma vertical comercial integrada:
`fontes → dados → histórico → análise → relatório → dashboard → saída cliente`.

Classificações:
- **FUNCIONAL**: existe código e contrato executável; ainda pode depender de freshness/live para a release.
- **PARCIAL**: existe implementação útil, mas falta elo obrigatório do fluxo.
- **QUEBRADO**: implementação existe, mas há evidência de falha bloqueante.
- **AUSENTE**: não há implementação suficiente.
- **DUPLICADO**: responsabilidade concorrente sem fonte canônica clara.
- **PÓS-RELEASE**: fora da vertical comercial desta semana.

## Auditoria executável

| Área | Estado | Evidência encontrada | Gap para Sellable V1 |
|---|---|---|---|
| Governança, provenance e classes de evidência | FUNCIONAL | `AGENTS.md`, `CLAUDE.md`, Data Source Registry, source promotion, freshness e release gate | executar gate no SHA candidato |
| BigQuery / marts | PARCIAL | `models/agrolog_360_marts.py`, scripts de materialização e readiness | marts comerciais ainda não cobrem todas as dimensões exigidas |
| CONAB Safra | PARCIAL | collector, pipeline, BigQuery, backfill, inventário/vintages e testes | live/backfill precisam ser executados e validados |
| IBGE PAM | PARCIAL | collector, BigQuery, hurdles e testes | execução live e integração ao relatório |
| IMEA | PARCIAL | migration, XLSX pipeline, BigQuery e testes | depende workbook autorizado/freshness; não pode bloquear relatório inteiro |
| PTAX | FUNCIONAL | collector BCB, mart current, testes, registry active | executar freshness no ciclo da release |
| Comex Stat | FUNCIONAL/PARCIAL | API collector, BigQuery, backfill e validações | confirmar carga/freshness atual; usar em exportação/logística |
| USDA PSD / Export Sales | PARCIAL | registry/configs e adapters | auth/live, materialização histórica e integração |
| USDA WASDE / Crop Production / Crop Progress / WAP / GMR / OMT | AUSENTE/PARCIAL | registry possui fontes planejadas; NASS possui runtime separado | implementar aquisição/normalização mínima da release |
| Argentina oficial | AUSENTE | SAGyP está apenas planned; não há collector operacional dedicado | collector + histórico + integração safra/clima |
| INMET | PARCIAL | normalizador diário existe | aquisição oficial, alertas/boletins e freshness |
| CPTEC/INPE | PARCIAL | normalizador de previsão existe | aquisição oficial, runs e comparação entre rodadas |
| Copernicus/ERA5 | PARCIAL | collector existe e fonte gated | credencial/live conforme termos |
| ECMWF/GFS/GEFS/ICON/CMC/UKMET | AUSENTE no engine integrado | não há camada multimodel canônica encontrada | normalização comum, run diff, consenso/dispersão |
| Agroclima | PARCIAL | normalização diária, rolling rain e eventos básicos | cultura × fase × clima observado × previsão |
| Preços físicos | AUSENTE/PARCIAL | CEPEA apenas planned; referências IMEA dependem workbook | ao menos uma referência física autorizada e freshness |
| CBOT/CME/B3 | AUSENTE no produto integrado | sem collector canônico encontrado para preço de grãos | ingestão autorizada/licenciada ou fonte declarada |
| Fretes WhatsApp | PARCIAL | contrato/normalizador/modelo de ofertas existe | runtime do WhatsApp AI ainda gated/sem execution_ref no registry |
| Frete histórico e estatística | PARCIAL | R$/t, R$/t.km e mart de lanes existem | comparação 1d/7d/30d/safra/histórico e pressão por corredor |
| Logística/portos | FUNCIONAL/PARCIAL | Maritime, line-up, AIS, storage, hydrology, Comex | integrar somente sinais úteis ao relatório comercial |
| Analysis Engine | PARCIAL | commercial_signals + agrolog_360 | faltava contrato único Evidência → Mecanismo → Impacto e tendências separadas |
| Histórico / sazonalidade / percentis | PARCIAL | backfills e point-in-time existem por módulos | faltava função canônica transversal de comparação |
| Anos análogos | AUSENTE | não encontrado motor canônico | implementar somente com critérios explícitos; não forçar analogia |
| Relatório comercial de 30 seções | AUSENTE | `AGROLOG_DAILY_V1.md` é especificação, não renderer final | gerar Markdown/JSON com gate de sellability |
| Dashboard geral | PARCIAL | Gateway Intelligence + Maritime UI | faltam rotas/páginas comerciais exigidas |
| CI/CD | PARCIAL | full-project gate robusto, GCE runner scripts | head auditado sem workflow/status; final gate ainda não provado |
| Deploy GCP | PARCIAL | scripts Cloud Run/GCP/WIF existem | precisa execução real no SHA candidato |
| Duplicações relevantes | NÃO IDENTIFICADAS nesta vertical | há componentes antigos com nome `agrolog360`, mas são canônicos e compatíveis | não renomear nesta semana; evitar regressão |
| Biomassa/pecuária/expansões não essenciais | PÓS-RELEASE | módulos existem | não consumir esforço da Sellable V1 |

## Conclusão da auditoria

O bloqueio comercial não é ausência de plataforma. É falta de fechamento vertical e de prova LIVE no mesmo SHA.

Prioridade de implementação desta branch:
1. histórico/comparações transversais;
2. multimodel meteorológico e run-diff;
3. análise com evidência/mecanismo/impacto;
4. relatório comercial com gate de sellability;
5. marts/endpoints necessários para alimentar o relatório/dashboard;
6. dashboard comercial reutilizando o frontend existente;
7. execução CI + E2E + evidência.

Nenhum componente será marcado SELLABLE enquanto o gate de release comercial retornar `BLOCKED`.
