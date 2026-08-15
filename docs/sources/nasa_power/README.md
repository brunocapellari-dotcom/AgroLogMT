# NASA POWER — avaliação (Issue #15, subconjunto sem chave)

Avaliação da API [NASA POWER](https://power.larc.nasa.gov/) (Prediction Of
Worldwide Energy Resources), endpoint `temporal/daily/point`, conforme
pedido pela Issue #15: "documentação e termos revisados, PoC por fonte,
schema temporal/geográfico definido, observado/modelado/sinal
classificados separadamente" antes de qualquer carga no BigQuery.
**Nenhum dado foi carregado no BigQuery nesta avaliação.**

A Issue #15 lista seis fontes candidatas: NASA POWER, ERA5/AgERA5 via
Copernicus, ANA HidroWebService, NASA FIRMS, NOAA/USGS Water e USACE Corps
Locks/Rivergages. Esta avaliação implementa **apenas o NASA POWER**, a
única testada nesta sessão que respondeu com dados reais, cobertura
global (incluindo o MT) e sem exigir registro de chave — consistente com
a regra de Fase D de priorizar fontes "que não exijam compra/chave nova".
As demais ficam registradas abaixo com o resultado do teste direto.

## Plataforma e acesso

- Domínio: `power.larc.nasa.gov`, operado pela NASA (Langley Research
  Center).
- Endpoint avaliado: `GET /api/temporal/daily/point` — série diária por
  ponto (latitude/longitude), parâmetros via query string
  (`parameters`, `community`, `longitude`, `latitude`, `start`, `end`,
  `format`). Versão da API confirmada na resposta: `v2.9.6`.
- Sem autenticação: nenhuma chave/token é exigida para os volumes
  consultados nesta avaliação.
- Erros de validação (`HTTP 422`) usam dois formatos distintos observados
  nesta avaliação: `{"detail": [...]}` (estilo pydantic, para
  latitude/longitude/community fora de faixa) e
  `{"header": ..., "messages": [...]}` (parâmetro climático desconhecido).
  `nasa_power.client._extract_error_message` trata os dois.
- Conectividade real confirmada nesta avaliação: chamadas diretas ao
  endpoint acima (Python `urllib.request`) e depois via testes
  automatizados em `nasa_power/tests/test_points_live.py`.

## Comunidades e parâmetros avaliados

A API oferece três "comunidades" (`ag`, `sb`, `re`) que só mudam o
conjunto padrão de parâmetros sugeridos na documentação, não o acesso aos
dados — qualquer parâmetro pode ser pedido em qualquer comunidade. Esta
avaliação usa `ag` (agroclimatology), a relevante para o AgroLog.

Parâmetros confirmados por chamada real (comunidade `ag`, ponto em
Sorriso/MT, `2026-01-01` a `2026-01-05`):

| Parâmetro | Unidade | Descrição | No escopo desta PoC (`CORE_PARAMETERS`) |
|---|---|---|---|
| `T2M` | `C` | Temperatura média a 2m | sim |
| `T2M_MAX` | `C` | Temperatura máxima a 2m | sim |
| `T2M_MIN` | `C` | Temperatura mínima a 2m | sim |
| `PRECTOTCORR` | `mm/day` | Precipitação corrigida | sim |
| `RH2M` | `%` | Umidade relativa a 2m | sim |
| `ALLSKY_SFC_SW_DWN` | `MJ/m²/day` | Radiação solar incidente | testado, fora do escopo padrão desta PoC |
| `WS2M` | `m/s` | Velocidade do vento a 2m | testado, fora do escopo padrão desta PoC |

`ALLSKY_SFC_SW_DWN` e `WS2M` respondem normalmente (mesma chamada, mesmo
formato) mas ficam fora de `CORE_PARAMETERS` para manter o escopo desta
PoC pequeno; qualquer parâmetro válido da API pode ser passado a
`daily_point(parameters=...)` sem mudança de código.

### Amostra real — Sorriso/MT, 2026-01-01 a 2026-01-05

