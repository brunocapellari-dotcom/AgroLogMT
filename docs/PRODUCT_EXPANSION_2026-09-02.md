# Expansão de Produtos e Inteligência — AgroLog MT

Data: 02/09/2026
Status: consolidado após decisão do Owner

## Objetivo

Consolidar as rodadas de pesquisa em módulos que ampliam o AgroLog MT sem criar fontes concorrentes de verdade e sem interromper P0/P1. Este documento complementa `ARCHITECTURE.md` e `TECHNOLOGY_STACK.md`; qualquer runtime novo continua sujeito aos gates já definidos nesses documentos.

## Regra

Não reescrever coletor, contrato, Gateway ou modelo homologado apenas para padronizar ferramenta. Novos componentes entram somente quando resolvem caso real e passam por licença, segurança, testes e estratégia de saída.

O **AgroLog Fleet OS Brasil foi descontinuado** como projeto/subprojeto comercial nesta data por ausência de público validado. Ideias técnicas de frota permanecem apenas como referência e não devem consumir desenvolvimento até nova decisão objetiva.

## 1. Official Sources Intelligence

Criar uma camada de produção própria de notícias/análises baseada prioritariamente em fontes oficiais e primárias.

Fluxo:

`fonte oficial -> coleta -> fato/claim -> reconciliação -> dados AgroLog -> contexto histórico -> impacto -> redação própria -> auditoria`

Regras:

- portais, Instagram e canais terceiros não são fontes canônicas;
- quando um conteúdo secundário revelar informação útil, o Source Hunter deve localizar a origem primária;
- preservar `observado`, `estimado`, `projetado`, `inferido` e `sinal_qualitativo`;
- qualquer análise própria deve ser distinguida do fato original.

## 2. Live Data Fabric

Uma ingestão deve servir vários módulos. Priorizar feeds oficiais/abertos e reutilizáveis para clima, hidrologia, satélite, logística, portos, energia e mercado.

Camadas:

- ingestão/adapters;
- contracts/provenance;
- BigQuery histórico;
- event/live cache apenas quando latência exigir;
- derivação de sinais;
- AgroLog Gateway.

Não adicionar ClickHouse/Redpanda/RisingWave/PostGIS apenas por antecipação. Medir primeiro latência, volume e custo com a arquitetura atual.

## 3. GeoRisk / Live Earth Core

Módulo compartilhado do AgroLog, não empresa separada.

Fontes/capacidades prioritárias:

- GOES/INPE para evolução meteorológica rápida;
- INMET/CPTEC/CEMADEN/ANA;
- GPM/IMERG para precipitação espacial;
- FIRMS para focos de calor/incêndio;
- Sentinel/Copernicus;
- Landsat;
- Brazil Data Cube;
- dados geoespaciais oficiais brasileiros.

Produtos derivados internos:

- Fire Risk;
- Flood/Water Risk;
- Drought Risk;
- Route Weather Risk quando houver caso de uso;
- property/farm risk;
- vegetation/land/water change;
- infrastructure monitoring.

Código proprietário deve produzir `risk/event objects` com evidência, timestamp, geografia, confidence e natureza da inferência, em vez de apenas mostrar imagens.

## 4. Field Weather Station — observação meteorológica própria

Módulo de observação de campo compartilhado com o projeto **Maintenance & Field Intelligence** da Holding.

Objetivo: construir estações meteorológicas modulares de baixo custo, baseadas em ESP32 e sensores adequados, para preencher lacunas locais e produzir dados próprios observados sem substituir as redes oficiais.

### 4.1 Configuração mínima

- ESP32;
- temperatura;
- umidade relativa;
- pressão atmosférica;
- timestamp confiável;
- health/status do dispositivo;
- armazenamento temporário se perder conectividade.

### 4.2 Expansões

- pluviômetro de báscula;
- anemômetro;
- direção do vento;
- radiação/iluminação quando sensor adequado existir;
- umidade/temperatura do solo em nós específicos;
- energia solar + bateria;
- Wi-Fi no modelo simples;
- LoRa/gateway ou conectividade celular quando a distância exigir.

### 4.3 Software e componentes de referência

- ESPHome;
- OpenMQTTGateway;
- rtl_433 para integração de sensores RF compatíveis quando fizer sentido;
- MQTT;
- WeeWX como referência de software de estação;
- componentes LoRa avaliados nas rodadas anteriores.

Nenhum desses componentes define o contrato canônico. O AgroLog terá schema próprio para `field_weather_observation`, device registry, calibration metadata, source health e quality flags.

### 4.4 Governança científica

