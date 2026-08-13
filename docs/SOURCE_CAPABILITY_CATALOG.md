# Catálogo Canônico de Fontes e Capacidades

Versão: 1.0  
Data: 2026-08-13

Este documento define o contrato canônico para avaliação e catalogação de APIs, datasets, repositórios e demais fontes estruturadas do AgroLog MT. Ele complementa `docs/ARCHITECTURE.md` e `docs/DATA_GOVERNANCE.md`; não substitui manifests de fontes que entrarem em implementação.

## Princípio

Não catalogar apenas uma instituição ou plataforma. A unidade útil é a capacidade concreta:

**Fonte → produto/dataset → endpoint/recurso → variável → pergunta respondida → indicador derivável.**

Toda descoberta deve ser analisada antes de ser apresentada como recomendação ativa. Fonte inadequada, redundante sem ganho, juridicamente problemática, instável ou tecnicamente frágil não deve ser promovida apenas porque está disponível.

## Arquivo canônico

O inventário versionado nesta fase é `catalog/source_capabilities.csv`.

Cada linha representa uma capacidade específica. Não criar um segundo catálogo concorrente por plataforma, API ou tema. Quando uma fonte tiver muitas capacidades, adicionar linhas ao mesmo contrato.

## Campos obrigatórios

- `capability_id`: identificador estável da capacidade;
- `fonte`;
- `produto_dataset`;
- `endpoint_recurso`;
- `variavel`;
- `descricao`;
- `unidade`;
- `geografia`;
- `granularidade_temporal`;
- `frequencia_atualizacao`;
- `historico`;
- `autenticacao`;
- `limites`;
- `licenca_termos`;
- `uso_comercial`;
- `pergunta_respondida`;
- `indicador_derivavel`;
- `classificacao_evidencia`;
- `qualidade_fonte`;
- `status`;
- `prioridade`;
- `destino_bigquery`;
- `ultima_verificacao`;
- `issue_referencia`;
- `observacoes`.

Campos desconhecidos não devem ser inventados. Usar `PENDENTE_VALIDACAO` quando a informação ainda precisa ser confirmada na documentação original. `ultima_verificacao` deve ficar vazia até uma verificação efetiva da fonte/documentação original.

## Status permitidos

- `RADAR`
- `VALIDANDO`
- `POC_APROVADA`
- `INTEGRACAO_PLANEJADA`
- `INTEGRADA`
- `RESTRITA`
- `SUPERSEDED`
- `DESCARTADA`

### Regra de promoção

`RADAR` → descoberta ainda não homologada.  
`VALIDANDO` → documentação original, acesso, termos, estabilidade e utilidade em análise.  
`POC_APROVADA` → PoC executada e evidenciada.  
`INTEGRACAO_PLANEJADA` → PoC aprovada e implementação priorizada por Issue.  
`INTEGRADA` → pipeline real validado conforme critérios de produção do projeto.

Uma Issue que diga “aprovada para PoC” não autoriza marcar `POC_APROVADA` antes da execução e validação da PoC.

## Evidência

Usar as classes canônicas de `docs/DATA_GOVERNANCE.md`: `observado`, `cadastro`, `calculo`, `inferencia`, `estimativa`, `projecao`, `sinal_indireto` e `negociado_autorizado`.

A qualidade da fonte é separada da classificação da evidência e da confiança de uma afirmação derivada.

## Destino

- séries e dados estruturados homologados → BigQuery;
- documentos-fonte → Drive/armazenamento documental;
- código, contratos e manifests → GitHub;
- conhecimento, metodologia, relações e sínteses → Obsidian.

`destino_bigquery` é planejamento de contrato, não autorização para criar tabela antecipadamente. Datasets e tabelas continuam sendo criados sob demanda.

## OpenAlex e Crossref

OpenAlex e Crossref podem permanecer no `RADAR` como mecanismos de descoberta e verificação bibliográfica. Seus metadados não substituem a leitura, avaliação e citação da publicação original.

## Governança de mudança

Toda nova capacidade, promoção de status ou descarte relevante deve ser rastreável a uma Issue. Integração de fonte exige Issue/PR próprios e não deve ser implementada apenas por constar neste catálogo.
