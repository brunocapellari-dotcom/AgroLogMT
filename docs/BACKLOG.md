# Backlog Prioritário

## Regra de execução

O AgroLog MT trabalha com **três frentes integradas** derivadas do Radar GitHub. Elas podem ser especificadas, prototipadas e testadas em paralelo, mas o núcleo em produção continua obedecendo aos gates de qualidade e governança já definidos.

Não criar novas tabelas, serviços ou integrações reais apenas para preencher arquitetura futura. Cada componente entra quando tiver caso de uso, contrato mínimo, teste e benefício demonstrado.

A seleção tecnológica atual deve evitar redundância: LangGraph é o candidato preferencial de orquestração de agentes; LibreChat é o candidato preferencial de cockpit; Ollama é o candidato preferencial de inferência local. Alternativas equivalentes só avançam quando o candidato preferencial falhar em requisito objetivo.

## P0 — CONAB Armazéns em produção

- [ ] Confirmar projeto/dataset/tabela de destino no BigQuery real.
- [ ] Executar coletor CONAB Armazéns ponta a ponta.
- [ ] Validar schema e tipos.
- [ ] Validar `data_referencia`, `data_publicacao`, `data_coleta` e `competencia`.
- [ ] Validar deduplicação e idempotência.
- [ ] Validar snapshots e membros de snapshot.
- [ ] Validar particionamento e clustering.
- [ ] Validar logs de execução e contagens.
- [ ] Executar consulta de conferência no BigQuery.
- [ ] Registrar evidências e resultado da primeira carga real.

## P1 — AgroLog Gateway

- [ ] Definir contrato mínimo da primeira ferramenta de consulta.
- [ ] Conectar Cloud Run ao BigQuery com permissões mínimas.
- [ ] Implementar endpoint/ferramenta de leitura para CONAB Armazéns.
- [ ] Adicionar logs e tratamento de erros.
- [ ] Testar a mesma consulta via OpenAI e Claude.

P0/P1 continuam sendo gates para declarar o núcleo ponta a ponta validado. As frentes abaixo podem avançar em documentação, benchmark e protótipos isolados sem comprometer esse caminho crítico.

# Programa Integrado Radar

## Frente A — coleta, documentos e qualidade

### A1 — Coleta híbrida
- [ ] Catalogar fontes em `API`, `arquivo`, `página`, `login/navegação` e `canal autorizado`.
- [ ] Definir padrão de adaptador de coleta desacoplado da normalização.
- [ ] Formalizar hierarquia `API/arquivo/HTTP → Crawl4AI → Playwright → browser-use`.
- [ ] Fazer PoC de Crawl4AI em 2 fontes públicas: uma página estática/semiestruturada e uma página dinâmica, medindo completude, estabilidade, tempo, estrutura e rastreabilidade.
- [ ] Fazer prova com Playwright em uma fonte sem API adequada e comparar com Crawl4AI quando houver sobreposição.
- [ ] Avaliar browser agent apenas onde navegação determinística não for suficiente.
- [ ] Avaliar n8n para webhooks, gatilhos e automações sem transferir a fonte de verdade para a ferramenta; manter alinhamento com a Issue #36.
- [ ] Avaliar Airbyte somente em fontes com conector padronizado vantajoso.
- [ ] Registrar termos, robots/políticas de acesso, licença e requisitos de atribuição antes de produção de qualquer crawler externo.

### A2 — Detecção de atualização e processamento por diferença
- [ ] Definir registro canônico de URL/artefato, versão, hash, data de publicação e data de coleta.
- [ ] Detectar arquivo/publicação nova antes de baixar/processar novamente.
- [ ] Implementar diff para publicações recorrentes quando tecnicamente confiável.
- [ ] Disparar processamento apenas do delta quando aplicável.

### A3 — Inteligência documental e multimodal
- [ ] Benchmark inicial de Docling em PDFs/tabelas reais autorizados.
- [ ] Comparar Unstructured/Marker somente nos casos em que Docling não atender.
- [ ] Preservar texto/tabela extraídos com referência à evidência original.
- [ ] Definir pipeline multimodal para tabelas/imagens quando parser documental não for suficiente.
- [ ] Criar PoC de Whisper com conteúdo público/autorizado em português: áudio curto e vídeo/webinar maior.
- [ ] Medir qualidade de transcrição em termos técnicos, nomes próprios, números e timestamps.
- [ ] Preservar `raw_artifact_ref`, idioma, modelo/versão, timestamp/segmento e confiança/revisão quando aplicável.
- [ ] Definir fluxo `RAW → transcrição → classificação/extração → RAG/Obsidian`, sem mídia pesada no GitHub.