Toda observação própria deve registrar:

- device_id;
- localização e altitude quando autorizadas;
- sensor/modelo;
- firmware;
- calibration_version;
- timestamp de medição e ingestão;
- unidade;
- quality flags;
- manutenção/calibração;
- alimentação/conectividade.

A estação própria não será chamada de estação oficial INMET. O QA deverá comparar, quando aplicável, com INMET, CPTEC/INPE, CEMADEN, ANA e outros dados canônicos próximos, sem forçar igualdade entre escalas espaciais diferentes.

### 4.5 Segurança obrigatória

- identidade única por dispositivo;
- credenciais individuais e revogáveis;
- secrets fora do GitHub;
- TLS quando tecnicamente suportado;
- MQTT ACL por dispositivo/tópico;
- nenhuma porta administrativa exposta à internet;
- atualização OTA controlada/assinada quando adotada;
- segregação do dispositivo/gateway;
- logs de firmware e atualização;
- possibilidade de bloqueio remoto de um dispositivo comprometido.

## 5. Traceability & Export Compliance — AgroLog Trace

Permanece como módulo interno do AgroLog, não como novo negócio independente sem nova validação.

Capacidades:

- propriedade/polígono;
- lote/origem;
- eventos de produção/movimentação/processamento/exportação;
- evidências ambientais/geoespaciais;
- documentos;
- reconciliação de cadeia;
- versionamento de regra regulatória.

`OpenEPCIS/EPCIS 2.0` é referência/componente possível, sujeito ao Intake Gate. Não afirmar conformidade apenas por rastreabilidade técnica; compliance exige regra vigente, evidência e auditoria.

## 6. Carbon & Environmental Intelligence

Permanece apenas como capacidade analítica acoplada a GeoRisk/Trace quando dados sustentarem. Não abrir projeto/negócio independente.

Registrar metodologia, fatores, escopo e incerteza; evitar green claims não auditáveis.

## 7. Agro Quality / Lab

Não abrir spin-off ou projeto comercial independente. Preservar somente conhecimento, schemas e possibilidades analíticas úteis ao AgroLog quando aparecer necessidade operacional real. SENAITE permanece REFERENCIA sujeita a licença.

## 8. Maritime Intelligence — ampliações aprovadas conceitualmente

Preservar a V1 já especificada. Acrescentar ao backlog pós-gates:

- Route Weather Exposure;
- Maritime Disruption Alert usando fontes oficiais + eventos externos validados;
- vessel/counterparty risk apenas com evidência autorizada;
- weather/current/wave context;
- ETA/fila com forecast próprio após baselines;
- integração GeoRisk;
- reconciliação line-up + AIS + clima + histórico.

Plugins/projetos OpenCPN/weather routing são REFERENCIA algorítmica, não sistema de navegação comercial AgroLog.

## 9. News/Knowledge/Video para AgroLog

Consumir a Knowledge Factory da Holding por contratos definidos.

Usos:

- aulas e seminários técnicos autorizados;
- Embrapa/universidades/órgãos oficiais;
- procedimentos de armazenagem/logística/manutenção;
- webinars e conferências;
- extração de slides/mapas/gráficos;
- criação de claims candidatos e Knowledge Gaps.

Vídeo não vira verdade por si só. O conhecimento estrutural deve ser confrontado com literatura, manuais, normas e fontes canônicas.

## 10. Monetização transversal

Sem abrir novos projetos nesta decisão, continuam possíveis dentro do AgroLog quando houver público:

- APIs derivadas via AgroLog Gateway;
- alertas premium;
- Trace/Compliance se posteriormente validado;
- GeoRisk API se posteriormente validado;
- Maritime ETA/Pressure API;
- relatórios e índices proprietários;
- data products derivados quando licenciamento permitir.

Fleet OS e Quality/Lab não entram na fila comercial atual.

## 11. Ordem recomendada sem desviar P0/P1

1. concluir gates atuais CONAB/Gateway/Comex/clima;
2. consolidar Official Sources Intelligence e Source Hunter como capacidade compartilhada;
3. ativar GeoRisk usando fontes já prioritárias;
4. especificar e montar o primeiro Field Weather Station Node de baixo custo, sem interferir no core;
5. integrar e validar observações próprias contra fontes oficiais próximas;
6. preservar Trace como módulo futuro condicionado a necessidade real;
7. Maritime pós-V1;
8. Carbon/Quality apenas quando houver caso operacional e dados suficientes.

Toda expansão deve entrar no AI-Holding com milestone, acceptance criteria, owner, risco, dependências e decisão explícita de continuidade.