```json
{
  "T2M": {"20260101": 27.04, "20260102": 28.01, "20260103": 26.99, "20260104": 24.49, "20260105": 23.77},
  "PRECTOTCORR": {"20260101": 2.24, "20260102": 1.47, "20260103": 9.95, "20260104": 7.61, "20260105": 1.59},
  "RH2M": {"20260101": 76.3, "20260102": 73.46, "20260103": 80.41, "20260104": 92.39, "20260105": 89.81}
}
```

Confirmado também para Rondonópolis/MT (`-16.4708, -54.6356`), com valores
igualmente plausíveis (T2M ~28-29°C, PRECTOTCORR 0.8-6.4 mm/day).

## Pontos de referência avaliados

Ver `nasa_power/points.py` (`KNOWN_POINTS`). Dois municípios do MT,
seguindo o mesmo padrão de "coordenadas aproximadas da sede municipal"
(resolução nativa da API é ~0.5°, ~50 km — precisão de poucos km no ponto
de consulta não muda o pixel de origem retornado):

| Chave | Município/UF | Relevância MT |
|---|---|---|
| `sorriso_mt` | Sorriso/MT | direta — um dos maiores produtores de soja/milho do Brasil |
| `rondonopolis_mt` | Rondonópolis/MT | direta — polo logístico/esmagamento de soja do sul do MT |

## Classificação de evidência

Seguindo `docs/DATA_GOVERNANCE.md` (categorias: observado, inferido,
estimado, negociado_autorizado):

