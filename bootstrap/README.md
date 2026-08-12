# Sincronização ChatGPT/Codex + Claude Code

O GitHub é o repositório compartilhado do AgroLog MT. BigQuery permanece como fonte única de verdade analítica.

## Regra operacional
- código, SQL, schemas, configurações, testes e documentação: GitHub;
- dados pesados, históricos, planilhas operacionais e credenciais: fora do GitHub;
- cada agente trabalha em branch própria e integra por Pull Request;
- Claude Code deve clonar/abrir este repositório diretamente e consumir o estado atual do Git, sem depender de pacotes compactados.

## Estado atual
A camada de arquitetura e governança está no repositório. Os módulos de código que ainda estiverem somente no workspace do Claude Code devem ser migrados para arquivos Git normais, preservando a estrutura e as decisões existentes.

## Prioridade
1. consolidar no Git a árvore de código que o Claude Code já está usando;
2. executar CONAB Armazéns ponta a ponta contra o BigQuery real;
3. validar carga, logs, deduplicação e consulta;
4. conectar a primeira tabela ao AgroLog Gateway;
5. testar a mesma consulta via OpenAI e Claude;
6. somente depois expandir novas fontes, começando pelo IMEA.
