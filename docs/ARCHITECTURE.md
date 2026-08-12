# Arquitetura do AgroLog MT

## Visão geral

O AgroLog MT usa uma arquitetura analítica centralizada.

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
5. **Camada de inteligência**
   - OpenAI/ChatGPT;
   - Claude;
   - futuros consumidores autorizados.

## Regras estruturais

- Não manter bases separadas por IA.
- Não criar dezenas de tabelas vazias antecipadamente.
- Criar datasets/tabelas conforme a fonte entra em produção.
- PostgreSQL somente se surgir necessidade transacional real.
- Toda nova fonte deve entrar com documentação de origem, frequência, granularidade, cobertura, limitações e classificação do tipo de evidência.
