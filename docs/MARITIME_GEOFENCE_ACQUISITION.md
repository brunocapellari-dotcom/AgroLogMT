# Maritime V1 — aquisição e validação de geofences

**Referência:** 2026-08-28  
**Status:** WORKING / DATA_GATED  
**Contrato de runtime:** `contracts/maritime_geofences.v1.json`  
**Manifesto de fontes:** `collector/config/maritime_geofence_sources.v1.json`

## 1. Princípio

A V1 não deve desenhar zonas operacionais por aproximação visual. A cadeia aceita é:

`fonte oficial -> extração rastreável -> candidato -> QA geométrico -> QA cartográfico/hidrográfico -> QA com AIS histórico -> revisão independente -> GEOFENCE_VALIDATED -> runtime`

A poligonal jurídica do porto organizado é uma **boundary administrativa/física de referência**. Ela não equivale automaticamente às zonas operacionais `APPROACH`, `ANCHORAGE` ou `BERTH` usadas pelo `PortZone`.

Bounding boxes de assinatura AIS também não são geofences.

## 2. Situação por porto

### 2.1 Santos

**Poligonal do porto organizado:** melhor caso de aquisição.

A Autoridade Portuária de Santos publica, para a poligonal vigente da Portaria GM-MPOR nº 5/2026:

- desenho em PDF;
- **arquivo vetorial KMZ**;
- ato normativo.

Fonte canônica de aquisição:
`https://www.portodesantos.com.br/oportunidades-de-negocios/planejamento-portuario/`

Confirmação federal da revisão 2026:
`https://www.gov.br/portos-e-aeroportos/pt-br/assuntos/noticias/2026/02/ministro-silvio-costa-filho-assina-portaria-que-revisa-a-ampliacao-da-poligonal-do-porto-de-santos`

**Próxima ação:** baixar o KMZ oficial, preservar o artefato RAW/hash, identificar CRS/datum, converter para GeoJSON apenas como derivado e confrontar com o desenho/Portaria antes da promoção.

**CHM para QA:** cartas 1711, 1712 e 1713.

### 2.2 Paranaguá

A Portaria nº 117, de 14/09/2021, define a área do Porto Organizado de Paranaguá por polígonos e lista seus vértices em SIRGAS 2000 nos Anexos 1 e 2.

Fonte legal:
`https://pesquisa.in.gov.br/imprensa/servlet/INPDFViewer?captchafield=firstAccess&data=15%2F09%2F2021&jornal=515&pagina=197`

Mapa da autoridade portuária:
`https://www.portosdoparana.pr.gov.br/Operacional/Pagina/Mapa-da-Poligonal`

PDZ aprovado, que reproduz a poligonal com base na Portaria 117/2021:
`https://www.gov.br/transportes/pt-br/assuntos/PIT/politica-e-planejamento/arquivos-pdz/pdz-paranagua-aprovado-pela-portaria-mpor-142-de-27-de-abril-de-2023.pdf`

**Próxima ação:** extrair os Anexos 1 e 2 preservando a separação dos polígonos; não concatenar todos os vértices em uma única ring.

**CHM para QA:** cartas 1820, 1821 e 1822.

### 2.3 Vila do Conde / Barcarena

O Decreto nº 8.394/2015 fornece 16 vértices oficiais da poligonal em SIRGAS 2000 e retorna ao primeiro ponto.

Fonte legal:
`https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/decreto/d8394.htm`

Autoridade portuária:
`https://www.cdp.com.br/companhia-docas-do-para/areas-de-porto-organizado/`

PDZ atual com coordenadas da poligonal:
`https://www.cdp.com.br/wp-content/uploads/2025/09/PDZ-RELATORIO-PORTO-DE-VILA-DO-CONDE-2025.pdf`

**QA preliminar executado:**

- 16 vértices convertidos de DMS para graus decimais;
- geometria simples preliminar: válida;
- área geodésica preliminar: aproximadamente **110,58 km²**;
- perímetro geodésico preliminar: aproximadamente **55,84 km**.

Isso autoriza criar uma **boundary candidata**, mas não uma geofence operacional.

**CHM para QA:** cartas 321 e 304.

### 2.4 Santarém

A poligonal vigente é associada à Portaria MINFRA nº 539/2022. Documento recente da CDP lista BRSTM-01 a BRSTM-21 em SIRGAS 2000.

Fonte da autoridade portuária:
`https://www.cdp.com.br/companhia-docas-do-para/areas-de-porto-organizado/`

