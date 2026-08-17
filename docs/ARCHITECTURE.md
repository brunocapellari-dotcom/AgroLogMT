# Arquitetura do AgroLog MT

## Visão geral

O AgroLog MT usa uma arquitetura analítica centralizada com camadas distintas para dados, engenharia, inteligência e conhecimento.

### Camadas

1. **Fontes externas**
   - CONAB, IMEA, CEPEA, Comex Stat, ANTAQ, ANTT, ANP, USDA, NOAA, INMET e demais fontes homologadas.
2. **Orquestração operacional**
   - n8n como camada de coordenação de workflows quando aprovado para produção;
   - responsável por agenda, gatilhos, encadeamento, monitoramento e alertas;
   - não deve concentrar lógica de negócio, normalização, regras analíticas ou segredos versionados;
   - collectors, parsers, validadores e transformações permanecem em código versionado e executável independentemente do n8n;
   - primeiro piloto: CONAB Armazéns, conforme Issue #36.
3. **Coleta e normalização**
   - coletores específicos por fonte;
   - validação de esquema;
   - deduplicação;
   - registro de coleta e qualidade.
4. **BigQuery**
   - fonte única de verdade analítica;
   - tabelas criadas sob demanda;
   - particionamento por `data_referencia` quando aplicável;
   - clustering conforme chaves de consulta relevantes;
   - pode armazenar telemetria operacional de automações e estado das fontes, desde que separada dos dados analíticos de domínio.
5. **AgroLog Gateway**
   - serviço em Cloud Run;
   - API/MCP própria;
   - permissões mínimas;
   - logs de acesso;
   - sem exposição direta do banco.
6. **Agentes de inteligência e engenharia**
   - ChatGPT/OpenAI: coordenação, governança e manutenção do GitHub;
   - Claude Code: executor principal no notebook, testes e operações GCP/BigQuery;
   - Codex: segundo agente de engenharia e revisor técnico independente, integrado ao Claude Code por MCP quando disponível.
7. **Camada de conhecimento**
   - Obsidian como Segundo Cérebro permanente do projeto;
   - preserva conhecimento técnico, histórico e contextual;
   - não substitui GitHub nem BigQuery.

## Fluxo operacional de referência

Fonte externa → n8n/gatilho operacional → collector/serviço versionado → validação → BigQuery → logs/alertas → AgroLog Gateway/agentes.

O n8n deve poder ser removido ou ficar indisponível sem tornar o collector inexequível. O mesmo pipeline deve possuir caminho manual ou programático independente para reprocessamento, depuração e recuperação.

## Fontes de verdade por responsabilidade

- GitHub: código, SQL, schemas, testes, configuração sem segredo, contratos e documentação do sistema.
- BigQuery: dados estruturados e histórico analítico oficial.
- RAW/Drive/Cloud Storage: arquivos originais e documentos de fonte.
- Obsidian: conhecimento derivado, contexto, relações e memória histórica.
- n8n: estado transitório de orquestração; nunca é fonte canônica de dados, regras ou conhecimento.

## Observabilidade operacional

A automação deve registrar evidência suficiente para reconstruir cada execução. O piloto de orquestração deve avaliar estruturas equivalentes a:

- `ops.automation_runs`: execução, workflow, fonte, início/fim, status, contagens, erro e referência ao artefato/processamento;
- `ops.source_status`: fonte, últimas datas de referência/publicação/coleta, próxima atualização esperada e status.

Essas estruturas só devem ser criadas quando a implementação entrar em uso real; não criar tabelas vazias antecipadamente apenas por desenho teórico.

## Regras estruturais

- Não manter bases separadas por IA.
- Não criar fontes concorrentes entre GitHub, BigQuery e Obsidian.
- Não criar dezenas de tabelas vazias antecipadamente.
- Criar datasets/tabelas conforme a fonte entra em produção.
- PostgreSQL somente se surgir necessidade transacional real.
- Toda nova fonte deve entrar com documentação de origem, frequência, granularidade, cobertura, limitações e classificação do tipo de evidência.
- Revisão por segundo agente não substitui testes executáveis.
- Workflows de n8n devem orquestrar componentes versionados, não duplicar lógica de negócio em nós visuais.
- Credenciais e segredos devem permanecer em mecanismo apropriado de secrets/credenciais; nunca no GitHub ou em exportações de workflow sem proteção.
