# Ferramentas de IA e Extensões

Este documento é o registro canônico de ferramentas externas, agentes, skills e extensões avaliadas para o AgroLog MT.

## Componentes permanentes

**ChatGPT/OpenAI**
- Coordenação, governança, arquitetura e consolidação do GitHub.

**Claude Code**
- Executor principal no notebook para implementação, terminal, testes e GCP/BigQuery.

**Codex**
- Segundo agente de engenharia e revisor técnico independente.
- Integração atual com Claude Code: MCP local usando `codex mcp-server`.
- Arquivos relacionados: `.mcp.json`, `AGENTS.md`, `docs/MULTI_AGENT_WORKFLOW.md` e `docs/CODEX_SETUP_WINDOWS.md`.
- Regra: um agente implementa e o outro revisa; evitar edição concorrente e loops entre agentes.

**Obsidian**
- Segundo Cérebro do AgroLog MT para conhecimento técnico, histórico e contextual.
- Não substitui GitHub nem BigQuery.
- Documento inicial: `docs/OBSIDIAN.md`.

## Radar Tecnológico do AgroLog MT

O projeto mantém um Radar Tecnológico como responsabilidade permanente do CONSTRUTOR/coordenação do AgroLog MT.

Objetivo:
- identificar componentes open source que reduzam tempo de desenvolvimento;
- aumentar automação e qualidade de dados;
- melhorar recuperação de conhecimento e capacidade analítica;
- criar capacidades comerciais sem redesenhar o núcleo;
- acompanhar licença, atividade do projeto, segurança, comunidade e risco de dependência.

Regra: componentes do Radar são **peças substituíveis**. BigQuery, GitHub, armazenamento RAW, AgroLog Gateway e Obsidian não são substituídos apenas porque uma ferramenta nova oferece função semelhante.

## Aprovado para adoção controlada

**Superpowers**
- Função: disciplina de planejamento, implementação, teste, depuração e revisão.
- Regra: não substitui `CLAUDE.md`, `AGENTS.md`, governança, testes próprios nem revisão multiagente.
- Status: aprovado para configuração controlada; não vendorizado no repositório.

## Seleção estratégica do Radar — ordem de avaliação

Os itens desta seção foram selecionados por criarem capacidade nova ou por terem papel suficientemente distinto. A seleção **não autoriza instalação ou produção automática**: cada componente ainda precisa de PoC, análise de licença, segurança, custo, manutenção e estratégia de saída.

### Orquestração de agentes analíticos

**Pydantic AI + Pydantic AI Harness — candidato preferencial**
- Uso pretendido: runtime tipado para os agentes definidos em `contracts/ai_roles.v1.json`, com ferramentas/outputs estruturados, Planning, SubAgents, Dynamic Workflow, Step Persistence, memória operacional segregada e instrumentação OpenTelemetry.
- Papel: coordenação de **agentes de inteligência**, não de pipelines de coleta.
- Toda ferramenta de dados deve passar pelo AgroLog Gateway/contrato autorizado; agentes não recebem acesso irrestrito ao BigQuery.
- Memory/Conversation Search são memória de runtime, nunca conhecimento canônico; Obsidian e a Knowledge Factory prevalecem para conhecimento aprovado.
- Durable execution só entra quando houver workflow longo/recovery real; não criar infraestrutura adicional por antecipação.

**LangGraph — referência / alternativa condicional**
- Continua válido para grafos stateful e human-in-the-loop, porém não será instalado em paralelo por precaução.
- Só deve superar Pydantic AI/Harness se benchmark real demonstrar requisito de grafo/ciclo/controle de estado que o stack preferencial não atenda adequadamente.

**Regra de exclusividade**
- Não instalar CrewAI, Agno, Semantic Kernel, AutoGen ou outro framework equivalente para a mesma responsabilidade sem falha objetiva do candidato preferencial.
- `n8n` continua separado para gatilhos/integrações operacionais; não é runtime de raciocínio.

