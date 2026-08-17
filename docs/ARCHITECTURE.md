# Arquitetura do AgroLog MT

## Visão geral

O AgroLog MT usa uma arquitetura analítica centralizada com camadas distintas para dados, engenharia, inteligência e conhecimento.

A evolução derivada do Radar GitHub passa a ser tratada como **três frentes integradas da mesma arquitetura**, e não como três arquiteturas separadas ou substituições do núcleo atual:

- **Frente A — coleta, documentos e qualidade**;
- **Frente B — inteligência, conhecimento e observabilidade**;
- **Frente C — expansão operacional e comercial**.

Essas frentes podem ser especificadas e desenvolvidas em paralelo, mas novas fontes e integrações reais só entram em produção após os critérios de qualidade, segurança e governança aplicáveis. BigQuery, GitHub, RAW/Drive/Cloud Storage, AgroLog Gateway e Obsidian mantêm suas responsabilidades canônicas.

## Camadas

1. **Fontes externas**
   - CONAB, IMEA, CEPEA, Comex Stat, ANTAQ, ANTT, ANP, USDA, NOAA, INMET e demais fontes homologadas;
   - páginas, portais, arquivos, APIs e canais autorizados de comunicação;
   - dados operacionais autorizados de clientes em etapas futuras.

2. **Aquisição e monitoramento de fontes**
   - coletores específicos por fonte;
   - APIs e conectores padronizados quando disponíveis;
   - navegação controlada com Playwright/browser automation quando uma fonte não possuir API adequada;
   - gatilhos/orquestração de coleta com ferramenta de automação aprovada;
   - detecção de nova publicação, versão, hash, alteração de página ou novo artefato;
   - processamento por diferença quando a publicação recorrente permitir.

3. **Inteligência documental e multimodal**
   - extração de texto, tabelas e metadados de PDFs e documentos;
   - extração estruturada de imagens/tabelas por pipeline multimodal aprovado;
   - classificação do conteúdo antes de qualquer persistência analítica;
   - preservação do artefato original no armazenamento RAW apropriado, nunca no GitHub.

4. **Staging, normalização, qualidade e linhagem**
   - validação de esquema;
   - normalização determinística sempre que possível;
   - deduplicação e resolução de entidades;
   - detecção de anomalias, quebra de série, mudança de unidade e inconsistência temporal;
   - registro de versão do coletor, origem, artefato, hash e transformações aplicadas;
   - bloqueio de publicação automática quando a confiança ou a qualidade estiver abaixo do limite definido.

5. **BigQuery**
   - fonte única de verdade analítica;
   - tabelas criadas sob demanda;
   - particionamento por `data_referencia` quando aplicável;
   - clustering conforme chaves de consulta relevantes;
   - dados observados, inferidos, estimados e negociados/autorizados permanecem explicitamente distinguíveis.

6. **AgroLog Gateway**
   - serviço em Cloud Run;
   - API/MCP própria;
   - permissões mínimas;
   - logs de acesso;
   - sem exposição direta do banco;
   - camada obrigatória para disponibilização controlada de consultas e, futuramente, produtos externos.

7. **Camada de conhecimento e recuperação**
   - Obsidian como Segundo Cérebro permanente do projeto;
   - preserva conhecimento técnico, histórico e contextual;
   - não substitui GitHub nem BigQuery;
   - uma camada RAG/vetorial pode indexar conhecimento e evidências para recuperação semântica, desde que não se torne nova fonte de verdade;
   - respostas de IA devem conseguir apontar a evidência e a origem usadas.

8. **Agentes de inteligência e engenharia**
   - ChatGPT/OpenAI: coordenação, governança e manutenção do GitHub;
   - Claude Code: executor principal no notebook, testes e operações GCP/BigQuery;
   - Codex: segundo agente de engenharia e revisor técnico independente, integrado ao Claude Code por MCP quando disponível;
   - agentes analíticos devem operar sobre ferramentas e contratos explícitos, com permissões limitadas e trilha de auditoria;
   - previsões relevantes devem ser persistidas para comparação posterior entre previsto e realizado.

9. **BI, observabilidade e geointeligência**
   - BI analítico para exploração de dados e indicadores;
   - observabilidade técnica separada da camada de BI de negócio;
   - geointeligência para rotas, armazenagem, indústria, rodovias, ferrovias, hidrovias, portos e fluxos;
   - componentes específicos só entram após validação de licença, segurança, manutenção e benefício real.

10. **Expansão operacional e comercial**
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