- **Estimado**, não observado. O cabeçalho da própria resposta
  (`header.sources`) declara `["SYN1DEG", "MERRA2", "POWER"]` — dado de
  satélite (SYN1DEG) combinado com reanálise numérica (MERRA-2, modelo de
  assimilação de dados da NASA/GMAO), não medição direta de estação
  meteorológica terrestre. Isso corresponde exatamente à definição de
  "estimado" em `docs/DATA_GOVERNANCE.md` ("valor calculado por modelo,
  coeficiente, aproximação ou hipótese explícita").
- Qualquer uso futuro (Gateway, BigQuery, Obsidian) deve rotular esse
  dado explicitamente como estimativa modelada, nunca como leitura de
  estação — `test_sources_confirm_modeled_reanalysis_not_ground_station`
  existe para pegar regressão se a API mudar as fontes declaradas.
- `fill_value` (`-999.0`) é tratado como dado ausente (`None`), nunca como
  leitura real — sem essa normalização, um buraco de cobertura viraria
  silenciosamente "temperatura de -999°C".

## Qualidade e limitações observadas

- Sem chave/token obrigatório.
- `time_standard` declarado pela API é `LST` (hora solar local do ponto),
  não UTC nem UTC-3 — precisa de normalização explícita antes de qualquer
  comparação com séries que já usam `data_referencia` em UTC-3 implícito
  (CONAB, IMEA), mesma limitação já documentada para AgTransport/CFTC.
- Resolução espacial nativa ~0.5° (~50 km) — um único ponto de consulta
  representa uma área regional, não o microclima exato de uma fazenda ou
  armazém específico.
- Cobertura temporal: dado histórico via MERRA-2 desde 1981, com
  atualização diária (delay de poucos dias para consolidação da
  reanálise); não confirmado nesta avaliação o delay exato de publicação
  para o dia mais recente — próximo passo antes de decidir cadência de
  coleta.
- Nenhuma indicação de descontinuação nesta avaliação.

## Termos de uso

Dado público da NASA (agência do governo federal dos EUA), sem chave de
API obrigatória para os endpoints de leitura usados. A documentação
oficial da NASA POWER recomenda atribuição em publicações derivadas:
**"NASA/POWER"** — a ser mantida em qualquer uso derivado. Licença
declarada como dado aberto do governo federal dos EUA (mesmo regime já
registrado para CFTC/AgTransport/CKAN nas avaliações anteriores).

## Fontes da Issue #15 fora do escopo desta avaliação

Testadas diretamente nesta sessão (chamada HTTP real, sem key quando
possível, para confirmar o tipo de bloqueio antes de registrar):

| Fonte | Endpoint testado | Resultado | Observação |
|---|---|---|---|
| ERA5/AgERA5 (Copernicus CDS) | `GET https://cds.climate.copernicus.eu/api` | `HTTP 202`, mensagem de boas-vindas | O endpoint raiz responde sem chave, mas a documentação oficial do CDS exige token pessoal (UID + API key, registro gratuito) para qualquer requisição de dados real — não confirmado nesta sessão porque exigiria criar conta. Registrado como blocker de credencial. |
| ANA HidroWebService (série de cotas, `hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieCotas/v1`) | `GET .../HidroinfoanaSerieCotas/v1?Código da Estação=...` | `HTTP 404` | Caminho exato do endpoint de série não confirmado nesta sessão (a API mais nova da ANA trocou de rota mais de uma vez); **não é bloqueio de credencial**, é pendência de descoberta de endpoint. |
| ANA HidroWebService (inventário legado, `telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroInventario`) | `GET .../HidroInventario?nmEstado=MATO GROSSO` | `HTTP 200`, XML com estações do MT | Responde sem chave e cobre inventário de estações do MT — caminho mais promissor para uma futura avaliação de hidrologia MT-específica, mas fica fora desta rodada (o PoC desta avaliação já está coberto pelo NASA POWER; retomar quando houver capacidade para mapear o endpoint de série correspondente). |
| NASA FIRMS (focos de calor) | `GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/DEMO_KEY/...` | `HTTP 400` — `"Invalid MAP_KEY"` | `DEMO_KEY` não é aceito (diferente de outras APIs NASA); exige `MAP_KEY` pessoal via registro gratuito. Blocker de credencial. |
| NOAA/USGS Water (`waterservices.usgs.gov/nwis/iv`) | `GET .../nwis/iv/?sites=07010000&period=P1D` | `HTTP 200`, dados reais | Responde sem chave, mas é **especificamente território dos EUA** (rede de estações USGS) — sem cobertura no Brasil/MT, então sem relevância direta para o AgroLog apesar de tecnicamente acessível. Não implementado por falta de relevância geográfica, não por bloqueio técnico. |
| USACE Rivergages (Corps Locks) | `GET https://rivergages.mvr.usace.army.mil/watercontrol/webservices/rest/webserviceWaterML.cfc?method=RGWML` | `HTTP 200`, corpo de erro genérico (`"An error has occurred."`) | Formato de chamada usado nesta avaliação não é o correto (serviço ColdFusion legado com assinatura própria); também é território/rios dos EUA (Mississippi), sem relevância direta para o MT. Não aprofundado por baixa prioridade geográfica. |

## Código

`nasa_power/` — `build_client()` (cliente travado no host NASA POWER,
mesmo padrão de `cftc_cot.build_client`), `daily_point()` (validação de
entrada + normalização de `fill_value`) e registro dos pontos/parâmetros
avaliados (`KNOWN_POINTS`, `CORE_PARAMETERS`). Diferente de `cftc_cot`,
não há extração de conector genérico: NASA POWER é a única fonte do
projeto usando esta plataforma até agora, então um cliente próprio e
autocontido é suficiente — extrair um `nasa_connector/` compartilhado
antes de existir uma segunda fonte na mesma plataforma seria
generalização prematura.

## Próximos passos (não executados nesta avaliação)

1. Decidir schema de destino (dataset/tabela) no BigQuery seguindo o
   padrão `data_referencia`/`data_publicacao`/`data_coleta`/`competencia`
   usado pelas demais fontes — aqui `data_referencia` seria a data LST do
   ponto e `competencia` o mês/safra; `data_publicacao` precisa de
   confirmação do delay real de consolidação MERRA-2 (não medido nesta
   avaliação).
2. Confirmar o endpoint correto de série temporal do ANA HidroWebService
   (o inventário responde sem chave; a série ainda não foi localizada) e
   avaliar hidrologia MT-específica numa rodada futura.
3. Reavaliar ERA5/AgERA5 (Copernicus) e NASA FIRMS quando houver decisão
   humana sobre registro de chave/token pessoal.
4. Só considerar carga real no BigQuery depois de (1) e da revisão de DQ,
   seguindo o mesmo processo de piloto validado usado para CONAB Armazéns.
5. Exposição no AgroLog Gateway somente após homologação de DQ, conforme
   critério de aceite da Issue #15 — fora do escopo desta avaliação.