**Padrão de debate inspirado em TradingAgents**
- Adotar o padrão conceitual de especialistas independentes, análise pró/contra, agente cético/risco, auditor e consolidador final.
- Não incorporar TradingAgents como segunda stack operacional, pois o padrão pode ser implementado sobre LangGraph e ferramentas próprias do AgroLog.
- O debate nunca substitui evidência, DQ, testes ou revisão humana quando exigida.

### Automação e coleta

**n8n**
- Uso pretendido: gatilhos, automações, webhooks e integrações entre serviços.
- Regra: revisar licença/modelo de uso antes de qualquer oferta comercial ou hospedagem para terceiros.
- Não armazenar lógica analítica canônica dentro de workflows quando ela pertencer ao código versionado.

**Crawl4AI — candidato prioritário para conteúdo público**
- Uso pretendido: transformar sites e páginas públicas em conteúdo limpo/estruturado para pipelines, RAG e agentes, incluindo páginas dinâmicas quando aplicável.
- Posição na hierarquia: usar depois de API/HTTP/arquivo determinístico e antes de automação de navegador mais pesada quando o caso permitir.
- Hierarquia preferencial: `API/arquivo/HTTP → Crawl4AI → Playwright → browser-use`.
- Regra: respeitar robots, termos, limites, autenticação e restrições da fonte; não usar técnicas de evasão como justificativa para violar políticas de acesso.
- Licença/atribuição: revisar a licença vigente e requisitos de atribuição antes de distribuição, uso público ou oferta comercial.

**Playwright**
- Uso pretendido: navegação determinística em fontes sem API adequada, testes, interação controlada e downloads automatizados.
- Usar quando Crawl4AI/HTTP não resolver o fluxo de forma estável ou quando houver sequência de interação autorizada.

**browser-use ou agente de navegador equivalente**
- Uso pretendido: tarefas de navegação que exigem interpretação contextual.
- Regra: último nível da hierarquia de navegação; não substituir coletor determinístico quando houver API/endpoint estável.

**Airbyte**
- Uso pretendido: conectores padronizados para fontes em que o uso do conector seja mais simples e confiável que código próprio.

### Inteligência documental, áudio e multimodal

**Docling**
- Uso pretendido: extração de texto, tabelas, estrutura e metadados de PDFs/documentos.

**Unstructured / Marker**
- Uso pretendido: alternativas/complementos de parsing documental quando demonstrarem desempenho melhor em casos específicos.

**Whisper — candidato prioritário para áudio/vídeo**
- Uso pretendido: transformar webinars, entrevistas, podcasts, vídeos, reuniões e áudios autorizados em transcrições pesquisáveis com referência temporal quando disponível.
- Aplicações: conteúdo técnico do agro, apresentações empresariais, audiências, eventos, entrevistas e materiais públicos/autorizados.
- Fluxo esperado: artefato original em RAW → transcrição → classificação/extração → conhecimento/RAG; nunca guardar mídia pesada no GitHub.
- Regra: transcrição é evidência derivada do áudio; trechos relevantes devem permanecer rastreáveis ao artefato e timestamp quando tecnicamente possível.

### Conhecimento e recuperação

**Qdrant**
- Uso pretendido: camada vetorial/RAG para recuperação semântica.
- Regra: índice vetorial não é fonte de verdade; toda resposta relevante deve ser rastreável à evidência canônica.

**RAGFlow / LlamaIndex / LangChain / AnythingLLM**
- Uso pretendido: avaliar componentes de ingestão e recuperação RAG quando agregarem capacidade não coberta pelo pipeline mínimo.
- Regra: selecionar somente o mínimo necessário após benchmark; evitar empilhar frameworks equivalentes.
- LangGraph, quando adotado, será tratado separadamente como orquestrador de agentes, não como substituto automático da camada RAG.

### Observabilidade e regressão de agentes

