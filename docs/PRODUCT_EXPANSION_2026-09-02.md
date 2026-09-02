# Expansão de Produtos e Inteligência — AgroLog MT

Data: 02/09/2026

## Objetivo

Consolidar as rodadas de pesquisa em módulos que ampliam o AgroLog MT sem criar fontes concorrentes de verdade e sem interromper P0/P1. Este documento complementa `ARCHITECTURE.md` e `TECHNOLOGY_STACK.md`; qualquer runtime novo continua sujeito aos gates já definidos nesses documentos.

## Regra

Não reescrever coletor, contrato, Gateway ou modelo homologado apenas para padronizar ferramenta. Novos componentes entram somente quando resolvem caso real e passam por licença, segurança, testes e estratégia de saída.

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

Módulo compartilhado do AgroLog, não empresa separada inicialmente.

Fontes/capacidades prioritárias:

- GOES/INPE para evolução meteorológica rápida;
- INMET/CPTEC/CEMADEN/ANA;
- GPM/IMERG para precipitação espacial;
- FIRMS para focos de calor/incêndio;
- Sentinel/Copernicus;
- Landsat;
- Brazil Data Cube;
- dados geoespaciais oficiais brasileiros.

Produtos derivados:

- Fire Risk;
- Flood/Water Risk;
- Drought Risk;
- Route Weather Risk;
- property/farm risk;
- vegetation/land/water change;
- infrastructure monitoring.

Código proprietário deve produzir `risk/event objects` com evidência, timestamp, geografia, confidence e natureza da inferência, em vez de apenas mostrar imagens.

## 4. AgroLog Fleet OS Brasil

Novo subprojeto lógico a validar comercialmente, podendo permanecer no repositório AgroLog enquanto compartilha Gateway, Data/Geo/Security Core e governança.

### 4.1 Núcleo

- veículos/implementos;
- motoristas;
- viagens;
- clientes/origens/destinos;
- documentos;
- custos;
- manutenção;
- ocorrências;
- localização autorizada;
- profitability.

### 4.2 Módulos consolidados

- Fleet Profitability: margem econômica real por viagem, rota, veículo, cliente e motorista;
- Document Intelligence: CT-e/MDF-e/NF-e/POD e conciliação;
- Tire Intelligence: custo/km, posição, recapagem, falha e vida útil;
- Fuel Intelligence/Fraud: nota + GPS + CAN/telemetria + expected consumption;
- Detention Intelligence: espera, carga/descarga e turnaround por cliente/local;
- Route Risk: clima, fogo, restrição, histórico e road score;
- Driver Copilot: PWA/offline/voz para eventos operacionais;
- Maintenance/Asset Health;
- Road Intelligence Network com sinais agregados de frota;
- parts/services procurement futuro.

### 4.3 Componentes/referências

Fleetbase por arquitetura/módulos; Traccar; OpenDBC/SavvyCAN; NFePHP; Valhalla/FMM; OR-Tools/PyVRP; PyOD/Nixtla; Pipecat; MapLibre/deck.gl.

Nenhum componente externo define o modelo de domínio canônico; contratos AgroLog permanecem próprios.

## 5. Traceability & Export Compliance — AgroLog Trace

Módulo inicial do AgroLog para rastreabilidade de cadeias e exigências de mercado/exportação.

Capacidades:

- propriedade/polígono;
- lote/origem;
- eventos de produção/movimentação/processamento/exportação;
- evidências ambientais/geoespaciais;
- documentos;
- reconciliação de cadeia;
- versionamento de regra regulatória;
- Supply Chain Passport futuro.

`OpenEPCIS/EPCIS 2.0` é referência/componente possível, sujeito ao Intake Gate. Não afirmar conformidade apenas por rastreabilidade técnica; compliance exige regra vigente, evidência e auditoria.

## 6. Carbon & Environmental Intelligence

Módulo do AgroLog Trace/GeoRisk, não projeto separado agora.

Calcular quando dados sustentarem:

- diesel/rota/carga;
- energia/processamento;
- t.km;
- fatores versionados;
- escopo e incerteza.

Brightway/LCA é referência de cálculo. Resultados devem registrar metodologia, fatores e intervalo/incerteza; evitar green claims não auditáveis.

## 7. Agro Quality / Lab Intelligence

Vertical a validar dentro do AgroLog antes de qualquer spin-off.

Objetivo: ligar qualidade física/laboratorial a origem, lote, armazenagem, transporte e resultado.

Dados potenciais:

- umidade;
- impurezas;
- avariados/ardidos;
- peso;
- temperatura;
- classificação;
- laudos;
- sensores de armazenagem.

SENAITE é referência de LIMS e exige revisão de licença/integração antes de uso comercial. O diferencial AgroLog deve ser a análise e reconciliação, não reconstrução de um LIMS genérico.

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

Possíveis camadas sem criar unidades separadas inicialmente:

- APIs derivadas via AgroLog Gateway;
- alertas premium;
- Fleet OS por assinatura;
- Trace/Compliance por empresa/propriedade/lote;
- GeoRisk API;
- Maritime ETA/Pressure API;
- Quality analytics;
- relatórios e índices proprietários;
- data products derivados quando licenciamento permitir.

## 11. Ordem recomendada sem desviar P0/P1

1. concluir gates atuais CONAB/Gateway/Comex/clima;
2. consolidar Official Sources Intelligence e Source Hunter como capacidade compartilhada;
3. ativar GeoRisk usando fontes já prioritárias;
4. validar comercialmente Fleet OS com escopo de profitability + documentos + detention antes de expandir;
5. Trace/Export Compliance;
6. Maritime pós-V1;
7. Quality/Lab;
8. Carbon somente com dados e metodologia auditáveis.

Toda expansão deve entrar no AI-Holding com milestone, acceptance criteria, owner, risco, dependências e decisão explícita de continuidade.
