# IMEA operacional → marts N6

- `indicadores diarios` + `indicadores semanais` → `mercado.imea_indicadores_operacionais`
- `frete` → `logistica.imea_frete_referencia`
- `semeadura` + `colheita` → `agro.imea_progresso_cultura`

Uso no Data Mart Soja MT:

- preço físico, CBOT, PTAX e prêmio: features de mercado, sempre com cutoff point-in-time;
- farelo/óleo: sinais de demanda/margem industrial, não equivalem a produção física;
- frete: referência publicada IMEA, não preço negociado individual;
- semeadura/colheita: progresso estimado por macrorregião e MT, preservando safra e publicação/coleta quando disponíveis.

A integração com `agro.imea_indicadores`, O&D, estimativas e custos do pacote v1.2 permanece complementar e obrigatória para cobertura histórica mais ampla.
