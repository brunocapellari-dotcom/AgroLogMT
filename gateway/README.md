# AgroLog Gateway

Primeiro serviço de consulta do AgroLog MT sobre a view `logistica.vw_armazens_atuais` no BigQuery.

Escopo inicial: somente leitura, filtros controlados, limite de resultados, Cloud Run e identidade com privilégio mínimo.

Variáveis: `GCP_PROJECT`, `BQ_LOCATION` e opcionalmente `BQ_ARMAZENS_VIEW`.

Endpoints iniciais previstos: `GET /healthz` e `GET /v1/armazens`.

Critério do piloto: consultar a view real, validar resposta, registrar erros e testar a mesma consulta via OpenAI/Codex e Claude.