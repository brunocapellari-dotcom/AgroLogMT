---
tipo: painel
status: vigente
ultima_revisao: 2026-08-12
---

# Próximas Ações

1. Executar [[Pipeline - CONAB Armazens]] ponta a ponta no BigQuery real.
2. Validar logs, snapshots, deduplicação, DQ e reexecução idempotente.
3. Conectar a primeira consulta ao [[AgroLog Gateway]].
4. Testar a mesma consulta via OpenAI/ChatGPT e Claude.
5. Implantar IMEA indicadores e fretes a partir dos manifests existentes.
6. Localizar/materializar CSV completo do [[Comex Stat]] para armazenamento externo e carga.
7. Implantar Portos/line-up separando programação e realizado.
8. Implantar ANP por domínio/cadência, começando por diesel semanal.
9. Consolidar NOAA/INMET/ANA com freshness e alertas de falha.
10. Só depois de fontes estáveis, ativar Scheduler produtivo.

## Intervenção humana ainda necessária

- executar/autorizar a implantação real no Google Cloud quando Claude Code estiver pronto;
- fornecer/autorizar credenciais restritas apenas quando uma fonte exigir, sem versioná-las no GitHub;
- decidir sobre conflitos de licença/acesso que não possam ser resolvidos tecnicamente.
