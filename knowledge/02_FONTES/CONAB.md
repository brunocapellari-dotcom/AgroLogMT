---
tipo: fonte
fonte: CONAB
status: estruturada
prioridade: P0
ultima_revisao: 2026-08-12
---

# CONAB

Domínios principais: safra, plantio/colheita, oferta e demanda, preços, armazenagem, estoques, custos e logística.

## Ativos conhecidos

- `AgroLog_Fonte_CONAB.xlsx`
- `ArmazensCadastrados.txt`
- `PrecosMensalMunicipio.txt`
- `CONAB_Plantio_Colheita_Historico.xlsx`
- pacotes de bases estruturadas, mercado, produção, monitoramento, logística e geoespacial no Drive.

## BigQuery

- `logistica.armazens`
- `agro.safra`
- `agro.progresso_safra`
- `mercado.precos_fisicos`

## Pipeline prioritário

[[Pipeline - CONAB Armazens]]

Arquivo oficial → raw/GCS → staging → DQ → snapshot/diff → MERGE → BigQuery → views → indicadores.

## Regras

- ausência em snapshot atual não significa exclusão;
- preservar hash, arquivo e vintage;
- XLSX mais estruturado pode ter prioridade sobre PDF quando ambos representam a mesma publicação, mantendo rastreabilidade;
- valores históricos/revisados devem preservar versões quando materialmente relevantes.
