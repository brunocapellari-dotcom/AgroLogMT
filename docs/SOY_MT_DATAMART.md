# Data Mart Soja MT v0.1 — Contrato

## Propósito

O Data Mart Soja MT é a camada analítica integrada do primeiro ciclo N6. Ele não cria uma segunda fonte de verdade: consome tabelas canônicas do BigQuery e preserva o vintage de cada informação.

## Grão analítico

O mart deve suportar pelo menos três grãos, sem misturá-los silenciosamente:

- **município × data/vintage × safra** para produção, clima e armazenagem;
- **rota/origem-destino × período × produto** para logística;
- **mercado/porto × data × produto/contrato** para preços, prêmio, line-up e exportação.

## Blocos de entrada

| Bloco | Fontes iniciais | Variáveis principais | Status do contrato |
|---|---|---|---|
| Produção | CONAB, IMEA, IBGE | área, produção, produtividade, plantio, colheita | definido |
| Armazenagem | CONAB | capacidade, unidades, localização | implementação iniciada |
| Comercialização | IMEA | percentual vendido, preço, vintage | definido |
| Mercado | CME/CBOT, BCB, IMEA/CEPEA, prêmio autorizado | futuro, câmbio, físico, prêmio, basis | definido |
| Comércio exterior | Comex Stat | toneladas, FOB, destino, UF, via, URF | definido |
| Logística | MDF-e/ANTT, IMEA, DNIT, ferrovias/hidrovias | fluxo, TKU, oferta de frete, corredor | definido |
| Portos | ANTAQ, line-ups oficiais | realizado, programado, escalas, terminais | definido |
| Clima | estações, NOAA/NASA/ERA5 conforme classificação | chuva, temperatura, ET0, solo | definido |
| Hidrologia | ANA | nível, vazão, estação | definido |
| Indústria | ABIOVE/ANP/UNEM e fontes autorizadas | esmagamento, etanol, demanda | definido |

## Chaves obrigatórias

Quando aplicável, cada fato precisa preservar `product_id`, `safra`, `geo_id`, `data_referencia`, `data_publicacao`, `data_coleta`, `competencia`, `source_id`, `evidence_class`, `source_hash` e versão de metodologia.

## Regras

1. Não converter URF automaticamente em porto físico.
2. Não chamar oferta de frete de frete pago.
3. Não misturar line-up programado com movimentação realizada.
4. Não interpolar séries anuais apenas para obter frequência mensal.
5. Não usar revisão publicada depois da data de corte em backtest histórico.
6. Não unir geografia por nome livre quando código canônico estiver disponível.
7. Toda métrica derivada deve apontar para `metric_id` em `contracts/canonical_metrics.csv`.

## Saídas mínimas do mart

- balanço de soja por safra/vintage;
- disponibilidade física estimada;
- comercialização remanescente;
- paridade de exportação por corredor;
- pressão logística por corredor;
- capacidade de armazenagem e razão capacidade/produção;
- exportação observada e previsão 30/90 dias;
- risco agroclimático e risco hidroviário;
- explicação decomponível de preço físico.

## Gate para materialização

A view/tabela integrada só deve ser materializada depois de os datasets de origem necessários existirem e terem passado QA. Até lá este arquivo é o contrato canônico do mart, evitando criar tabelas vazias ou SQL fictício contra fontes ainda não implantadas.
