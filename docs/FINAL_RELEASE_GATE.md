# Final Release Gate — AgroLog MT

## Princípio

O AgroLog MT é aceito como **uma plataforma**, não como uma coleção de módulos aprovados isoladamente.

Testes específicos por fonte, domínio ou componente continuam úteis para diagnóstico rápido, mas **não autorizam release**. A única decisão final é produzida pelo `Full Project Final Gate`.

## O que significa 100% do projeto

A promoção final exige simultaneamente:

1. integridade estrutural do repositório;
2. compilação de **todos** os arquivos Python descobertos;
3. execução de **todos** os testes determinísticos descobertos no repositório;
4. execução de **todos** os testes live descobertos; teste live pulado não conta como executado na promoção;
5. validação de todos os JSONs/configs/contratos relevantes;
6. validação de todos os workflows YAML e scripts shell;
7. Data Source Registry íntegro e referências existentes;
8. frontend reprodutível com `package-lock.json`, `npm ci` e build real;
9. build de todos os containers de produção;
10. secret scanning do repositório/histórico;
11. vulnerability + misconfiguration scan de filesystem e imagens;
12. SBOM de source e imagens;
13. runtime security real no GCP;
14. data quality + freshness real;
15. restore drill real e não destrutivo;
16. GCP preflight;
17. `N6 CORE HOMOLOGATION: PASS`;
18. auditor final independente da primeira avaliação.

O contrato está em `contracts/full_project_release_gate.v1.schema.json`.

## Estados

- `PASS`: todas as 18 etapas obrigatórias possuem evidência `PASS`.
- `FAIL`: uma ou mais etapas foram executadas e falharam.
- `BLOCKED`: alguma etapa necessária não pôde ser executada ou não possui evidência suficiente.

Não existe `PARTIAL PASS` para release final.

## Execução canônica

### CI de mudança

`.github/workflows/full-project-final-gate.yml` executa o projeto inteiro em cada PR:

- secret scan;
- Trivy filesystem/IaC/dependencies;
- SBOM;
- build de todos os containers;
- descoberta/compilação de todo Python;
- descoberta e execução de todos os testes determinísticos;
- validação de contracts/configs/workflows/scripts;
- registry;
- frontend reproduzível.

Esse estágio verifica toda a base de código, não apenas os arquivos alterados.

### Promoção final

`workflow_dispatch(final_release=true)` executa novamente a base inteira e acrescenta:

- identidade federada GCP;
- todos os testes live;
- preflight de produção;
- restore drill point-in-time em sandbox;
- homologação N6 real;
- freshness/quality/runtime security;
- auditor final;
- reexecução final do manifesto até `PASS`.

## Segurança de supply chain

Ferramentas selecionadas:

- Gitleaks CLI verificado por checksum para segredos;
- Trivy pinado por commit para vulnerabilidades/misconfiguration/imagens;
- Syft/Anchore SBOM Action pinada por commit para SBOM;
- Cosign/SLSA entram na etapa de assinatura/provenance após Artifact Registry/WIF estarem homologados.

Nenhuma action de terceiro entra por tag flutuante.

## Frontend

`package.json` com versões diretas fixas não substitui lockfile transitivo.

Release exige:

- `maritime_ui/package-lock.json` versionado;
- `npm ci --ignore-scripts`;
- build Vite real;
- Dockerfile utilizando o mesmo lock;
- scan e SBOM do resultado.

Ausência do lock é falha de release, não warning.

## Restore

`scripts/run_bigquery_restore_drill.py` executa drill não destrutivo:

- lê o BigQuery por point-in-time/time travel;
- restaura em `recovery_sandbox`;
- aplica TTL ao alvo;
- compara schema e row count;
- preserva job IDs/target como evidência;
- não acessa/exporta Secret Manager;
- nunca sobrescreve produção.

O resultado deve satisfazer `contracts/restore_drill.v1.schema.json` e `models/restore_readiness.py`.

## Auditor final

`scripts/final_release_auditor.py` não cria um segundo critério. Ele verifica independentemente se todas as outras etapas obrigatórias já estão `PASS`.

A sequência final é:

`whole-project evidence → pre-audit report → independent auditor → FINAL report`

A saída terminal autorizada é:

`AGROLOG MT FINAL RELEASE: PASS`

Isso não substitui o sinal interno do core:

`N6 CORE HOMOLOGATION: PASS`

## Bloqueios não são exceções

Runner indisponível, credencial ausente, fonte não homologada, lockfile inexistente, secret não configurado ou restore não executado resultam em `BLOCKED`/`FAIL`.

O gate não deve ser reduzido para liberar uma versão.
