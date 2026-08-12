# Bootstrap V3 — CONAB + IMEA

Este bootstrap preserva os pacotes já validados do AgroLog MT e organiza o repositório sem redesenhar a V3.

## Artefatos-fonte

- CONAB Collector v1.2.2
- CONAB BigQuery Historical Package v2.3
- IMEA Agro v1.2 — candidato de pré-produção
- GitHub Governance v3

## Política de versionamento

O GitHub recebe código, configuração, schemas, SQL, testes e documentação. Bases históricas, snapshots, exports operacionais, arquivos brutos e credenciais ficam fora do Git e devem ser produzidos/armazenados na camada de dados apropriada.

## Ordem operacional

1. concluir a importação e revisão deste bootstrap;
2. executar CONAB Armazéns ponta a ponta no BigQuery real;
3. validar logs, schema, deduplicação, snapshots, particionamento/clustering e consulta;
4. conectar a primeira consulta ao AgroLog Gateway;
5. somente depois promover IMEA para execução contra o BigQuery.

## Regra de arquitetura

BigQuery permanece a fonte única de verdade analítica. Cloud Run é a camada de serviços e o AgroLog Gateway expõe ferramentas controladas para OpenAI/ChatGPT e Claude.

## Dados não versionados

Os diretórios `core/`, `current/`, `raw/`, `downloads/` e exports operacionais são deliberadamente excluídos do repositório. Testes que dependam desses datasets devem ser tratados como testes de integração/pacote e não como testes unitários de clone limpo.
