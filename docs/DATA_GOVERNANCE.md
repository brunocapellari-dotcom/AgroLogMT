# Governança de Dados

## Classificação obrigatória da evidência

Cada indicador, registro derivado ou conclusão deve ser classificado como uma das categorias abaixo:

1. **observado** — valor obtido diretamente de fonte oficial, contratada ou autorizada;
2. **inferido** — conclusão derivada de um ou mais dados observados;
3. **estimado** — valor calculado por modelo, coeficiente, aproximação ou hipótese explícita;
4. **negociado_autorizado** — informação efetivamente negociada ou operacional obtida de fonte interna/autorizada.

Subtipos podem detalhar a natureza do registro sem criar uma nova classe de evidência. Exemplo: uma oferta de frete publicada em canal autorizado deve ser armazenada como `observado` com subtipo `oferta_frete_observada`.

## Campos temporais mínimos

As tabelas analíticas devem preservar, quando aplicável:

- `data_referencia`: data a que o dado se refere;
- `data_publicacao`: data em que a fonte publicou o dado;
- `data_coleta`: data/hora em que o AgroLog MT coletou o dado;
- `competencia`: período lógico do indicador (safra, mês, semana, ano etc.).

Para eventos de mensagens, `data_publicacao` corresponde ao timestamp observável de publicação/envio da mensagem quando esse timestamp for disponibilizado pela fonte. `data_coleta` corresponde ao momento em que o AgroLog recebeu/persistiu o evento.

## Regras gerais

- Não apresentar estimativa como dado observado.
- Não afirmar frete real pago sem fonte autorizada.
- Não afirmar disponibilidade real de caminhões sem evidência operacional adequada.
- Não atribuir volume a trading individual sem fonte que sustente essa granularidade.
- Preservar origem da informação e, quando uma fonte agregadora for usada, registrar também a fonte primária quando identificável.
- Snapshots históricos devem ser mantidos quando a fonte puder alterar ou remover dados retroativos.
- Toda transformação automatizada deve registrar método/versão suficiente para reprocessamento e auditoria.
- Quando houver extração por IA ou visão, preservar nível de confiança e encaminhar casos abaixo do limite definido para revisão em vez de inventar valores.

## Ofertas de frete observadas em canais autorizados

Uma mensagem que anuncie uma oportunidade de frete representa evidência de que **uma oferta foi observada**, não de que houve contratação, execução ou pagamento.

Regras obrigatórias:

- `classe_evidencia = observado`;
- `subtipo_evidencia = oferta_frete_observada`;
- `contratado = desconhecido` por padrão;
- `executado = desconhecido` por padrão;
- `valor_observado` deve manter a unidade anunciada quando identificável;
- se a unidade do valor não puder ser determinada com confiança, o registro deve ser sinalizado para revisão e não convertido silenciosamente;
- valores agregados como mediana por rota devem ser descritos como **valores de ofertas observadas na amostra**, nunca como frete efetivamente praticado no mercado;
- repostagens prováveis da mesma carga não devem ser contadas como novas oportunidades sem regra de deduplicação explícita;
- alterações de valor em provável mesma oportunidade devem ser preservadas como eventos observados e podem alimentar indicadores derivados de reoferta/reajuste.

## Privacidade e minimização de dados

Canais de comunicação podem conter nomes, telefones e outros dados pessoais. O princípio é coletar e persistir apenas o necessário para a finalidade legítima/autorizada do módulo.

- Preferir identificador pseudonimizado/hash do remetente quando a identidade nominal não for necessária.
- Não expor telefones, nomes pessoais ou identificadores diretos em dashboards analíticos por padrão.
- Mensagem/arquivo original deve permanecer em armazenamento RAW controlado quando sua retenção for necessária para auditoria; o GitHub nunca deve armazenar esse conteúdo real.
- Definir política de retenção, acesso e exclusão antes de colocar ingestão real em produção.
- Credenciais, tokens, sessões e cookies de integrações nunca devem ser versionados.
- Dados de grupos/canais só podem ser ingeridos quando o acesso e o uso forem autorizados e compatíveis com as regras aplicáveis ao projeto.

## Linhagem mínima

Todo registro que alimentar análise relevante deve conseguir apontar, diretamente ou por referência controlada, para:

- fonte/canal;
- identificador do evento/artefato ou hash equivalente;
- data de publicação;
- data de coleta;
- versão do coletor/parser;
- transformações aplicadas;
- confiança de extração/normalização quando houver IA;
- grupo de deduplicação quando aplicável.

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

Para ingestão contínua/eventos, as mesmas métricas devem ser agregadas por janela operacional definida (por exemplo hora ou dia) e acompanhadas de taxa de erro, atraso de ingestão e volume de mensagens descartadas como ruído.