**Phoenix — POC preferencial de observabilidade/eval de IA**
- Instrumentação via OpenTelemetry/OpenInference.
- Tracing de modelo, tools, retrieval, tokens, latência, custo e erros.
- Datasets/experimentos para comparar versões de agentes e prompts.
- Aplicar minimização/redaction antes de enviar conteúdo sensível à telemetria.
- Não substitui OpenTelemetry Collector nem logs operacionais do runtime.

**Promptfoo — POC preferencial de regressão/red-team**
- Testar prompt injection, tool injection, exfiltração, uso indevido de ferramentas, regressão de citação/evidência e violações de classificação epistemológica.
- Usar golden cases versionados e ataques explícitos em CI/ambiente controlado.
- Não substitui unittest, data-quality gates, live tests ou auditor final.

### Cockpit interno e acesso humano à IA

**LibreChat — candidato preferencial de cockpit**
- Uso pretendido: interface interna multiusuário/multiprovedor para conversar com agentes, ferramentas e conhecimento do AgroLog.
- Integração obrigatória: `LibreChat → AgroLog Gateway → BigQuery/serviços autorizados`.
- Nunca conceder acesso direto e irrestrito do cockpit ao BigQuery.
- Avaliar autenticação, RBAC, MCP/tools, logs, isolamento por usuário e custos antes do piloto.

**Open WebUI — alternativa condicional**
- Não adotar em paralelo com LibreChat para a mesma função.
- Reavaliar somente se uma estratégia local-first/offline ou requisitos específicos de Open WebUI superarem claramente o cockpit preferencial.

**Dify — somente prototipagem rápida**
- Permitido como sandbox para validar rapidamente um agente, interface ou fluxo de IA.
- Não usar como segunda plataforma de produção duplicando LangGraph + n8n + RAG + LibreChat.
- Protótipo aprovado deve ser migrado para contratos e componentes oficiais do AgroLog antes de produção.

### BI, observabilidade e geointeligência

**Metabase**
- Uso pretendido: BI operacional/analítico para exploração de indicadores.

**Grafana**
- Uso pretendido: observabilidade técnica de pipelines, coletores, filas, jobs e serviços.

**QGIS / GeoServer**
- Uso pretendido: análise espacial e eventual disponibilização controlada de camadas geográficas.

### Memória de agentes

**Pydantic AI Harness Memory / Conversation Search — preferência de runtime**
- Usar somente para memória operacional segregada por projeto/agente/conversa.
- Obsidian/Segundo Cérebro continua sendo a verdade editorial/canônica aprovada.
- Runtime memory não pode promover, alterar ou sobrescrever conhecimento canônico.
- Mem0 e equivalentes permanecem `NAO_SELECIONADO` enquanto duplicarem essa função sem ganho mensurável.

### Sinais externos experimentais

**Polymarket Public API/SDK — somente leitura**
- Uso pretendido: sinal complementar de expectativa coletiva sobre eventos macroeconômicos ou geopolíticos com possível impacto em energia, câmbio, fertilizantes, commodities ou logística.
- Consumir somente dados públicos necessários; não usar wallet, ordem, posição ou execução de mercado no AgroLog.
- Classificação: sinal observado de mercado de previsão, não fato futuro nem previsão oficial do AgroLog.
- Qualquer uso analítico deve preservar mercado/evento, timestamp, probabilidade/preço observado, liquidez/volume quando disponíveis e limitações da amostra.
- O SDK oficial vigente deve ser confirmado no momento da implementação; em 17/08/2026 o projeto oficial recomenda `Polymarket/py-sdk` para novos projetos.

### IA local e redução futura de custo

**Ollama — candidato preferencial para inferência local**
- Uso pretendido: tarefas locais/privadas ou de alto volume em que qualidade, latência e custo demonstrem vantagem.
- Não substituir modelos de maior qualidade em tarefas críticas sem benchmark objetivo.
- Expor modelos locais por interface controlada e observável, evitando dependência direta espalhada pelo código.

