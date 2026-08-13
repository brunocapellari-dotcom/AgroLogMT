# Arquitetura do AgroLog MT

## Visão geral

O AgroLog MT usa uma arquitetura analítica centralizada com camadas distintas para dados, engenharia, inteligência e conhecimento.

### Camadas

1. **Fontes externas**
   - CONAB, IMEA, CEPEA, Comex Stat, ANTAQ, ANTT, ANP, USDA, NOAA, INMET e demais fontes homologadas.
2. **Coleta e normalização**
   - coletores específicos por fonte;
   - validação de esquema;
   - deduplicação;
   - registro de coleta e qualidade.
3. **BigQuery**
   - fonte única de verdade analítica;
   - tabelas criadas sob demanda;
   - particionamento por `data_referencia` quando aplicável;
   - clustering conforme chaves de consulta relevantes.
4. **AgroLog Gateway**
   - serviço em Cloud Run;
   - API/MCP própria;
   - permissões mínimas;
   - logs de acesso;
   - sem exposição direta do banco.
5. **Agentes de inteligência e engenharia**
   - ChatGPT/OpenAI: coordenação, governança e manutenção do GitHub;
   - Claude Code: executor principal no notebook, testes e operações GCP/BigQuery;
   - Codex: segundo agente de engenharia e revisor técnico independente, integrado ao Claude Code por MCP quando disponível.
6. **Camada de conhecimento**
   - Obsidian como Segundo Cérebro permanente do projeto;
   - preserva conhecimento técnico, histórico e contextual;
   - não substitui GitHub nem BigQuery.

## Fontes de verdade por responsabilidade

- GitHub: código, SQL, schemas, testes, configuração sem segredo, contratos e documentação do sistema.
- BigQuery: dados estruturados e histórico analítico oficial.
- RAW/Drive/Cloud Storage: arquivos originais e documentos de fonte.
- Obsidian: conhecimento derivado, contexto, relações e memória histórica.

## Regras estruturais

- Não manter bases separadas por IA.
- Não criar fontes concorrentes entre GitHub, BigQuery e Obsidian.
- Não criar dezenas de tabelas vazias antecipadamente.
- Criar datasets/tabelas conforme a fonte entra em produção.
- PostgreSQL somente se surgir necessidade transacional real.
- Toda nova fonte deve entrar com documentação de origem, frequência, granularidade, cobertura, limitações e classificação do tipo de evidência.
- Revisão por segundo agente não substitui testes executáveis.
