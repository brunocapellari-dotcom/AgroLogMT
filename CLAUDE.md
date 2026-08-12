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

## Bootstrap de código
O pacote `bootstrap/agrolog_code_bootstrap.tar.gz` contém o código-fonte e a governança preparados por ChatGPT para CONAB e IMEA. Antes de implementar a próxima etapa, leia `bootstrap/README.md` e extraia o pacote em uma branch de trabalho, preservando os arquivos existentes do repositório e revisando conflitos antes do commit.
