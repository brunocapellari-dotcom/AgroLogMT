# Governança de Dados

## Classificação obrigatória da evidência

Cada indicador, registro derivado ou afirmação material deve ser classificado como uma das categorias abaixo:

1. **observado** — valor obtido diretamente de medição, operação ou publicação que representa o fenômeno observado;
2. **cadastro** — informação declaratória/cadastral da fonte, como capacidade registrada, estabelecimento, autorização ou atributo institucional;
3. **calculo** — resultado determinístico de fórmula aplicada a entradas identificadas, sem hipótese estatística adicional;
4. **inferencia** — conclusão derivada de um ou mais dados/evidências, com mecanismo e premissas explícitos;
5. **estimativa** — valor aproximado por modelo, coeficiente, interpolação ou hipótese explícita;
6. **projecao** — valor referente a período futuro ou cenário prospectivo;
7. **sinal_indireto** — proxy que sugere atividade/condição sem medir diretamente o fenômeno de interesse;
8. **negociado_autorizado** — informação efetivamente negociada ou operacional obtida de fonte interna/autorizada.

A classificação descreve a natureza da evidência, não a reputação da fonte.

## Qualidade da fonte e confiança da afirmação

Manter dimensões separadas:

- **qualidade da fonte**: autoridade, metodologia, rastreabilidade, cobertura, consistência e atualidade da origem;
- **confiança da afirmação**: grau de suporte da conclusão específica considerando evidência, premissas, conflitos e limitações.

Uma fonte de alta qualidade pode sustentar uma inferência de baixa confiança se o vínculo causal for fraco. Uma afirmação não deve herdar confiança automaticamente da reputação da fonte.

## Campos temporais mínimos

As tabelas analíticas e artefatos de conhecimento devem preservar, quando aplicável:

- `data_referencia`: data a que o dado ou fato se refere;
- `data_publicacao`: data em que a fonte publicou o conteúdo;
- `data_coleta`: data/hora em que o AgroLog MT coletou ou registrou o conteúdo;
- `competencia`: período lógico do indicador (safra, mês, semana, ano etc.);
- `data_corte_estudo`: limite de informação disponível usado em estudo retrospectivo, backtest ou comparação histórica para impedir look-ahead bias.

## Regras

- Não apresentar estimativa, projeção, inferência ou sinal indireto como observado.
- Diferenciar capacidade cadastrada de produção/uso efetivamente observado.
- Não afirmar frete real pago sem fonte autorizada.
- Não afirmar disponibilidade real de caminhões sem evidência operacional adequada.
- Não atribuir volume a trading individual sem fonte que sustente essa granularidade.
- Preservar origem da informação e, quando uma fonte agregadora for usada, registrar também a fonte primária quando identificável.
- Snapshots históricos devem ser mantidos quando a fonte puder alterar ou remover dados retroativos.
- Publicações recorrentes usadas no Segundo Cérebro devem ser processadas por diferença quando a responsabilidade for manter estado atual.

## Qualidade mínima por carga

Toda carga deve produzir evidências de:

- quantidade de registros lidos;
- quantidade de registros aceitos;
- quantidade de registros rejeitados;
- duplicidades encontradas/removidas;
- período coberto;
- timestamp da execução;
- versão do coletor;
- resultado final da carga.
