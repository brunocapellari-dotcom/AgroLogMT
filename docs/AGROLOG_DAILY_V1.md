# AgroLog Daily v1

Status: `FROZEN_V1 / A4_SUPERVISED / DATA_GATED`

## Fluxo
1. coleta das fontes e preservação RAW;
2. validação de freshness e datas de referência/publicação/coleta;
3. classificação da evidência;
4. execução dos modelos elegíveis;
5. recuperação de contexto no Segundo Cérebro;
6. boletim meteorológico da manhã;
7. radar intradiário somente para mudanças materiais;
8. fechamento de mercado somente após as fontes fecharem;
9. auditoria factual e de provenance;
10. registro das métricas operacionais.

## Produtos
- Relatório Meteorológico da Manhã;
- Notícia Rápida quando houver fato novo;
- Fechamento Diário de Mercado em dia útil após fechamento;
- insumos para Conjuntura e dashboards.

## Gate P0 do ciclo integral live
- PTAX primária do BCB com freshness válido;
- ANA HidroWeb nas estações do M04 com qualidade e timestamps;
- parcial semanal MDIC/SECEX quando houver release aplicável. O consolidado mensal não substitui o semanal.

## Modelos
M01: no v0.1, usar vetor de componentes, dominante, confiança e campos ausentes. Não fixar pesos antes de backtest.

M04: score numérico depende de dados hidrológicos, tendência, antecedente de bacia, previsão e evidência operacional suficientes. Condição hidrológica não equivale automaticamente a restrição de navegação.

M07: estádio temporalmente correto é obrigatório. Pós-colheita, pousio ou área ainda não plantada devem gerar `NO_ACTIVE_CROP_EXPOSURE`, não um risco agronômico artificial.

## Métricas
Persistir em `agrolog_ops.daily_product_runs` e consolidar em `v_daily_product_kpis` e `v_daily_operational_gate`:
- runtime;
- passos automáticos e intervenções humanas;
- minutos manuais;
- número de fontes, source lag e erros;
- claims materiais e claims sem suporte;
- correções;
- falsos positivos e falsos negativos;
- custos observados/estimados identificados;
- valor confirmado pelo cliente, quando existir.

## Regras
- dado ausente não vira zero;
- dado antigo não recebe data nova;
- previsão não vira observado;
- programação não vira realizado;
- valor para o cliente só é registrado como confirmado quando houver confirmação real.

O Daily v1 pode operar em A4 supervisionado com gaps explícitos. O marco técnico seguinte é `CLIENT_DAY_ZERO_P0_GAPS`; A5 é uma avaliação separada.