### A4 — Auditoria e linhagem
- [ ] Criar validações comuns para valor ausente, duplicidade, outlier, unidade e quebra temporal.
- [ ] Registrar versão do coletor/parser e hash do artefato.
- [ ] Definir limite de confiança para bloquear extração por IA duvidosa.
- [ ] Garantir rastreabilidade do indicador até fonte/artefato/transformação.
- [ ] Criar regra transversal de data de corte para impedir look-ahead em estudos históricos, sinais e backtests.

### A5 — Earth Observation cloud-native
- [ ] Selecionar um caso real MT/Brasil com valor operacional (prioridade: umidade do solo/chuva/vegetação) e fonte autorizada.
- [ ] Comparar acesso via STAC (PySTAC Client + odc-stac) e NASA Earthdata (earthaccess) conforme a fonte escolhida.
- [ ] Preservar asset/item/vintage, geometria/AOI, timestamps, licença e provenance.
- [ ] Avaliar VirtualiZarr para HDF/NetCDF grandes antes de download/cópia integral.
- [ ] Materializar inventário STAC em GeoParquet somente se o volume justificar.
- [ ] Usar TiTiler somente quando houver raster operacional que precise tiles dinâmicos no MapLibre.
- [ ] Não implantar pgSTAC/stac-fastapi/PostGIS nesta fase.

## Frente B — inteligência, conhecimento e observabilidade

### B1 — RAG do Segundo Cérebro
- [ ] Definir quais conteúdos do Obsidian/documentos/transcrições podem ser indexados.
- [ ] Benchmark Qdrant e pipeline mínimo de embeddings/recuperação.
- [ ] Garantir que o índice vetorial não se torne fonte de verdade.
- [ ] Exigir citação/evidência recuperável em respostas relevantes.

### B2 — Memória e avaliação de previsões
- [ ] Definir contrato de `hipotese`, `previsao`, `confianca`, `horizonte`, `resultado_observado` e `erro`.
- [ ] Persistir previsões relevantes antes de conhecer o resultado.
- [ ] Implementar comparação previsto × realizado.
- [ ] Avaliar memória de agente sem substituir BigQuery/GitHub/Obsidian.
- [ ] Verificar se memória/checkpoint do LangGraph cobre a necessidade antes de adicionar mem0 ou camada equivalente.

### B3 — Runtime multiagente tipado
- [ ] Usar Pydantic AI + Harness como primeiro candidato do runtime analítico.
- [ ] Implementar piloto com 3 papéis: especialista → cético/contra → auditor/consolidador.
- [ ] Validar outputs tipados, tools autorizadas, Planning, SubAgents/Dynamic Workflow e limites de uso.
- [ ] Testar Step Persistence/recovery e human approval somente onde o caso exigir.
- [ ] Definir permissões e ferramentas por agente exclusivamente via AgroLog Gateway/contratos explícitos.
- [ ] Manter Memory/Conversation Search segregados e sem autoridade sobre Obsidian canônico.
- [ ] Adaptar padrões úteis de TradingAgents/Vibe-Trading sem importar uma segunda stack.
- [ ] Manter LangGraph como alternativa condicional; não instalar em paralelo sem falha objetiva do candidato preferencial.
- [ ] Manter separação entre runtime de agentes e n8n (pipelines/gatilhos).

### B3.1 — Avaliação, tracing e red-team de IA
- [x] Criar contrato canônico `contracts/agent_evaluation.v1.schema.json`.
- [x] Adicionar teste de governança para grounding, classificação epistemológica, autorização de tools, prompt injection, exfiltração e cutoff temporal.
- [x] Implementar gate determinístico fail-closed em `models/agent_evaluation.py`, independente do avaliador externo.
- [x] Cobrir missing/duplicate checks, tool não autorizada, evidência incompleta e divergência de status em `tests/test_agent_evaluation.py`.
- [ ] Instrumentar o primeiro piloto com OpenTelemetry/Phoenix.
- [ ] Construir golden dataset versionado por cenário/agente.
- [ ] Criar suíte Promptfoo para regressão + red-team.
- [ ] Bloquear promoção quando houver tool não autorizada, claim sem evidência material, exfiltração, quebra de cutoff ou classificação epistemológica incorreta.

