# CLAUDE.md — AgroLog MT

Antes de alterar código, leia:
- `docs/ARCHITECTURE.md`
- `docs/DATA_GOVERNANCE.md`
- `docs/BACKLOG.md`
- `bootstrap/README.md`

Regras essenciais:
- Trabalhe sobre o estado atual do repositório; não redesenhe do zero sem necessidade.
- Preserve compatibilidade com BigQuery e Cloud Run.
- Nunca versione credenciais, tokens ou arquivos brutos pesados.
- Diferencie dado observado, inferência, estimativa e informação negociada/autorizada.
- Antes de remover ou renomear tabelas/campos, procure todas as referências no repositório.
- BigQuery é a fonte única de verdade analítica; GitHub guarda código, SQL, schemas, testes e documentação.
- A prioridade atual é CONAB Armazéns ponta a ponta no BigQuery real; depois conectar a primeira consulta ao AgroLog Gateway e validar via OpenAI e Claude.

## Trabalho compartilhado
Este repositório é o ponto de sincronização entre ChatGPT/Codex e Claude Code. Claude deve trabalhar sempre a partir do repositório/branch atual e enviar mudanças por Pull Request. Não use ZIPs do repositório como fonte de verdade; o código deve existir como arquivos Git normais.
