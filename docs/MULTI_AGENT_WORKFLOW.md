# Fluxo Multiagente — AgroLog MT

## Componentes permanentes

- ChatGPT/OpenAI: governança, GitHub, arquitetura e coordenação.
- Claude Code: executor principal no notebook, testes, terminal e GCP/BigQuery.
- Codex: revisor técnico independente e segundo agente de engenharia.
- Obsidian: Segundo Cérebro para conhecimento técnico, histórico e relações causais.

## Fontes de verdade

- GitHub: código, SQL, schemas, testes e documentação.
- BigQuery: dados analíticos estruturados.
- RAW/Drive/Cloud Storage: arquivos originais.
- Obsidian: conhecimento derivado e memória histórica.

## Fluxo padrão

1. Claude lê a governança e prepara um plano.
2. Codex revisa o plano via MCP.
3. Claude implementa a menor mudança coerente.
4. Claude executa testes.
5. Codex revisa o diff final.
6. ChatGPT consolida governança e GitHub quando necessário.
7. A mudança é validada no ambiente real.

Um agente implementa; o outro revisa. Não criar loops entre agentes nem fontes de verdade paralelas.

## Configuração local

O repositório inclui `.mcp.json` para expor Codex ao Claude Code usando o comando `codex mcp-server`. A instalação e autenticação do Codex devem ser feitas localmente no notebook. Depois, validar a integração com `claude mcp list` e `claude mcp get codex`.

## Critério de uso

Revisão Codex é esperada para mudanças materiais em schemas, SQL de merge, BigQuery, idempotência, Gateway, autenticação, permissões e migrações. Revisão de segundo modelo não substitui testes executáveis.
