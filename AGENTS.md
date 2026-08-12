# AGENTS.md — Regras canônicas para agentes de IA

Este arquivo é a fonte canônica de instruções para qualquer agente que trabalhe neste repositório. Em caso de conflito com instruções de um provedor, este arquivo prevalece.

## 1. Fontes de verdade

1. **BigQuery**: fonte única de verdade para dados analíticos em produção.
2. **GitHub**: fonte única de verdade para código, schemas, SQL, documentação e configuração versionada.
3. **Issues**: fonte de verdade para escopo e estado de cada tarefa.
4. **Pull Requests**: proposta de alteração; só vira verdade após revisão e merge.

Nunca criar uma segunda implementação, schema, documento ou configuração para resolver algo que já possui arquivo canônico. Antes de criar arquivo novo, pesquise o repositório e prefira melhorar o existente.

## 2. Regra anti-sobreposição

Antes de editar:
- leia a Issue da tarefa e os PRs abertos relacionados;
- pesquise por arquivos, funções, tabelas, views e documentos equivalentes;
- identifique o arquivo canônico a ser alterado;
- pare e reporte se houver outro agente trabalhando no mesmo escopo ou nos mesmos arquivos.

Não duplicar lógica entre `collector/`, `historical/`, `imea/`, `gateway/` ou `sql/`. Não manter duas versões concorrentes da mesma regra de negócio.

## 3. Fluxo obrigatório

- Não trabalhar diretamente em `main`.
- Uma tarefa = uma Issue com escopo explícito.
- Uma implementação = uma branch e um PR vinculados à Issue.
- Alterar somente os caminhos necessários ao escopo.
- Todo PR deve informar qual agente/modelo foi usado, arquivos revisados antes da edição, testes executados e limitações conhecidas.
- Merge final é humano.

## 4. Arquitetura que deve ser preservada

- BigQuery para histórico e inteligência analítica.
- Cloud Run como camada de serviços.
- AgroLog Gateway como API/MCP de acesso controlado.
- OpenAI/ChatGPT, Claude e outros agentes consultam a mesma base central; não criar bancos separados por IA.
- PostgreSQL fica reservado para eventual camada transacional futura.
- Evoluir a V3 incrementalmente; não redesenhar do zero sem decisão registrada.

## 5. Governança de dados

Quando aplicável, preservar: `data_referencia`, `data_publicacao`, `data_coleta` e `competencia`.

Classificar claramente informação como: dado observado, inferência, estimativa ou informação negociada/autorizada. Nunca apresentar estimativa como dado observado.

## 6. Segurança e versionamento

Nunca commitar credenciais, tokens, cookies, senhas, chaves de serviço, `.env`, RAW pesado, exports operacionais ou bases históricas que pertençam ao BigQuery/armazenamento de dados. Respeitar `.gitignore`.

## 7. Qualidade

- Preserve compatibilidade com os contratos existentes.
- Execute testes, lint/validações disponíveis antes de concluir.
- Se um teste não puder ser executado, explique o motivo no PR.
- Mudanças em schema/SQL devem documentar impacto de deduplicação, particionamento, clustering e histórico.

## 8. Papéis dos agentes

Consulte `docs/AI_ROLES.md`. Arquivos específicos de provedor devem apenas apontar para estas regras; não devem criar políticas paralelas.
