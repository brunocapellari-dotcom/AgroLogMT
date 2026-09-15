# Auditoria de melhorias GitHub — 2026-09-15

## Objetivo

Reavaliar componentes open source que podem elevar a versão final do AgroLog MT sem substituir collectors homologados, duplicar responsabilidades ou criar uma segunda plataforma de orquestração.

Critérios de seleção:

1. reduzir risco material de segurança, supply chain ou perda de evidência;
2. aumentar auditabilidade, proveniência, observabilidade ou reprodutibilidade;
3. integrar ao stack BigQuery + Cloud Run + GitHub existente;
4. possuir responsabilidade clara e não duplicada;
5. não exigir mudança arquitetural apenas por preferência de ferramenta;
6. licença/termos devem ser aceitáveis antes do uso em produção;
7. nenhuma ferramenta nova pode substituir o gate de 100% do projeto por validação modular.

## Selecionados e aplicados

### Zizmor — `zizmorcore/zizmor`

**Decisão:** selecionado para auditoria estática especializada dos workflows GitHub Actions/CI.

- licença MIT verificada na documentação do projeto;
- versão pinada no AgroLog: `1.30.1` via `requirements-security.txt`;
- executado em modo `--offline`, persona `auditor`, sem token/API externa no gate determinístico;
- cobre template injection, persistência/vazamento de credenciais, permissões excessivas e referências confusas/impostoras;
- complementa o pinning SHA e os scans do Trivy;
- finding dentro do limiar configurado bloqueia o gate integral.

### actionlint — `rhysd/actionlint`

**Decisão:** selecionado e incorporado ao `Full Project Final Gate`.

- versão pesquisada: `v1.7.12`;
- binário Linux amd64 validado por SHA-256 antes da execução;
- SHA-256 usado no gate: `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`;
- valida sintaxe/schema do GitHub Actions, expressões `${{ }}`, inputs/outputs de actions, dependências de jobs, cron/globs, reusable workflows e riscos de script injection;
- complementa PyYAML + Zizmor: PyYAML prova sintaxe YAML, Zizmor audita segurança específica e actionlint valida a semântica do workflow;
- roda sobre todos os workflows, nunca apenas o arquivo alterado.

### Gitleaks CLI — `gitleaks/gitleaks`

**Decisão:** selecionado para secret scanning do repositório e histórico relevante.

- núcleo do projeto sob licença MIT verificada;
- versão: `v8.30.1`;
- usa CLI/binário verificado por checksum, não `gitleaks-action`;
- motivo: o `gitleaks-action` atual declara EULA comercial própria;
- PR gate usa scan do tree atual com redaction;
- release final usa scan do histórico Git completo;
- em falha, o diagnóstico pode expor apenas arquivo, linha e rule ID — nunca o valor do segredo;
- falha de secret scan bloqueia release.

### Trivy — `aquasecurity/trivy` / `aquasecurity/trivy-action`

**Decisão:** scanner principal de vulnerabilidades, filesystem, imagens e IaC/configuração.

- action pesquisada novamente em 15/09/2026: `v0.36.0` continua sendo a release atual;
- commit pinado: `ed142fd0673e97e23eac54620cfb913e5ce36c25`;
- vulnerabilidade HIGH/CRITICAL fora da política de exceções bloqueia release;
- evita adoção simultânea de múltiplos scanners com a mesma responsabilidade.

### Syft / Anchore SBOM Action — `anchore/syft`, `anchore/sbom-action`

**Decisão:** selecionado para SBOM de código/dependências e imagens finais.

- action pinada: `v0.24.2` / commit `3ad7283483fc7af8ff2b4ea19663c2d5ca935e26`;
- licença Apache-2.0;
- formato padrão: SPDX JSON;
- SBOM é evidência de release e não substitui scanner de vulnerabilidades.

### consistência de dependências Python

**Decisão:** incorporar `python -m pip check` ao gate integral.

- roda após instalar o conjunto de requirements descoberto no repositório;
- conflito de dependências passa a bloquear o gate antes dos testes;
- lock transitivo Python por hashes continua como melhoria de reprodutibilidade a ser fechada antes de promover imagens assinadas como artefato definitivo.

## Selecionados para a promoção de runtime

### Sigstore Cosign — `sigstore/cosign`

**Decisão:** selecionado para promoção de imagem no Artifact Registry após WIF/Artifact Registry estarem homologados.

- assinatura/attestation liga a imagem promovida à evidência do release;
- não será simulada antes da cadeia real existir;
- depois da primeira homologação da cadeia de build, assinatura deve integrar o critério de promoção da imagem.

### SLSA GitHub Generator — `slsa-framework/slsa-github-generator`

**Decisão:** POC direcionado para provenance de build depois da estabilização de WIF + Artifact Registry.

- não substitui Cosign/SBOM;
- só promove a CORE se operar com mínimo privilégio e sem criar fragilidade operacional.

### OpenTelemetry — `open-telemetry/opentelemetry-python`

**Decisão:** padrão de observabilidade a integrar a Gateway/collectors após runtime GCP homologado.

- traces/metrics/log correlation para collector → storage → Gateway;
- Cloud Logging/Monitoring permanece o destino inicial, sem backend paralelo desnecessário.

### OpenLineage — `OpenLineage/OpenLineage`

**Decisão:** padrão de lineage em POC, incremental.

- transporta fatos que o AgroLog já preserva — source/hash/snapshot/version — e não cria outra fonte de verdade;
- promoção depende de utilidade operacional comprovada no BigQuery/Cloud Run.

### OpenSSF Scorecard — `ossf/scorecard`

**Decisão:** auditoria periódica de postura do repositório, não gate primário de cada PR.

- complementa action pinning, regras de branch, dependências e token permissions;
- não substitui os testes internos do AgroLog.