**llama.cpp — motor/fallback de baixo nível**
- Não manter servidor paralelo ao Ollama sem necessidade real.
- Avaliar apenas quando houver requisito de hardware, quantização, desempenho, portabilidade ou controle que Ollama não atenda.

### Laboratório quantitativo e backtesting

**VectorBT — R&D interno**
- Uso pretendido: testar historicamente indicadores, sinais, thresholds, relações temporais e hipóteses do AgroLog, inclusive previsto × realizado e sensibilidade de parâmetros.
- Não restringir o conceito a trading financeiro; pode ser usado como motor experimental para séries temporais do agro/logística quando a abstração fizer sentido.
- Regra metodológica: sempre respeitar `data_referencia`, `data_publicacao`, `data_coleta`, data de corte, dados disponíveis naquele momento e prevenção de look-ahead bias.
- Licença: a edição comunitária atual usa fair-code/Apache 2.0 com Commons Clause; tratar como laboratório e não como dependência central de produto comercial sem revisão jurídica/licença vigente.
- Se uma metodologia validada virar funcionalidade central do AgroLog, avaliar implementação própria/permissiva ou licença adequada.

### Integração WhatsApp para Freight Listener

**WPPConnect Server — baseline FL-0 provisório**
- Motivo: a documentação atual declara explicitamente recebimento/envio de mensagens, múltiplas sessões, criação/entrada em grupos, webhook, auto-download de mídia para webhook e opção S3.
- Licença observada: Apache-2.0 padrão no repositório consultado em 17/08/2026.
- Arquitetura: usa WhatsApp Web com Chromium/Puppeteer; isso exige benchmark específico de consumo, reconexão e estabilidade.
- Status: primeiro candidato para teste isolado, sem conta real nesta fase.

**Evolution API — segundo benchmark**
- Pontos fortes: arquitetura multi-provider/event-driven, integração Baileys + WhatsApp Cloud API, filas/eventos e armazenamento de mídia.
- Licença observada: Apache-2.0 com condições adicionais de marca/notificação de uso no arquivo de licença consultado em 17/08/2026.
- Status: comparar após o baseline WPPConnect, especialmente em estabilidade, consumo de recursos, grupos, mídia e recuperação de sessão.

**WAHA — terceiro benchmark**
- Pontos fortes: API REST self-hosted, Docker e múltiplos engines.
- Licença observada: Apache-2.0 no repositório consultado em 17/08/2026.
- Status: manter no benchmark; validar no caso AgroLog os requisitos exatos de grupos, webhooks e mídia antes de promoção na ordem de preferência.

A ordem acima é **provisória e específica do Freight Listener**. A decisão final depende de teste comparável.

Critérios mínimos FL-0:
- receber mensagens de grupo autorizado;
- preservar ID/timestamp do evento;
- entregar evento por webhook/fila;
- receber/baixar mídia sem expor credenciais;
- reconectar após restart/rede;
- medir mensagens perdidas/duplicadas;
- medir consumo de CPU/RAM/disco;
- isolar sessão e credenciais;
- permitir pin de versão e rollback;
- não exigir acesso direto ao BigQuery.

Regras específicas:
- integração deve ficar isolada do núcleo do AgroLog;
- nenhuma sessão, cookie, token ou credencial entra no GitHub;
- revisar licença, termos de uso, estabilidade, segurança, privacidade e compatibilidade antes de produção;
- o módulo começa somente como ingestão/observação: não enviar mensagens, contratar fretes ou negociar automaticamente nesta fase.

### Publicação e produtos de conteúdo

**HyperFrames — camada futura de mídia**
- Uso pretendido: transformar relatórios, gráficos, mapas e roteiros já aprovados em vídeos/explicadores automatizados para comunicação interna ou externa.
- Não participa da geração do dado nem da conclusão analítica; recebe somente conteúdo já validado pelo fluxo editorial.
- Prioridade baixa até existir necessidade real de publicação recorrente em vídeo.

