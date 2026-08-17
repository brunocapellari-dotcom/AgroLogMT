# Arquitetura do AgroLog MT

## Visão geral

O AgroLog MT usa uma arquitetura analítica centralizada com camadas distintas para dados, engenharia, inteligência e conhecimento.

A evolução derivada do Radar GitHub passa a ser tratada como **três frentes integradas da mesma arquitetura**, e não como três arquiteturas separadas ou substituições do núcleo atual:

- **Frente A — coleta, documentos e qualidade**;
- **Frente B — inteligência, conhecimento e observabilidade**;
- **Frente C — expansão operacional e comercial**.

Essas frentes podem ser especificadas e desenvolvidas em paralelo, mas novas fontes e integrações reais só entram em produção após os critérios de qualidade, segurança e governança aplicáveis. BigQuery, GitHub, RAW/Drive/Cloud Storage, AgroLog Gateway e Obsidian mantêm suas responsabilidades canônicas.

## Princípio de seleção tecnológica

O AgroLog não acumula frameworks equivalentes. Cada capacidade deve ter uma responsabilidade principal e uma rota de substituição.

Seleção atual do Radar para provas controladas:

- **LangGraph** — candidato preferencial para orquestração dos agentes analíticos;
- **Crawl4AI** — candidato para coleta/extração de conteúdo público preparado para pipelines e RAG;
- **Whisper** — candidato para transcrição de áudio/vídeo autorizado;
- **LibreChat** — candidato para cockpit interno de IA sobre o AgroLog Gateway;
- **Polymarket Public API/SDK** — sinal experimental somente leitura para expectativa macro/geopolítica;
- **Ollama** — candidato preferencial para inferência local futura;
- **VectorBT** — laboratório quantitativo interno, não dependência central do produto;
- **HyperFrames** — publicação automatizada futura, fora do núcleo analítico;
- **code-server** — conveniência opcional de engenharia, fora do AgroLog Core.

TradingAgents, Vibe-Trading, Fincept Terminal e awesome-quant são referências/benchmarks; Open WebUI, Dify, Markdoc e llama.cpp permanecem condicionais conforme `docs/AI_TOOLING.md`.

## Camadas

1. **Fontes externas**
   - CONAB, IMEA, CEPEA, Comex Stat, ANTAQ, ANTT, ANP, USDA, NOAA, INMET e demais fontes homologadas;
   - páginas, portais, arquivos, APIs e canais autorizados de comunicação;
   - áudio/vídeo público ou autorizado quando houver valor informacional e direito de processamento;
   - sinais externos experimentais, como mercados de previsão, sempre identificados por natureza e limitações;
   - dados operacionais autorizados de clientes em etapas futuras.

2. **Aquisição e monitoramento de fontes**
   - coletores específicos por fonte;
   - APIs e conectores padronizados quando disponíveis;
   - hierarquia preferencial de aquisição: `API/arquivo/HTTP determinístico → Crawl4AI → Playwright → browser-use`;
   - Crawl4AI para conteúdo público/estruturável quando reduzir complexidade sem sacrificar rastreabilidade;
   - Playwright para navegação determinística, interação e downloads autorizados quando HTTP/Crawl4AI não forem suficientes;
   - browser-use apenas para tarefas de navegação que exijam interpretação contextual;
   - gatilhos/orquestração operacional de coleta com n8n ou ferramenta equivalente aprovada;
   - detecção de nova publicação, versão, hash, alteração de página ou novo artefato;
   - processamento por diferença quando a publicação recorrente permitir.

3. **Inteligência documental, áudio e multimodal**
   - extração de texto, tabelas e metadados de PDFs e documentos;
   - extração estruturada de imagens/tabelas por pipeline multimodal aprovado;
   - transcrição de áudio/vídeo por Whisper ou componente aprovado, preservando referência temporal quando possível;
   - classificação do conteúdo antes de qualquer persistência analítica;
   - preservação do artefato original no armazenamento RAW apropriado, nunca no GitHub.

4. **Staging, normalização, qualidade e linhagem**
   - validação de esquema;
   - normalização determinística sempre que possível;
   - deduplicação e resolução de entidades;
   - detecção de anomalias, quebra de série, mudança de unidade e inconsistência temporal;
   - registro de versão do coletor, origem, artefato, hash e transformações aplicadas;
   - bloqueio de publicação automática quando a confiança ou a qualidade estiver abaixo do limite definido;
   - prevenção explícita de look-ahead bias em estudos históricos e backtests, usando a informação disponível na data de corte.