## Avaliados e não selecionados como CORE

### StepSecurity Harden-Runner — `step-security/harden-runner`

**Decisão:** não incorporar automaticamente.

- tecnicamente útil para monitorar e controlar egress/processos em runners;
- a documentação pesquisada informa Community gratuito apenas para repositórios públicos em GitHub-hosted runners;
- repositório privado requer plano Enterprise;
- não criar dependência comercial nova apenas para satisfazer o gate quando os controles atuais já incluem WIF, mínimo privilégio, pinning SHA, Zizmor, Gitleaks, Trivy e isolamento de credenciais.

### GitHub CodeQL — `github/codeql-action`

**Decisão:** deferido até elegibilidade confirmada.

- excelente análise semântica de segurança e action sob licença MIT;
- o CodeQL CLI possui termos próprios;
- documentação atual indica uso em repositórios privados quando o repositório pertence a organização com GitHub Advanced Security habilitado;
- exige `security-events: write` em advanced setup;
- não será colocado no gate como requisito impossível de cumprir com o plano/repositório atual não confirmado.

### Ruff — `astral-sh/ruff`

**Decisão:** candidato de alta qualidade, mas não promovido a gate nesta rodada.

- release pesquisada: `0.16.7`;
- é adequado para lint estático rápido e pode complementar `py_compile` e testes;
- antes de torná-lo obrigatório, deve haver baseline explícito das regras de erro material para não transformar estilo em blocker operacional;
- prioridade posterior: regras de erro de runtime/undefined names, sem reformatar todo o repositório por preferência estética.

### Gitleaks Action — `gitleaks/gitleaks-action`

**Decisão:** não selecionar automaticamente.

O AgroLog usa o núcleo CLI MIT verificado diretamente e evita introduzir a EULA comercial própria do action.

### OSV-Scanner — `google/osv-scanner`

**Decisão:** diagnóstico secundário, não scanner principal.

Trivy já cobre vulnerabilidades e imagens. Usar ambos como gates obrigatórios aumentaria duplicidade e ruído. OSV pode ser empregado para investigar divergências específicas.

### ShellCheck — `koalaman/shellcheck`

**Decisão:** manter como referência/diagnóstico complementar.

- `bash -n` já valida sintaxe de todos os shell scripts;
- actionlint integra-se a ShellCheck quando disponível para blocos `run:`;
- não adicionar outro workflow obrigatório até existir evidência de lacuna material não coberta pelos testes atuais.

### Dagster / Airflow / Prefect

**Decisão:** não selecionados.

O AgroLog já possui Cloud Run Jobs, Scheduler, Data Source Registry e estado operacional em BigQuery. Um segundo orquestrador aumentaria superfície operacional, permissões, manutenção e custo.

### dbt / SQLMesh / dlt

**Decisão:** não promover todo o stack por antecipação.

- SQLMesh permanece POC para transformação/versionamento SQL quando houver ganho comprovado;
- dlt permanece POC para novas fontes onde reduza boilerplate sem reescrever collectors homologados;
- não criar migração geral apenas para padronização tecnológica.

## Melhorias aplicadas à versão final

1. `Full Project Final Gate` único para a plataforma inteira.
2. descoberta automática de todos os arquivos Python, testes, configs, workflows e scripts.
3. todos os testes determinísticos obrigatórios no gate de mudança.
4. todos os testes live obrigatórios e com zero skipped para `FINAL RELEASE: PASS`.
5. `py_compile` de todo Python.
6. `pip check` de consistência do ambiente Python.
7. PyYAML + actionlint + Zizmor sobre todos os workflows.
8. GitHub Actions pinadas por SHA completo.
9. checkout do gate sem persistir credencial Git quando ela não é necessária.
10. Gitleaks CLI verificada: tree no PR e histórico completo no release.
11. Trivy para filesystem/IaC/dependências/imagens no release final.
12. SBOM source + imagens.
13. containers non-root e frontend com `package-lock.json` + `npm ci`.
14. GCP preflight + runtime security + freshness/quality + restore drill.
15. `N6 CORE HOMOLOGATION: PASS` como prova do core real.
16. auditor independente e `AGROLOG MT FINAL RELEASE: PASS` como única aprovação final.
17. qualquer stage ausente produz `BLOCKED`, nunca `PARTIAL PASS`.
18. workflows diagnósticos não autorizam promoção da plataforma.

## Bloqueios atuais

### Resolvidos

- #159 — GitHub Actions voltou a receber runner e já executou o gate hospedado;
- #161 — `maritime_ui/package-lock.json` existe e o frontend usa `npm ci`;
- achados HIGH do Zizmor — corrigidos; execução posterior reportou zero findings HIGH.

### A fechar antes da declaração FINAL

- o gate determinístico de 100% do branch consolidado ainda precisa terminar verde após todas as mudanças atuais, inclusive o lote Maritime;
- o último Gitleaks encontrou duas correspondências; fixtures sintéticas foram reescritas e precisam ser confirmadas pelo novo gate integral;
- bootstrap/homologação GCP/WIF/service accounts do projeto `agrolog-mt-prod` ainda precisa ser provado pelo gate real;
- `main` foi observado sem proteção ativa; o ruleset canônico precisa ser aplicado/verificado antes de produção;
- credenciais externas da ANA continuam sendo bloqueio da própria fonte, sem autorização para colocá-las em GitHub Actions;
- assinatura/provenance de imagem depende do Artifact Registry/WIF real;
- a promoção final LIVE/GCP ainda não produziu simultaneamente `N6 CORE HOMOLOGATION: PASS` e `AGROLOG MT FINAL RELEASE: PASS`.

Nenhum desses bloqueios autoriza reduzir o critério. A solução é fechar a causa e executar novamente 100% do projeto.