**Markdoc — condicional para portal público**
- Não adotar agora: GitHub atende documentação técnica e Obsidian atende conhecimento interno.
- Reavaliar quando existir portal público/cliente, documentação externa ou experiência editorial que justifique uma camada de publicação web dedicada.

### Engenharia e acesso ao ambiente

**code-server — opcional, fora do AgroLog Core**
- Uso pretendido: acesso ao ambiente de desenvolvimento pelo navegador quando isso resolver uma necessidade operacional concreta.
- Nunca expor diretamente à internet sem autenticação forte, HTTPS e camada de acesso como VPN/IAP/Zero Trust equivalente.
- Credenciais GCP/GitHub e permissões do ambiente devem continuar mínimas e auditáveis.
- Não é requisito para executar o AgroLog; é conveniência de engenharia substituível.

### Expansão operacional futura

**Traccar / Fleetbase**
- Uso pretendido: telemetria/frota autorizada e inteligência operacional complementar, não criação de TMS genérico.

**ThingsBoard / EMQX / ChirpStack**
- Uso pretendido: IoT, sensores, silos, ativos e telemetria futura.

**Ultralytics / OpenCV / Frigate**
- Uso pretendido: provas controladas de visão computacional para contagem/atividade em pátios, vias e ativos.

## Referências permanentes do Radar — estudar, não incorporar como dependência

**TradingAgents**
- Referência para arquitetura de analistas especializados, debate pró/contra, risco, persistência de decisão e consolidação final.
- Não instalar como segunda stack operacional se LangGraph for adotado.

**Vibe-Trading**
- Referência para grounding, proveniência, trilha de auditoria, correção de unidades, testes de look-ahead, backtesting e controles de segurança/correctness.
- Padrões úteis podem inspirar testes e contratos próprios sem importar toda a plataforma.

**Fincept Terminal**
- Benchmark de produto para terminal de inteligência, UX, pesquisa macro, geopolítica, quant, agentes e conectores.
- Não incorporar o código aberto ao produto AgroLog sem revisão específica: a edição aberta atual é AGPL-3.0 strong copyleft e o fornecedor separa uma edição Enterprise proprietária para uso empresarial.

**awesome-quant**
- Catálogo de descoberta para bibliotecas quantitativas, estatísticas e de pesquisa.
- Alimenta o Technology Radar; não é componente de produção.

## Piloto posterior

**Claude Mem**
- Função: memória entre sessões.
- Regra: GitHub e documentação atual prevalecem sobre memória externa.

**Auditoria / doctor do ambiente Claude**
- Função: identificar skills, hooks, plugins e configurações desnecessárias ou quebradas.
- Status: conceito aprovado; implementação específica deve ser validada antes de instalar.

## Futuro

- Strix: testes de segurança controlados em ambiente autorizado.

## Não incorporar ao núcleo agora

- Open WebUI em paralelo com LibreChat.
- Dify como segunda plataforma de produção.
- llama.cpp como servidor paralelo ao Ollama sem necessidade comprovada.
- Markdoc antes de existir portal/documentação externa.
- Fincept Terminal, Vibe-Trading ou TradingAgents como stacks incorporadas; usar como referência.
- Agent Reach.
- OmniRoute e roteadores de muitos modelos.
- Listas de APIs/modelos grátis.
- Task Observer/autoevolução de skills.
- Skills de design sem demanda atual.
- Otimizadores de token/contexto não validados.

## Checklist obrigatório antes de adotar ferramenta externa

1. necessidade concreta e ganho mensurável;
2. licença e permissões de uso;
3. atividade/manutenção do projeto;
4. vulnerabilidades e superfície de ataque;
5. tratamento de credenciais e dados sensíveis;
6. dependências e custo operacional;
7. capacidade de substituição/saída;
8. teste com caso real do AgroLog;
9. comparação com capacidade já existente;
10. documentação da decisão.

## Princípio operacional

Ferramenta nova entra apenas se resolver necessidade concreta sem criar segunda fonte de verdade, duplicar capacidade existente ou ampliar desnecessariamente a complexidade do AgroLog MT.
