# Motor próprio de rotas — OSM/Valhalla/OSRM (Issue #18)

Primeiro passo, estritamente documental, da avaliação pedida pela Issue
#18: "Avaliar e implantar um motor próprio para distância, tempo teórico
e matrizes origem-destino rodoviárias, reduzindo dependência de APIs
comerciais." **Nenhum container subiu, nenhum benchmark rodou, nenhuma
decisão de infraestrutura foi tomada nesta avaliação** — este documento
cobre apenas licenciamento e requisitos de disco/memória, para permitir
uma decisão humana de escopo (PoC completo com Valhalla/OSRM reais vs.
avaliação documental reduzida) sem comprometer infraestrutura antes
dessa decisão. Execuções anteriores da janela autônoma (3ª a 7ª)
identificaram repetidamente esta issue como próximo item de Fase D sem
risco de duplicação, mas adiaram por depender de decisão de escopo sobre
PoC pesado — este documento é o primeiro incremento sem essa decisão,
conforme registrado em `.agrolog48h_state.md`.

## Critérios de aceite da Issue #18 — status após este documento

- [x] licença/atribuição documentadas (esta seção, abaixo)
- [~] custo de infraestrutura estimado — estimativa inicial de disco por
  requisitos de dados de origem (OSM) e por relatos de terceiros para
  memória; **não é medição própria do AgroLog MT** (ver seção de
  classificação de evidência)
- [ ] benchmark Valhalla x OSRM em rotas do AgroLog — não iniciado
- [ ] qualidade de rota validada em corredores prioritários — não iniciado
- [ ] matriz O/D testada em lote — não iniciado
- [ ] limites de atualização do mapa definidos — não iniciado
- [ ] API interna somente leitura projetada para o AgroLog Gateway — não
  iniciado

## Licença e atribuição do OpenStreetMap (ODbL)

