---
tipo: fonte
fonte: Comex Stat
status: estruturada
prioridade: P0
ultima_revisao: 2026-08-12
---

# Comex Stat

## Ativos conhecidos na Biblioteca

- `COMEX_Base_Tratada_AgroLog_MT360_Ajustada.xlsx`
- arquivos integrais CSV/CSV.GZ associados ao tratamento.

Cobertura tratada conhecida: 2020 a junho/2026, com recortes de Mato Grosso e agro Brasil.

## Metodologias

Manter separadas as granularidades/metodologias compatíveis com:

- NCM + UF + via + URF;
- município + SH4 quando permitido pela base.

## Regras

- URF não é automaticamente porto físico;
- UF é conceito estatístico da mercadoria, não necessariamente origem física imediata;
- não inferir trading, fazenda ou transportador;
- frete informado em importações não representa frete rodoviário doméstico.

## BigQuery

Destino lógico: `comex.exportacoes` e `comex.importacoes`.

Prioridade: localizar/materializar o CSV completo fora do GitHub e carregar por staging com schema explícito.
