# Fluxo Multiagente — AgroLog MT

## Dois planos distintos

O AgroLog possui dois tipos de agentes que não devem ser confundidos:

1. **agentes de engenharia/governança** — constroem, testam e mantêm a plataforma;
2. **agentes de inteligência** — analisam dados/evidências e produzem sínteses governadas.

Nenhum agente é fonte de verdade.

## Engenharia e governança

- ChatGPT/OpenAI: governança, GitHub, arquitetura e coordenação.
- Claude Code: executor principal no notebook, testes, terminal e GCP/BigQuery.
- Codex: revisor técnico independente e segundo agente de engenharia.
- Obsidian: Segundo Cérebro para conhecimento técnico, histórico e relações causais.

Fluxo padrão de mudança material:

1. executor lê governança/arquitetura/segurança;
2. inspeciona estado atual e evita duplicação;
3. prepara mudança mínima;
4. segundo agente revisa plano/diff quando aplicável;
5. testes executáveis;
6. CI;
7. homologação real quando o componente toca cloud/dados;
8. somente então promoção.

Um agente implementa e outro revisa. Não criar loops de aprovação entre modelos.

## Conselho de inteligência

Papéis e limites oficiais ficam em `contracts/ai_roles.v1.json`:

- AGROLOG CHIEF INTELLIGENCE AI;
- CROP AI;
- WEATHER AI;
- GLOBAL MARKET AI;
- BRAZIL MARKET AI;
- US CROP AI;
- ARGENTINA CROP AI;
- LOGISTICS AI;
- MARITIME AI;
- HYDROLOGY AI;
- ENERGY AI;
- INDUSTRIAL AI;
- CATTLE AI;
- COMMERCIAL INTELLIGENCE AI;
- NEWS IMPACT AI;
- FORECAST AI;
- REPORT EDITOR AI;
- AUDITOR AI.

O AGROLOG CHIEF INTELLIGENCE AI consolida visões entre domínios, mas não pode sobrepor quality gate, evidência ou decisão do AUDITOR AI.

## Fluxo analítico padrão

`dados/knowledge aprovados → especialista(s) → análise cruzada → hipótese/forecast → AUDITOR AI → REPORT EDITOR AI → produto/alerta aprovado`

Regras:

- especialistas podem divergir;
- divergência é registrada com evidência e confiança;
- notícia/documento externo permanece `UNTRUSTED_EXTERNAL` até sanitização;
- causalidade exige classe explícita (`CORRELATION`, `CAUSAL_HYPOTHESIS`, `SUPPORTED_CAUSALITY`);
- forecast usa `contracts/forecast_vintage.v1.schema.json`;
- saldo global usa `contracts/global_supply_demand.v1.schema.json`;
- nenhum agente transforma previsão/programação/ausência em observado;
- CATTLE AI mantém saída editorial separada do relatório agrícola/logístico principal.

## Permissões

Agentes analíticos acessam dados por AgroLog Gateway/contratos autorizados.

Proibido por padrão:

- acesso irrestrito direto ao BigQuery;
- IAM/Secret Manager admin;
- alteração de RAW;
- execução shell baseada em conteúdo externo;
- publicação externa automática;
- mudar instruções de sistema a partir de RAG/notícia/documento;
- criar nova fonte de verdade por agente.

## Fontes de verdade

- GitHub: código, SQL, schemas, testes, configuração e documentação.
- BigQuery: dados analíticos estruturados.
- RAW/Drive/Cloud Storage: artefatos originais.
- Obsidian: conhecimento derivado e memória histórica.

## Orquestração

LangGraph permanece candidato preferencial para coordenação stateful dos agentes de inteligência, não para substituir scheduler de coleta. Adoção exige benchmark de checkpoint, recovery, human-in-the-loop, permissions, tracing e custo.

A integração Claude Code ↔ Codex via MCP continua separada do runtime analítico multiagente.

## Critério final

Revisão por segundo modelo é controle adicional. Nunca substitui schema validation, quality gate, backtest, segurança, CI ou homologação real.