Fonte: [OSM Foundation — Licence/Attribution
Guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines) e
[Licence and Legal
FAQ](https://osmfoundation.org/wiki/Licence/Licence_and_Legal_FAQ).
Classificação: **observado** (texto da licença e da própria fundação
OSM, não interpretação própria de terceiro).

- O OpenStreetMap é distribuído sob **ODbL (Open Database License)**. Uso
  comercial é permitido explicitamente ("for any purpose you like,
  including personal, community, educational, commercial or
  governmental").
- "Produced Works" (obras derivadas que não são um banco de dados —
  ex.: um mapa renderizado, uma rota calculada, uma instrução de
  navegação) precisam deixar claro que os dados vêm do OpenStreetMap sob
  ODbL, com link para `www.openstreetmap.org/copyright` (ou
  `www.opendatacommons.org/licenses/odbl`). Para o AgroLog Gateway, isso
  significa: qualquer resposta de API ou tela que exponha rota/distância
  calculada a partir de dados OSM precisa de atribuição visível "©
  OpenStreetMap contributors" com o link acima.
- Instruções de rota geradas por um motor de roteamento **não** precisam
  manter atribuição presa a cada instrução individual, desde que não
  formem, elas mesmas, um "Derivative Database" redistribuído
  publicamente.
- **Share-alike só se aplica a distribuição/uso público de uma
  "Derivative Database"**: se o AgroLog MT apenas consumir OSM
  internamente para calcular rotas (uso operacional, não redistribuição
  do próprio extrato de dados), não há obrigação de publicar extração
  derivada sob ODbL. Isso muda se, no futuro, o AgroLog publicar/vender
  um dataset derivado substancial do grafo OSM (não é o caso do Gateway
  read-only atual).
- Ação necessária antes de qualquer exposição pública de rota calculada:
  adicionar atribuição "© OpenStreetMap contributors" (ODbL) na
  documentação de resposta do endpoint correspondente do AgroLog
  Gateway, quando esse endpoint existir.

## Requisitos de disco e memória — Valhalla vs. OSRM

Classificação: **inferido/estimado** a partir de relatos públicos de
terceiros (documentação oficial e comparativos independentes) — não é
medição própria do AgroLog MT nesta avaliação. Números variam por
extrato geográfico, perfil de veículo e versão do software; tratar como
ordem de grandeza para planejamento, não como capacidade contratada.

| | Valhalla | OSRM |
|---|---|---|
| Onde fica o grafo em tempo de resposta | Em tiles no disco, carregados sob demanda | Memory-mapped a partir de arquivos `.osrm` pré-processados |
| RAM em produção (extrato regional, não planeta) | Referenciado como confortável em 4–8 GB para a maioria dos perfis de tráfego | Depende diretamente do tamanho do `.osrm`; tende a exigir mais RAM que o Valhalla para o mesmo extrato, pois os dados pré-computados residem em memória |
| Disco (grafo processado) | Da ordem de dezenas de GB para uma região (ex.: tiles da América do Norte citados na faixa de 15–20 GB); planeta inteiro da ordem de 100 GB | Menor pegada em disco que o conjunto de tiles do Valhalla para a mesma área, mas o custo se desloca para RAM |
| Velocidade de resposta | Calcula a rota por request sobre o grafo pré-processado; desempenho precisa de benchmark no recorte e workload do AgroLog | Calcula a rota por request sobre o grafo pré-processado com CH ou MLD; desempenho e consumo de RAM precisam de benchmark no mesmo recorte e workload |
| Trade-off resumido | Favorece ambiente com RAM limitada | Favorece resposta mais rápida quando há RAM disponível |

Fontes: [Valhalla — GitHub](https://github.com/valhalla/valhalla),
[Valhalla Docs](https://valhalla.github.io/valhalla/), [GraphHopper vs
OSRM vs Valhalla — Pi Stack,
2026](https://www.pistack.xyz/posts/2026-04-25-graphhopper-vs-osrm-vs-valhalla-self-hosted-routing-engines-guide-2026/),
[OSRM vs Valhalla vs GraphHopper — SumGuy's
Ramblings](https://sumguy.com/osrm-vs-valhalla-vs-graphhopper/).

## Tamanho do extrato OSM de origem (Brasil)

Classificação: **observado** (tamanho de arquivo no servidor de download
consultado nesta avaliação).

- `brazil-latest.osm.pbf` (Geofabrik, extrato de todo o Brasil,
  atualizado continuamente): **1,9 GB** em 31/07/2026.
- Geofabrik não publica um extrato isolado por estado para o Brasil;
  divide o país em 5 macrorregiões. As publicadas com tamanho
  confirmado nesta consulta: Nordeste 410 MB, Norte 150 MB, Sul 395 MB,
  Sudeste 811 MB. **Não observado nesta avaliação**: tamanho do extrato
  Centro-Oeste (região que contém Mato Grosso) — não apareceu nos
  resultados desta consulta; precisa confirmação direta em
  `download.geofabrik.de/south-america/brazil.html` antes de qualquer
  dimensionamento de infraestrutura.
- Esses tamanhos são o `.osm.pbf` de entrada, não o grafo já processado
  por Valhalla/OSRM — o grafo processado é tipicamente maior que o
  `.pbf` de origem (ver tabela acima); não há, nesta avaliação, medição
  própria do fator de expansão para um extrato do Brasil especificamente.

## Lacunas explícitas (não decididas nesta avaliação)

1. Escopo do PoC: rodar Valhalla e OSRM de fato (com extrato real do
   Centro-Oeste/MT) vs. permanecer só documental por mais tempo —
   decisão de escopo pendente do usuário, como nas execuções 3–7.
2. Benchmark de qualidade de rota nos corredores prioritários do AgroLog
   (escoamento de soja/milho MT) não existe ainda; não pode ser
   estimado sem rodar os dois motores.
3. Custo de infraestrutura aqui é sobre disco/memória do software de
   roteamento isoladamente — não inclui custo de Cloud Run/Compute
   Engine, egress, nem frequência de reprocessamento do grafo ao
   atualizar o extrato OSM.
4. Política de atualização do mapa (a cada quanto tempo reprocessar,
   como versionar) não foi definida.

## Próximo passo recomendável

Quando houver decisão de escopo: (a) se PoC completo aprovado, iniciar
por um extrato pequeno (Centro-Oeste ou recorte de MT via `osmium
extract`) em ambiente descartável, não em infraestrutura de produção;
(b) se avaliação documental reduzida for suficiente por ora, este
documento cobre a lacuna de licenciamento — restam benchmark, matriz O/D
e API interna como trabalho futuro explícito, não implícito.
