# Inteligencia geopolitica externa — contrato de consumo

## Decisao arquitetural

O monitor global de conflitos, denominado **Geopolitical Watch**, e um projeto independente do AgroLog MT.

O AgroLog MT nao deve hospedar o codigo, banco, credenciais, coletores, jobs, dashboards, scoring ou reports do Geopolitical Watch. O relacionamento entre os projetos e exclusivamente de **fornecedor externo de inteligencia -> consumidor**.

```text
Geopolitical Watch
  fontes -> coleta -> normalizacao -> corroboracao -> reports -> API/feed versionado
                                                      |
                                                      v
                                                AgroLog MT
                                      ingestao controlada -> validacao
                                      -> relevancia agro/logistica
                                      -> analise e produtos AgroLog
```

## Separacao obrigatoria

O Geopolitical Watch deve possuir, de forma independente:

- repositorio e ciclo de releases;
- armazenamento RAW e historico;
- banco analitico;
- credenciais e secrets;
- automacoes/schedulers;
- API/feed;
- dashboard e mapa;
- metodologia de clustering, corroboracao e prioridade;
- reports e historico editorial.

O AgroLog MT nao acessa diretamente o banco ou armazenamento interno do provedor. O consumo ocorre somente por interface publicada e versionada.

## Papel do AgroLog MT

Ao consumir o feed, o AgroLog:

1. preserva o identificador e a versao do provedor;
2. preserva as datas de referencia, publicacao e coleta informadas;
3. preserva o nivel de verificacao declarado pelo provedor;
4. nao transforma noticia em fato confirmado;
5. avalia de forma independente se o evento e material para agricultura, energia, fertilizantes, comercio, cambio ou logistica;
6. registra a propria inferencia de impacto separadamente da evidencia recebida;
7. promove o evento para boletins/relatorios AgroLog somente quando houver elo causal relevante.

## Contrato minimo do feed

Cada evento ou cluster consumivel deve expor, quando aplicavel:

- `schema_version`;
- `provider`;
- `provider_event_id`;
- `provider_cluster_id`;
- `title`;
- `event_type`;
- `data_referencia`;
- `data_publicacao`;
- `data_coleta`;
- `verification_level`;
- `corroboration_status`;
- `priority_score` e `priority_method_version` como dados de triagem do provedor;
- `country` / `region`;
- `latitude` / `longitude` somente quando sustentadas pelas fontes;
- `actors` somente quando sustentados pelas fontes;
- `fatalities_best` somente quando fornecido por fonte apropriada;
- `impact_domains` como tags do provedor, sem substituir a analise AgroLog;
- `sources` / evidencias institucionais;
- `news[]` com `title`, `publisher`, `published_at` e `url`;
- `generated_at` e `updated_at`;
- cursor ou mecanismo equivalente para sincronizacao incremental.

## Semantica de evidencia

O feed deve preservar a distincao entre:

- `research_coded` — evento codificado por base de pesquisa especializada;
- `curated_report` — relatorio institucional/humanitario curado;
- `osint_signal` — noticia ou outro sinal OSINT.

Para o AgroLog, o fato observado ao ingerir o feed e que **o provedor publicou aquele registro com aquela classificacao**. O AgroLog nao deve elevar automaticamente o conteudo subjacente para uma classe de certeza maior.

## Interface esperada

A implementacao externa deve oferecer ao menos capacidades equivalentes a:

- feed incremental de eventos/clusters desde um cursor ou timestamp;
- consulta de evento/cluster por identificador;
- report situacional mais recente;
- historico de reports;
- health/freshness da fonte;
- versao do schema e da metodologia.

Os nomes finais dos endpoints pertencem ao projeto Geopolitical Watch. O AgroLog deve depender do contrato, nao da implementacao interna.

## Idempotencia e atualizacoes

- IDs do provedor devem ser estaveis.
- O mesmo registro pode ser atualizado quando houver nova corroboracao ou revisao.
- O AgroLog deve fazer upsert pela chave do provedor + ID + schema/versionamento aplicavel.
- Reprocessamento nao pode multiplicar o mesmo evento.
- Revisoes devem preservar trilha temporal quando alterarem conclusoes relevantes.

## Promocao para produtos AgroLog

O evento so deve entrar nos produtos AgroLog quando existir relevancia causal material, por exemplo:

- conflito -> petroleo/diesel -> custo logistico;
- conflito/sancao -> gas, amonia, potassio ou fosfatados -> fertilizantes;
- Mar Vermelho/Suez/Hormuz -> shipping -> frete/tempo de viagem/seguro;
- Mar Negro -> graos/oleos vegetais -> oferta, preco e substituicao de fluxo;
- ataque/interrupcao -> porto, ferrovia, canal ou fronteira -> gargalo logistico.

Sem esse elo, o evento permanece apenas no Geopolitical Watch.