5. **BigQuery**
   - fonte única de verdade analítica;
   - tabelas criadas sob demanda;
   - particionamento por `data_referencia` quando aplicável;
   - clustering conforme chaves de consulta relevantes;
   - dados observados, inferidos, estimados e negociados/autorizados permanecem explicitamente distinguíveis;
   - previsões, hipóteses e resultados observados podem ser persistidos para avaliação posterior.

6. **AgroLog Gateway**
   - serviço em Cloud Run;
   - API/MCP própria;
   - permissões mínimas;
   - logs de acesso;
   - sem exposição direta do banco;
   - camada obrigatória para disponibilização controlada de consultas, ferramentas dos agentes, cockpit interno e, futuramente, produtos externos.

7. **Camada de conhecimento e recuperação**
   - Obsidian como Segundo Cérebro permanente do projeto;
   - preserva conhecimento técnico, histórico e contextual;
   - não substitui GitHub nem BigQuery;
   - uma camada RAG/vetorial pode indexar conhecimento e evidências para recuperação semântica, desde que não se torne nova fonte de verdade;
   - respostas de IA devem conseguir apontar a evidência e a origem usadas;
   - transcrições de áudio/vídeo entram nesta camada somente após preservação de origem, data e referência temporal disponível.

8. **Agentes de inteligência e engenharia**
   - ChatGPT/OpenAI: coordenação, governança e manutenção do GitHub;
   - Claude Code: executor principal no notebook, testes e operações GCP/BigQuery;
   - Codex: segundo agente de engenharia e revisor técnico independente, integrado ao Claude Code por MCP quando disponível;
   - **LangGraph** é o candidato preferencial para coordenar agentes analíticos/operacionais stateful do AgroLog, separado do fluxo de engenharia Claude/Codex/ChatGPT;
   - agentes analíticos devem operar sobre ferramentas e contratos explícitos, com permissões limitadas e trilha de auditoria;
   - o padrão de análise pode usar especialistas independentes, debate pró/contra, agente cético/risco, auditor e consolidador final;
   - previsões relevantes devem ser persistidas para comparação posterior entre previsto e realizado;
   - nenhum debate entre agentes transforma inferência em dado observado.

9. **Cockpit interno de IA**
   - LibreChat é o candidato preferencial para uma interface interna multiusuário/multiprovedor;
   - fluxo obrigatório: `LibreChat → AgroLog Gateway → ferramentas/dados autorizados`;
   - LibreChat não recebe acesso irrestrito direto ao BigQuery;
   - autenticação, RBAC, logs, custo, isolamento e MCP/tools devem ser validados antes do piloto;
   - Open WebUI não deve operar em paralelo para a mesma responsabilidade sem justificativa demonstrada;
   - Dify pode ser usado apenas como sandbox/protótipo rápido, não como segunda plataforma de produção.

10. **BI, observabilidade e geointeligência**
   - BI analítico para exploração de dados e indicadores;
   - observabilidade técnica separada da camada de BI de negócio;
   - geointeligência para rotas, armazenagem, indústria, rodovias, ferrovias, hidrovias, portos e fluxos;
   - componentes específicos só entram após validação de licença, segurança, manutenção e benefício real.

11. **Laboratório quantitativo e avaliação de hipóteses**
   - ambiente separado da camada de produção para backtests, walk-forward, sensibilidade de parâmetros e validação de sinais;
   - VectorBT pode ser usado inicialmente como ferramenta de R&D, sujeito à licença vigente e sem se tornar dependência central do produto comercial;
   - qualquer teste deve reconstruir apenas os dados que estariam disponíveis na data analisada;
   - indicadores aprovados devem manter metodologia, versão, universo testado, janela, métricas e limitações;
   - uma hipótese validada no laboratório só entra em produção por contrato próprio, testes e revisão de governança.

12. **Sinais macro/geopolíticos experimentais**
   - Polymarket Public API/SDK pode fornecer probabilidade/preço observado, volume/liquidez e evolução temporal de mercados selecionados;
   - uso somente leitura: nenhuma wallet, ordem, posição ou execução pertence ao escopo do AgroLog;
   - o dado representa expectativa observada naquele mercado, não verdade futura;
   - a seleção de mercados deve exigir relevância causal potencial para energia, câmbio, fertilizantes, commodities, comércio ou logística;
   - nenhum sinal de mercado de previsão substitui fonte oficial, dado físico ou análise própria.

13. **IA local e roteamento futuro**
   - Ollama é o candidato preferencial para tarefas locais/privadas ou de alto volume quando benchmark demonstrar vantagem;
   - modelos locais não substituem automaticamente modelos externos de maior qualidade;
   - llama.cpp permanece alternativa de baixo nível para requisitos específicos de hardware, quantização ou desempenho;
   - evitar manter Ollama e llama.cpp como servidores redundantes sem necessidade comprovada.

