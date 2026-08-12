# Automações, APIs e collectors — AgroLog MT

## Fluxo universal

1. Consultar somente fonte oficial, licenciada ou canal autorizado.
2. Identificar última versão aceita e data de referência/publicação.
3. Comparar versão, hash, tamanho e metadados.
4. Se não houver mudança, registrar `NO_CHANGE`.
5. Se houver atualização, preservar bruto imutável no GCS antes de transformar.
6. Validar schema, contagens, datas, chaves, unidades e anomalias.
7. Carregar staging no BigQuery.
8. Comparar com versão anterior/snapshot.
9. Executar DQ.
10. Executar MERGE/append conforme contrato.
11. Registrar recebidos, novos, alterados, inalterados, ausentes e erros.
12. Atualizar views e indicadores somente após carga aprovada.
13. Atualizar documentação/knowledge quando schema, status, endpoint ou metodologia mudarem.

## Classes de acesso

- API pública;
- API com token/chave;
- download estruturado;
- login autorizado;
- consulta/evento com snapshots;
- entrada manual;
- dados internos autorizados.

Credenciais ficam em Secret Manager/variáveis seguras. Nunca no GitHub, logs ou notas Obsidian.

## Bloqueios

Não contornar login, CAPTCHA, paywall, 403 ou restrição de licença. Quando o acesso automatizado não for permitido, adotar download manual autorizado + ingestão automática.

## Alertas obrigatórios do collector

- falha HTTP/autenticação;
- endpoint indisponível;
- mudança de schema/cabeçalho;
- variação anormal na contagem;
- atraso de referência/publicação em relação ao SLA;
- chave natural incompleta;
- duplicidade fora do padrão;
- revisão retroativa material;
- divergência com fonte de conciliação;
- carga parcial, bloqueada ou com erro.

## Scheduler

Não ativar Scheduler produtivo enquanto não houver pelo menos 4–5 fontes reais estáveis com:

- idempotência comprovada;
- DQ;
- logs;
- alertas;
- IAM mínimo;
- custo monitorado;
- rollback/reprocessamento validado.

## Cadências de referência

- CONAB safra: calendário oficial, normalmente mensal durante a safra.
- IMEA: semanal/mensal/safra conforme indicador.
- CEPEA: mercado diário, consolidação para o semanal.
- USDA WASDE: mensal; Crop Progress: semanal na temporada.
- Comex Stat: mensal.
- ANTAQ: mensal.
- line-up crítico: diário/evento.
- ANP diesel: semanal; demais conjuntos: conforme publicação, frequentemente mensal.
- NOAA/INMET: horário/diário conforme série.
- ANA: horário/diário conforme estação.
- IBGE LSPA: mensal; PAM/PPM/PEVS: anual.
- BCB PTAX/SGS: frequência da série; Focus: semanal.
- SAPCANA/UNICA: quinzenal conforme divulgação; UNEM: mensal/eventual/safra.

A automação deve verificar a publicação real e não criar atualização artificial apenas porque chegou a data do calendário.
