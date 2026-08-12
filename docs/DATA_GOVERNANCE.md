# Governança de Dados

## Classificação obrigatória da evidência

Cada indicador, registro derivado ou conclusão deve ser classificado como uma das categorias abaixo:

1. **observado** — valor obtido diretamente de fonte oficial, contratada ou autorizada;
2. **inferido** — conclusão derivada de um ou mais dados observados;
3. **estimado** — valor calculado por modelo, coeficiente, aproximação ou hipótese explícita;
4. **negociado_autorizado** — informação efetivamente negociada ou operacional obtida de fonte interna/autorizada.

## Campos temporais mínimos

As tabelas analíticas devem preservar, quando aplicável:

- `data_referencia`: data a que o dado se refere;
- `data_publicacao`: data em que a fonte publicou o dado;
- `data_coleta`: data/hora em que o AgroLog MT coletou o dado;
- `competencia`: período lógico do indicador (safra, mês, semana, ano etc.).

## Regras

- Não apresentar estimativa como dado observado.
- Não afirmar frete real pago sem fonte autorizada.
- Não afirmar disponibilidade real de caminhões sem evidência operacional adequada.
- Não atribuir volume a trading individual sem fonte que sustente essa granularidade.
- Preservar origem da informação e, quando uma fonte agregadora for usada, registrar também a fonte primária quando identificável.
- Snapshots históricos devem ser mantidos quando a fonte puder alterar ou remover dados retroativos.

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