Tabela recente de coordenadas:
`https://www.cdp.com.br/wp-content/uploads/2026/02/PGRS-Porto-de-Santarem-2025.pdf`

PDZ aprovado:
`https://www.gov.br/portos-e-aeroportos/pt-br/assuntos/transporte-aquaviario/planejamento-portuario/plano-de-desenvolvimento-e-zoneamento-pdz/arquivos-pdz/Texto_PDZ_Santarem_aprovado_portaria_mpor_644_2024.pdf`

**Bloqueio encontrado na QA:** ligar BRSTM-01 ... BRSTM-21 ingenuamente na ordem da tabela produz uma geometria auto-intersectante. Portanto a tabela não será promovida a polygon de runtime enquanto a estrutura/topologia do ato e do mapa oficial não for resolvida.

**Próxima ação:** recuperar a estrutura integral da Portaria 539/2022 e/ou um vetor oficial, identificar eventuais sub-rings/segmentos e comparar com a figura vigente do PDZ.

**CHM para QA:** carta 4020A como principal, complementada por 4020 e cartas regionais do acesso amazônico.

### 2.5 Itaqui

O Decreto federal de 25/07/2005 lista 10 vértices da poligonal do Porto Organizado do Itaqui.

Fonte legal:
`https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/dnn/dnn10590.htm`

Página EMAP:
`https://website.portodoitaqui.com.br/porto-itaqui/localizacao`

**Correção de fonte:** a página web da EMAP apresenta erro de transcrição no ponto `M F`, repetindo a latitude na coluna de longitude. O Decreto federal traz o valor legal: **44°21’47,0 W**.

**QA preliminar usando o Decreto:**

- 10 vértices convertidos para graus decimais;
- geometria simples preliminar: válida;
- área geodésica preliminar: aproximadamente **5,21 km²**;
- perímetro geodésico preliminar: aproximadamente **15,67 km**;
- a área é coerente com a ordem de grandeza de 5.100.000 m² informada pela EMAP.

**Bloqueio de atualidade:** ata do CAP/EMAP de março de 2025 registra a necessidade de renovação da poligonal e apresentação de proposta de nova poligonal. A busca de 28/08/2026 não identificou ato posterior conclusivo, mas ausência de resultado não prova vigência. Por isso a geometria de 2005 permanece `PENDING_CURRENCY_REVIEW`.

**CHM para QA:** cartas 410, 411, 412, 413 e 414.

## 3. Cartografia hidrográfica

O CHM informa que cartas raster estão disponíveis gratuitamente para download em NOAA-BSB e GeoTIFF. Elas representam, entre outros objetos, áreas de fundeio, canais, profundidades, perigos, auxílios à navegação e linha de costa.

Catálogo:
`https://www.marinha.mil.br/chm/dados-do-segnav-cartas-nauticas`

Downloads raster/GeoTIFF:
`https://www.marinha.mil.br/chm/dados-do-segnav/cartas-raster`

ENC vetorial não é download aberto do CHM; é distribuída por RENC/IC-ENC e está sujeita a licença/comercialização. Portanto ENC não será dependência da V1 enquanto raster + fontes portuárias oficiais forem suficientes.

## 4. Ordem de execução

1. Santos: obter e validar KMZ oficial 2026.
2. Vila do Conde: persistir boundary candidata derivada dos 16 vértices legais e executar QA visual com PDZ + carta 321.
3. Paranaguá: extrair corretamente os dois anexos/polígonos da Portaria 117/2021 e comparar ao PDZ.
4. Santarém: resolver topologia antes de qualquer GeoJSON operacional.
5. Itaqui: resolver vigência da proposta de nova poligonal antes de promover o candidato de 2005.
6. Depois das boundaries administrativas, adquirir zonas operacionais de fundeadouro/canal/berço por fonte portuária/CHM e validar com AIS histórico.
7. Somente após todos os gates gerar `AIS_PORT_ZONES_JSON` versionado e habilitar classificação de lifecycle.

## 5. Critério mínimo de promoção

- fonte primária oficial preservada;
- ato vigente confirmado;
- datum/CRS confirmado;
- ordem e agrupamento dos vértices confirmados;
- geometria válida e não degenerada;
- área plausível;
- comparação visual com mapa oficial;
- QA hidrográfico quando aplicável;
- QA com posições AIS históricas;
- `source_ref`, hash e versão persistidos;
- revisão independente concluída.
