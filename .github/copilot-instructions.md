# Instruções para GitHub Copilot

Leia e siga integralmente `/AGENTS.md` antes de qualquer alteração.

Pontos obrigatórios:
- não editar `main` diretamente;
- confirmar a Issue e o escopo antes de modificar arquivos;
- pesquisar o repositório para evitar duplicação;
- preservar BigQuery como fonte única de verdade analítica;
- não criar política, schema ou lógica paralela;
- trabalhar em branch própria e abrir PR;
- executar os testes/validações disponíveis;
- registrar no PR agente/modelo usado, arquivos impactados, testes e limitações;
- não commitar credenciais, tokens, `.env`, RAW pesado ou bases históricas.

Papéis e critérios de revisão: `docs/AI_ROLES.md`.
