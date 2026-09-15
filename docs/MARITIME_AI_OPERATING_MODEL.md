# AgroLog Maritime Intelligence — AI Operating Model

## Princípio
A Inteligência Marítima pertence ao AgroLog e reutiliza governança, dados e Segundo Cérebro comuns, mas opera com um motor especializado. Nenhum agente pode promover programação a realizado, uma única mensagem AIS a verdade física ou inferência a observação.

## Agentes

### MARITIME CHIEF AI
Responsável pela visão integrada do domínio marítimo, priorização, síntese operacional e coordenação dos demais agentes. Consolida sinais de AIS, portos, line-up, clima, comércio exterior e qualidade das fontes. Não altera dado bruto e não ignora gates de evidência.

### VESSEL TRACKING AI
Responsável por identidade, trajetória, qualidade AIS, posição, movimento, replay e estado físico provável. Usa MMSI/IMO, sequência temporal e geofences validadas. Uma mensagem isolada permanece `UNCONFIRMED_SINGLE`.

### PORT AI
Responsável por port calls, áreas portuárias, fundeios, berços, terminais, filas, turnaround e estados físicos. Só pode declarar `OPERANDO` ou `CONCLUIDO` com evidência operacional oficial/validada.

### ETA AI
Responsável por ETA observado/informado/modelado e erro de ETA. Deve manter separados ETA informado pela fonte, ETA derivado de AIS e ETA proprietário AgroLog. Modelos proprietários permanecem `DATA_GATED` até calibração fora da amostra.

### LINE-UP AI
Responsável por ingestão, normalização, comparação temporal e confronto de line-ups oficiais. Line-up é `INFORMADO`; volume programado não é volume realizado.

### TRADE FLOW AI
Responsável por conectar movimento físico marítimo com Comex Stat, ANTAQ e demais bases de comércio exterior. Não atribui comprador, vendedor, trading ou carga efetiva a um navio sem fonte autorizada e identificável.

### ANOMALY AI
Responsável por detectar anomalias de posição, relógio, velocidade, identidade, rota e comportamento. Pode emitir `SPOOFING_SUSPECTED`, nunca `SPOOFING_CONFIRMED`, sem evidência adicional independente.

### MARITIME AUDITOR
Agente independente de validação. Audita freshness, proveniência, coerência temporal, classificação epistemológica, direitos/licenciamento, qualidade AIS, transições de estado, segurança, custo de consulta e cobertura dos cinco portos piloto. Pode bloquear publicação ou promoção de estado.

## Fluxo de decisão
1. collectors preservam RAW e metadados de coleta;
2. normalização produz registros canônicos sem apagar RAW;
3. Quality Engine valida identidade, posição, tempo e trajetória;
4. Vessel Tracking/Port AI constroem estado físico apenas com evidência suficiente;
5. Line-up AI confronta programação com evidência física;
6. ETA AI calcula diferenças e modelos somente quando elegíveis;
7. Trade Flow AI integra contexto de comércio exterior sem inventar carga por navio;
8. Anomaly AI adiciona flags e confiança;
9. Maritime Auditor valida antes da publicação;
10. Maritime Chief AI consolida o produto final.

## Segurança e dados
- segredos somente em Secret Manager/Vault equivalente;
- nenhuma chave em Git, log, URL ou artefato;
- gateway privado por padrão;
- raw e canônico separados;
- mínimo privilégio para collectors, gateway e deploy;
- dados hidrográficos sujeitos a autorização/licença;
- logs sem payloads sensíveis ou segredos;
- toda inferência preserva fonte, versão, timestamp e confiança.

## Estado físico canônico
`PROGRAMADO -> EM_VIAGEM -> APROXIMACAO -> AREA_PORTUARIA -> FUNDEADO -> AGUARDANDO -> MANOBRA -> ATRACADO -> OPERANDO -> CONCLUIDO -> DESATRACADO -> SAIU`.

O estado físico é separado do lifecycle editorial legado. Transições futuras devem usar o modelo em `models/maritime_port_state.py`.

## Referências de arquitetura
- `ais-tracker`: referência arquitetural para tracking, não dependência automática;
- `vessel-eta-tracker`: referência para ETA versus programação;
- `SeaRoute`: referência para rotas/visualização, sujeito a licença e validação;
- MapLibre + PMTiles: base cartográfica/tiles;
- PostGIS + TimescaleDB: opção para camada operacional/hot history quando latência/consulta espacial justificar; BigQuery permanece a fonte analítica histórica canônica do AgroLog até gate técnico explícito.
