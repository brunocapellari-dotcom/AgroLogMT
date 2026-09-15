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

## Dois momentos do mesmo gate

O critério é sempre do **projeto inteiro**. A separação abaixo existe apenas para evitar desperdiçar GitHub Actions e credenciais de produção em cada commit.

### 1. Gate determinístico de mudança

`.github/workflows/full-project-final-gate.yml` roda automaticamente no PR e verifica **100% da base determinística**, independentemente dos arquivos alterados:

- checkout sem persistência de credencial Git quando não necessária;
- instalação do conjunto de requirements descoberto;
- `pip check` do ambiente Python;
- compilação de todo Python;
- descoberta e execução de todos os testes determinísticos;
- validação de todos os JSONs/configs/contratos;
- validação YAML e `bash -n` de todos os scripts shell;
- action pinning e containers non-root;
- Data Source Registry completo;
- frontend com `package-lock.json`, `npm ci --ignore-scripts` e build real;
- Zizmor sobre todos os workflows;
- actionlint sobre todos os workflows;
- Gitleaks sobre o tree atual, com redaction.

Não há aprovação modular: uma mudança em qualquer área faz o gate determinístico percorrer o repositório inteiro.

Checks caros, externos ou que exigem identidade produtiva **não são simulados** no PR. Eles são obrigatórios no segundo momento.

### 2. Promoção final LIVE/GCP

`workflow_dispatch(final_release=true)` executa a homologação integral antes da declaração de versão final. Ela revalida a base e acrescenta toda a evidência que não pode ser produzida honestamente no PR:

- identidade federada GCP via WIF;
- full Git-history secret scan;
- Trivy filesystem/dependencies/IaC;
- SBOM de source;
- build dos containers de produção;
- Trivy de todas as imagens;
- SBOM das imagens;
- todos os testes live com **zero skipped**;
- GCP preflight de produção;
- runtime security;
- data quality e freshness reais;
- homologação N6 real;
- restore drill point-in-time não destrutivo;
- auditor final independente;
- selagem do relatório final sem transformar ausência de evidência em sucesso.

A promoção só termina quando todas as 18 etapas estão `PASS`.

## Segurança de supply chain

Ferramentas selecionadas:

- Gitleaks CLI verificado por checksum para segredos;
- Zizmor para auditoria especializada de GitHub Actions;
- actionlint verificado por checksum para semântica de workflows e expressões;
- Trivy pinado por commit para vulnerabilidades/misconfiguration/imagens;
- Syft/Anchore SBOM Action pinada por commit para SBOM;
- Cosign/SLSA entram na cadeia de assinatura/provenance após Artifact Registry/WIF real estar homologado.

Nenhuma action de terceiro entra por tag flutuante. Actions remotas ficam pinadas por SHA completo.

## Dependências

### JavaScript/frontend

`package.json` com versões diretas não substitui lock transitivo.

Release exige:

- `maritime_ui/package-lock.json` versionado;
- `npm ci --ignore-scripts`;
- build Vite real;
- Dockerfile utilizando o mesmo lock;
- scan e SBOM do resultado.

### Python

O gate instala os requirements do repositório em conjunto e exige `python -m pip check` sem conflitos.

Ranges de requirements continuam permitidos enquanto a cadeia de build ainda não foi promovida como imagem definitiva. Antes de tratar uma imagem assinada como artefato imutável de produção, a resolução efetiva de dependências deve ser preservada na evidência/SBOM e a estratégia de lock transitivo por hashes deve ser fechada junto da promoção Artifact Registry + Cosign/SLSA.

## Secret scanning

No PR:

- Gitleaks examina o tree atual;
- valores são redacted;
- quando houver finding, o diagnóstico pode imprimir somente arquivo, linha e rule ID.

Na promoção final:

- Gitleaks examina o histórico Git completo;
- finding bloqueia release;
- falso positivo só pode ser tratado por regra/fixture explícita e auditável, nunca desabilitando o scan inteiro.

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

Os dois devem existir no mesmo ciclo de homologação final.

## Branch protection

Uma versão não deve ser considerada pronta para produção se `main` puder receber alterações sem o ruleset canônico. `scripts/harden_github_repository.sh` define o controle esperado de pull request, status checks, resolução de review threads, bloqueio de delete/force-push e ausência de bypass amplo.

O ruleset deve ser aplicado e depois verificado por API antes da declaração FINAL.

## Bloqueios não são exceções

Runner indisponível, credencial ausente, fonte não homologada, secret não configurado, branch sem proteção, live test skipped, scan não executado ou restore não realizado resultam em `BLOCKED`/`FAIL`.

O gate não deve ser reduzido para liberar uma versão.