### B4 — Cockpit interno de IA
- [ ] PoC de LibreChat como candidato preferencial de cockpit interno.
- [ ] Integrar o PoC somente ao AgroLog Gateway/mock controlado; nenhuma credencial direta de BigQuery.
- [ ] Validar autenticação, RBAC/grupos, MCP/tools, arquivos, logs, isolamento por usuário e custo.
- [ ] Definir perfis iniciais: Agro, Logística, Portos, Clima/Macro, Documentos e Freight Intelligence.
- [ ] Não instalar Open WebUI em paralelo; reavaliar apenas se houver requisito local-first/offline não atendido.
- [ ] Permitir Dify somente em sandbox para protótipos rápidos; qualquer protótipo aprovado deve migrar para a arquitetura oficial.

### B5 — BI, observabilidade e geointeligência
- [ ] Avaliar Metabase para exploração analítica.
- [ ] Avaliar Grafana para saúde de coletores/jobs/filas/serviços.
- [ ] Definir primeiras camadas QGIS: produção, armazéns, indústria, corredores e portos.
- [ ] Avaliar GeoServer apenas quando houver necessidade real de servir camadas.

### B6 — AgroLog Watch e grafo causal
- [ ] Definir monitoramento de páginas/publicações críticas.
- [ ] Separar clipping de notícia de evento material para variável AgroLog.
- [ ] Registrar relações causais tipadas quando houver evidência suficiente.
- [ ] Manter confiança e alternativas explicativas em análises causais.

### B7 — Laboratório quantitativo e backtesting
- [ ] Criar especificação de laboratório separada da produção, sem criar nova fonte de verdade.
- [ ] Avaliar VectorBT em sandbox para 2 casos AgroLog: um indicador de mercado/agro e um sinal logístico/frete.
- [ ] Implementar reconstrução point-in-time usando `data_referencia`, `data_publicacao`, `data_coleta` e data de corte.
- [ ] Medir robustez fora da amostra, sensibilidade de parâmetros e desempenho por regime/período quando aplicável.
- [ ] Registrar versão da hipótese, universo, janela, regra, métricas, limitações e resultado.
- [ ] Revisar Commons Clause/licença vigente antes de qualquer uso que componha produto comercial.
- [ ] Se metodologia validada virar função central, avaliar implementação própria/permissiva ou licença adequada.
- [ ] Usar `awesome-quant` como catálogo de descoberta, não como dependência.

### B8 — Sinais macro/geopolíticos experimentais
- [ ] PoC somente leitura com a API/SDK pública oficial vigente da Polymarket.
- [ ] Selecionar poucos mercados com vínculo causal plausível a petróleo/energia, câmbio, fertilizantes, commodities, comércio ou logística.
- [ ] Persistir evento/mercado, timestamp, probabilidade/preço, volume/liquidez quando disponíveis e metadados de origem.
- [ ] Classificar explicitamente como `sinal_expectativa_mercado`, nunca fato futuro nem previsão oficial.
- [ ] Proibir wallet, posição, ordem ou execução no escopo AgroLog.
- [ ] Avaliar utilidade incremental: o sinal melhora antecedência/explicação ou apenas replica notícias?

### B9 — IA local
- [ ] Benchmark Ollama com 2 tarefas de alto volume e baixo risco antes de qualquer uso crítico.
- [ ] Comparar custo, latência, privacidade e qualidade com modelo externo de referência.
- [ ] Expor IA local por interface controlada, sem espalhar dependência de provider pelo código.
- [ ] Não manter llama.cpp como servidor paralelo; avaliá-lo somente para requisito específico de hardware/quantização/desempenho.
- [ ] Definir quais tarefas nunca podem ser rebaixadas para modelo local sem validação adicional.

## Frente C — expansão operacional e comercial

### C1 — Freight Listener
- [ ] Usar `docs/FREIGHT_LISTENER.md` como especificação canônica do módulo.
- [ ] Comparar Evolution API, WPPConnect e WAHA para prova isolada.
- [ ] Não conectar conta real antes de validar licença, segurança, termos, privacidade e isolamento.
- [ ] Definir webhook/evento canônico independente do provedor de WhatsApp.
- [ ] Criar fixture artificial de mensagem de oferta de frete para testes futuros.
- [ ] Implementar classificador `relevante/ruido`.
- [ ] Implementar extração estruturada de texto.
- [ ] Implementar pipeline para imagem/PDF em etapa seguinte.
- [ ] Implementar normalização de município/UF/produto/equipamento/unidade.
- [ ] Implementar deduplicação e agrupamento de repostagens.
- [ ] Implementar detecção de reoferta, reajuste e persistência.
- [ ] Definir sinais agregados e limites mínimos de cobertura antes de publicar indicador.
- [ ] Integrar ao BigQuery somente depois de schema/testes/idempotência/linhagem validados.
- [ ] Expor consultas pelo AgroLog Gateway quando a primeira tabela estiver validada.

