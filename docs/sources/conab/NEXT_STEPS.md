# CONAB — próximos passos após o piloto de Armazéns

O piloto histórico de Armazéns foi aprovado em 2026-08-13. A sequência operacional é:

1. **AgroLog Gateway** — conectar leitura controlada da primeira tabela validada e testar a mesma consulta via OpenAI/Codex e Claude.
2. **Coleta oficial ao vivo de Armazéns** — baixar `ArmazensCadastrados.txt` da fonte oficial, preservar RAW, transformar, aplicar circuit breaker e comparar com o snapshot atual.
3. **Workflow de QUARENTENA** — implementar revisão/aprovação explícita de saltos legítimos; nunca promover automaticamente um snapshot suspeito.
4. **Cloud Storage RAW** — migrar preservação RAW para armazenamento imutável/versionado do projeto antes da automação.
5. **Cloud Run Job** — service account dedicada, mínimo privilégio, execução manual aprovada antes de agendar.
6. **Cloud Scheduler e alertas** — somente após Cloud Run manual estável; falha e QUARENTENA devem gerar alerta.
7. **Carga histórica CONAB completa** — ativar as demais 20 tabelas gradualmente, validando cada família no BigQuery real e repetindo a carga para idempotência.
8. **Expansão das fontes CONAB** — ativar famílias estruturadas e documentais sem misturar RAW com CORE.

A expansão não deve bloquear o desenvolvimento do Gateway: ambos podem avançar em paralelo quando suas dependências estiverem satisfeitas.