14. **Publicação e experiência externa**
   - HyperFrames pode, futuramente, transformar relatórios, gráficos, mapas e roteiros aprovados em vídeos/explicadores automatizados;
   - a camada de publicação nunca deve recalcular indicadores ou alterar conclusões aprovadas;
   - Markdoc será reavaliado apenas quando houver portal público/documentação externa que justifique uma camada editorial própria.

15. **Engenharia e acesso ao ambiente**
   - code-server pode ser usado como conveniência opcional de desenvolvimento pelo navegador;
   - não faz parte do runtime do AgroLog;
   - qualquer exposição remota exige autenticação forte, HTTPS, controle de acesso de rede/Zero Trust equivalente e permissões mínimas;
   - segredos e credenciais continuam fora do GitHub e do frontend.

16. **Expansão operacional e comercial**
   - integração futura com telemetria/frota, IoT e visão computacional;
   - dados de clientes somente quando autorizados e isolados por contrato/permissão;
   - produtos externos consomem dados por interfaces controladas, sem acesso irrestrito ao BigQuery.

## Freight Listener — canal autorizado de ofertas de frete

O Freight Listener é um módulo da Frente C com dependências nas Frentes A e B. Sua responsabilidade é transformar mensagens e mídias de **canais autorizados** em observações estruturadas de mercado.

Fluxo conceitual:

```text
Canal autorizado (ex.: WhatsApp)
        ↓
Adaptador isolado de integração
        ↓
Webhook/fila
        ↓
Classificação de mensagem/mídia
        ↓
Extração estruturada
        ↓
Normalização + deduplicação + auditoria
        ↓
BigQuery
        ↓
Freight Market Signal Engine / BI / mapa / agentes
```

Regras estruturais:

- o adaptador de WhatsApp deve ser desacoplado do núcleo para que mudanças no provedor não derrubem o AgroLog;
- mensagens RAW, imagens, PDFs e áudios não pertencem ao GitHub;
- uma oferta anunciada é `observado` com subtipo `oferta_frete_observada`, não frete realizado;
- `contratado` e `executado` permanecem desconhecidos sem evidência operacional autorizada;
- identidade pessoal deve ser minimizada e pseudonimizada quando não for necessária à finalidade analítica;
- repostagens da mesma oportunidade devem ser agrupadas para evitar dupla contagem;
- reajuste, reoferta e persistência podem gerar sinais derivados, explicitamente classificados como inferência/estimativa conforme a metodologia;
- a especificação canônica do módulo está em `docs/FREIGHT_LISTENER.md`.

## Referências arquiteturais externas

Alguns projetos podem influenciar padrões do AgroLog sem entrar como dependência:

- **TradingAgents** — especialização, debate pró/contra, risco e consolidação;
- **Vibe-Trading** — grounding, proveniência, audit ledger, prevenção de look-ahead e testes quantitativos;
- **Fincept Terminal** — benchmark de UX, terminal de inteligência, macro/geopolítica/quant e conectores; não incorporar código sem revisão específica de copyleft/licença comercial;
- **awesome-quant** — catálogo de descoberta para o Radar Tecnológico.

Usar referência arquitetural não autoriza copiar código, marca, dados ou contratos incompatíveis.

## Fontes de verdade por responsabilidade

- GitHub: código, SQL, schemas, testes, configuração sem segredo, contratos e documentação do sistema.
- BigQuery: dados estruturados e histórico analítico oficial.
- RAW/Drive/Cloud Storage: arquivos originais, documentos de fonte e artefatos autorizados.
- Obsidian: conhecimento derivado, contexto, relações e memória histórica.

## Regras estruturais

- Não manter bases separadas por IA.
- Não criar fontes concorrentes entre GitHub, BigQuery e Obsidian.
- Não criar dezenas de tabelas vazias antecipadamente.
- Criar datasets/tabelas conforme a fonte ou módulo entra em produção.
- PostgreSQL somente se surgir necessidade transacional real.
- Toda nova fonte deve entrar com documentação de origem, frequência, granularidade, cobertura, limitações e classificação do tipo de evidência.
- Revisão por segundo agente não substitui testes executáveis.
- Ferramentas open source são componentes substituíveis: nenhuma delas deve se tornar dependência arquitetural irreversível sem justificativa.
- Antes de adotar componente externo, revisar licença, modelo de manutenção, segurança, termos de uso, privacidade, integração e estratégia de saída.
- Não adotar duas plataformas completas para a mesma função quando uma ferramenta menor ou um contrato próprio resolver o problema.