### C2 — Freight Market Signal Engine
- [ ] Quantidade bruta de mensagens classificadas como ofertas.
- [ ] Quantidade estimada de oportunidades únicas após deduplicação.
- [ ] Taxa de repostagem/reoferta.
- [ ] Taxa de reajuste de valor em provável mesma oportunidade.
- [ ] Persistência observada da oferta.
- [ ] Mediana/faixas de valor de **ofertas observadas** por rota/produto/equipamento/período.
- [ ] Índice de concentração por fonte para evitar interpretar uma amostra enviesada como mercado total.
- [ ] Cobertura/amostra mínima explícita em todo indicador.

### C3 — Mapa de ofertas
- [ ] Geocodificar origem/destino com identificadores canônicos.
- [ ] Exibir fluxos agregados, nunca PII.
- [ ] Cruzar futuramente com infraestrutura, line-up, safra e demanda industrial.

### C4 — Integrações operacionais futuras
- [ ] Avaliar Traccar/Fleetbase somente com dados autorizados de clientes.
- [ ] Avaliar ThingsBoard/IoT quando existir caso concreto de sensor/ativo.
- [ ] Avaliar visão computacional apenas em ambiente autorizado e com objetivo mensurável.
- [ ] Todo produto externo deve consumir interfaces controladas via AgroLog Gateway.

### C5 — Publicação automatizada
- [ ] Avaliar HyperFrames somente após existir fluxo editorial estável e necessidade recorrente de vídeo/explicador.
- [ ] PoC futura: transformar um relatório já aprovado em vídeo curto com gráficos/mapas/narração/legendas.
- [ ] Garantir que a camada de publicação consuma números e conclusões aprovados, sem recalcular indicadores.
- [ ] Definir identidade visual e revisão humana antes de conteúdo externo automático.
- [ ] Reavaliar Markdoc somente quando houver portal público/documentação para clientes.

## Trilha transversal — engenharia e referências

### T1 — Ambiente de desenvolvimento remoto
- [ ] Avaliar code-server apenas se acesso pelo navegador resolver necessidade concreta do time.
- [ ] Qualquer PoC deve usar autenticação forte, HTTPS e acesso de rede restrito (VPN/IAP/Zero Trust equivalente).
- [ ] Não expor credenciais GCP/GitHub ao frontend e não tornar code-server requisito do runtime.

### T2 — Benchmarks arquiteturais
- [ ] Fincept Terminal: estudar UX/terminal de inteligência, macro/geopolítica/quant e organização de módulos; não incorporar código sem revisão específica de licença/copyright/comercialização.
- [ ] TradingAgents: estudar debate multiagente, risco, persistência e checkpoints.
- [ ] Vibe-Trading: estudar grounding, proveniência, audit ledger, unidades e look-ahead.
- [ ] awesome-quant: manter como fonte de descoberta do Technology Radar.
- [ ] Toda ideia aproveitada deve ser reimplementada como contrato/padrão próprio ou por componente com licença compatível; não copiar plataforma inteira.

## Próxima fonte oficial

A expansão de fontes de produção continua começando pelo **IMEA** após o núcleo P0/P1 estar validado, preservando separação por produto e rotina de atualização automática/API/login conforme a fonte permitir.

Isso não impede os protótipos isolados das três frentes, desde que não criem uma segunda fonte de verdade nem comprometam a prioridade do núcleo.

## Critério de pronto por fonte ou módulo

Uma fonte/módulo só é considerada em produção quando tiver:

- coleta reproduzível;
- schema/contrato documentado;
- normalização determinística quando aplicável;
- deduplicação validada;
- histórico preservado quando necessário;
- classificação de evidência explícita;
- política de privacidade/retenção quando houver dado pessoal ou canal autorizado;
- carga real no BigQuery quando o módulo produzir dado analítico;
- logs auditáveis;
- consulta de conferência;
- documentação de limitações;
- teste pelo AgroLog Gateway quando aplicável;
- plano de substituição para dependências externas críticas;
- licença/termos revisados para o modo de uso real;
- ausência de ferramenta equivalente paralela sem justificativa documentada.
