# Bootstrap compartilhado — ChatGPT/Codex + Claude Code

Este diretório contém o pacote de código preparado para colocar ChatGPT/Codex e Claude Code sobre a mesma base versionada.

## Conteúdo do pacote
`agrolog_code_bootstrap.tar.gz` contém somente código, SQL, schemas, configurações, testes e documentação selecionados dos módulos atuais:

- governança multiagente;
- templates de Issue/PR e quality gates;
- fonte CONAB (coletor v1.2.2 e componentes de BigQuery/Armazéns);
- fonte IMEA (candidato pré-produção v1.2);
- parsers, schemas e SQL associados.

Arquivos pesados de dados, planilhas operacionais, históricos comprimidos e credenciais foram deliberadamente excluídos. O BigQuery permanece como fonte de verdade analítica.

## Para Claude Code
Na raiz de uma branch criada a partir deste PR/merge:

```bash
tar -xzf bootstrap/agrolog_code_bootstrap.tar.gz
```

Depois:
1. revise os arquivos extraídos e eventuais conflitos;
2. não substitua decisões mais novas já existentes em `docs/`;
3. execute os testes pertinentes antes de qualquer merge;
4. mantenha dados pesados e segredos fora do GitHub;
5. siga a Issue #3 e abra PR para integrar o código extraído.

## Prioridade
A primeira execução real continua sendo CONAB Armazéns ponta a ponta contra o BigQuery real, com validação de carga, logs, deduplicação e consulta. IMEA entra na sequência após essa validação e a primeira integração do AgroLog Gateway.
