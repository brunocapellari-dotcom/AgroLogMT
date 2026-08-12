# CLAUDE.md — AgroLog MT

Antes de alterar código, leia nesta ordem:
- `docs/MANIFESTO.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_GOVERNANCE.md`
- `docs/REPOSITORY_GOVERNANCE.md`
- `docs/REPORTS.md`
- `docs/AGENTS.md`
- `docs/AUTOMATIONS.md`
- `docs/AI_TOOLING.md`
- `docs/BACKLOG.md`
- `config/manifesto.yaml`
- `config/sources.yaml`
- `bootstrap/README.md`

A decisão explícita mais recente registrada no repositório prevalece sobre documento legado conflitante. O nome oficial do produto é **AgroLog MT**; nomes técnicos legados contendo `360` podem permanecer apenas por compatibilidade.

Regras essenciais:
- Trabalhe sobre o estado atual do repositório; não redesenhe do zero sem necessidade.
- Antes de criar arquivo, módulo, schema, SQL, configuração ou documento, pesquise se já existe responsabilidade equivalente.
- Prefira atualizar, estender ou refatorar a fonte canônica existente a criar uma segunda implementação.
- Se houver duas definições concorrentes, identifique a fonte canônica antes de continuar.
- Preserve compatibilidade com BigQuery e Cloud Run.
- Nunca versione credenciais, tokens ou arquivos brutos pesados.
- Nomes de fontes como CONAB, IMEA, CEPEA, Comex Stat, ANTAQ, ANP e USDA identificam responsabilidades de código; não autorizam armazenar os datasets reais dessas fontes no GitHub.
- Código, parsers, schemas, SQL, configurações sem segredo, testes, prompts, documentação e `knowledge/` pertencem ao GitHub; dados reais/RAW, planilhas, ZIPs, PDFs e históricos pesados ficam em armazenamento externo.
- Google Cloud Storage preserva o raw automatizado imutável; Google Drive preserva documentação, relatórios, arquivos manuais e bases resumidas; BigQuery é a fonte única de verdade analítica.
- O diretório `knowledge/` é o Vault lógico do Obsidian. GitHub é a fonte canônica dos Markdown; não criar uma cópia concorrente do Vault no Drive.
- Testes que dependam de dados reais devem receber caminho externo/configurável. Não copie dados reais para dentro do repositório só para fazer o teste passar.
- Fixtures pequenos e artificiais podem permanecer em `tests/fixtures/` quando necessários.
- Diferencie `OBSERVADO`, `DECLARADO`, `INFERIDO`, `ESTIMADO`, `PROJETADO` e `NEGOCIADO_CONFIRMADO`.
- Antes de remover ou renomear tabelas/campos, procure todas as referências no repositório e prepare migração/rollback.
- BigQuery é a fonte única de verdade analítica; não migrar o warehouse para Supabase/PostgreSQL sem nova decisão formal.
- Quando aplicável, preserve `data_referencia`, `data_publicacao`, `data_coleta` e `competencia`.
- Não criar dezenas de tabelas vazias antecipadamente; criar sob demanda conforme cada fonte entrar em produção.
- Preferir particionamento por `data_referencia` e clustering pelas chaves reais de consulta.
- Cargas devem usar staging + MERGE/append conforme contrato, ser idempotentes e preservar histórico.
- Ausência de um cadastro no snapshot atual não significa exclusão automática.
- Nunca afirmar frete real pago, disponibilidade real de caminhão, contratação individual ou volume por trading usando somente bases públicas.
- Gado de corte não entra no relatório agrícola/logístico principal em nenhuma forma.
- ABIOVE/esmagamento mensal não vira seção semanal fixa; obedecer `docs/REPORTS.md`.
- Scheduler produtivo só entra depois de fontes reais estáveis com DQ, logs, alertas, IAM mínimo, idempotência e custo monitorado.
- A prioridade atual é CONAB Armazéns ponta a ponta no BigQuery real; depois AgroLog Gateway, IMEA, Comex, Portos e ANP.

## Método de trabalho

Para mudanças não triviais:
1. inspecione a árvore e os arquivos relacionados;
2. descreva um plano curto antes de implementar;
3. implemente a menor mudança coerente possível;
4. execute ou proponha testes adequados;
5. revise o diff e procure duplicação, regressão e conflito de contrato;
6. atualize documentação/knowledge quando schema, pipeline, status, endpoint ou metodologia mudarem;
7. só então considere a tarefa concluída.

Esse método é obrigatório mesmo quando uma skill externa estiver instalada. Skills complementam estas regras; não as substituem.

## Organização por fonte

- Não crie diretórios vazios apenas para antecipar fontes futuras.
- Quando uma fonte entrar em implementação, seu pacote deve declarar origem, granularidade, schema, chave natural, particionamento, clustering, estratégia de carga, DQ, dependências e critério de aceite.
- Preserve componentes compartilhados quando a regra for comum a várias fontes; não replique a mesma lógica apenas por organização visual.
- Se a implementação existente já possuir uma estrutura funcional, adapte-a incrementalmente em vez de mover arquivos apenas para seguir um desenho teórico.
- Estado `PRONTO_PARA_CLAUDE_CODE` não significa `INTEGRADA`. Só marcar produção após carga real, logs, DQ, consulta e idempotência comprovados.

## Skills e ferramentas externas

- Não instale automaticamente skills, plugins, hooks ou MCPs encontrados em catálogos.
- Consulte `docs/AI_TOOLING.md` antes de adotar qualquer ferramenta externa.
- Ferramenta não registrada como aprovada/piloto deve ser tratada como não autorizada até revisão.
- Memória externa nunca prevalece sobre o conteúdo atual do GitHub.
- Nenhum agente pode alterar autonomamente estas regras ou instalar mecanismos de autoevolução sem revisão explícita.

## Trabalho compartilhado

Este repositório é o ponto de sincronização entre ChatGPT/OpenAI e Claude Code.

- ChatGPT/OpenAI mantém governança, requisitos, semântica, pacotes determinísticos e validação funcional.
- Claude Code implementa/refatora, testa e executa mudanças técnicas no Google Cloud a partir do repositório/branch atual.
- Claude deve melhorar o que já existe, não criar uma segunda fonte de verdade concorrente.
- Gemini pode atuar futuramente como validador independente/pesquisador/multimodal sobre os mesmos contratos e dados curados.
- Não use ZIPs do repositório como fonte de verdade; o código deve existir como arquivos Git normais.
- Quando houver dúvida entre criar algo novo e melhorar o existente, analisar e melhorar o existente primeiro.
- Mudanças de governança ou significado econômico exigem registro explícito e decisão humana.
