# Backlog Prioritário

## Regra de execução

O AgroLog MT passa a trabalhar com **três frentes integradas** derivadas do Radar GitHub. Elas podem ser especificadas, prototipadas e testadas em paralelo, mas o núcleo em produção continua obedecendo aos gates de qualidade e governança já definidos.

Não criar novas tabelas, serviços ou integrações reais apenas para preencher arquitetura futura. Cada componente entra quando tiver caso de uso, contrato mínimo, teste e benefício demonstrado.

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
- [ ] Fazer prova com Playwright em uma fonte sem API adequada.
- [ ] Avaliar browser agent apenas onde navegação determinística não for suficiente.
- [ ] Avaliar n8n para webhooks, gatilhos e automações sem transferir a fonte de verdade para a ferramenta.
- [ ] Avaliar Airbyte somente em fontes com conector padronizado vantajoso.

### A2 — Detecção de atualização e processamento por diferença
- [ ] Definir registro canônico de URL/artefato, versão, hash, data de publicação e data de coleta.
- [ ] Detectar arquivo/publicação nova antes de baixar/processar novamente.
- [ ] Implementar diff para publicações recorrentes quando tecnicamente confiável.
- [ ] Disparar processamento apenas do delta quando aplicável.

### A3 — Inteligência documental
- [ ] Benchmark inicial de Docling em PDFs/tabelas reais autorizados.
- [ ] Comparar Unstructured/Marker somente nos casos em que Docling não atender.
- [ ] Preservar texto/tabela extraídos com referência à evidência original.
- [ ] Definir pipeline multimodal para tabelas/imagens quando parser documental não for suficiente.

### A4 — Auditoria e linhagem
- [ ] Criar validações comuns para valor ausente, duplicidade, outlier, unidade e quebra temporal.
- [ ] Registrar versão do coletor/parser e hash do artefato.
- [ ] Definir limite de confiança para bloquear extração por IA duvidosa.
- [ ] Garantir rastreabilidade do indicador até fonte/artefato/transformação.

## Frente B — inteligência, conhecimento e observabilidade

### B1 — RAG do Segundo Cérebro
- [ ] Definir quais conteúdos do Obsidian/documentos podem ser indexados.
- [ ] Benchmark Qdrant e pipeline mínimo de embeddings/recuperação.
- [ ] Garantir que o índice vetorial não se torne fonte de verdade.
- [ ] Exigir citação/evidência recuperável em respostas relevantes.

### B2 — Memória e avaliação de previsões
- [ ] Definir contrato de `hipotese`, `previsao`, `confianca`, `horizonte`, `resultado_observado` e `erro`.
- [ ] Persistir previsões relevantes antes de conhecer o resultado.
- [ ] Implementar comparação previsto × realizado.
- [ ] Avaliar memória de agente sem substituir BigQuery/GitHub/Obsidian.

### B3 — Orquestração multiagente
- [ ] Benchmark de um único orquestrador entre candidatos aprovados.
- [ ] Definir permissões e ferramentas por agente.
- [ ] Formalizar handoff, auditoria e condição de parada.
- [ ] Não permitir instalação simultânea de frameworks equivalentes sem justificativa.

### B4 — BI, observabilidade e geointeligência
- [ ] Avaliar Metabase para exploração analítica.
- [ ] Avaliar Grafana para saúde de coletores/jobs/filas/serviços.
- [ ] Definir primeiras camadas QGIS: produção, armazéns, indústria, corredores e portos.
- [ ] Avaliar GeoServer apenas quando houver necessidade real de servir camadas.

### B5 — AgroLog Watch e grafo causal
- [ ] Definir monitoramento de páginas/publicações críticas.
- [ ] Separar clipping de notícia de evento material para variável AgroLog.
- [ ] Registrar relações causais tipadas quando houver evidência suficiente.
- [ ] Manter confiança e alternativas explicativas em análises causais.

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
- plano de substituição para dependências externas críticas.
