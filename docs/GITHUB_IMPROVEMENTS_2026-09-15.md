# Auditoria de melhorias GitHub — 2026-09-15

## Objetivo

Reavaliar componentes open source que podem elevar a versão final do AgroLog MT sem substituir collectors homologados, duplicar responsabilidades ou criar uma segunda plataforma de orquestração.

Critérios de seleção:

1. reduzir risco material de segurança, supply chain ou perda de evidência;
2. aumentar auditabilidade, proveniência, observabilidade ou reprodutibilidade;
3. integrar ao stack BigQuery + Cloud Run + GitHub existente;
4. possuir responsabilidade clara e não duplicada;
5. não exigir mudança arquitetural apenas por preferência de ferramenta;
6. licença/termos devem ser aceitáveis antes do uso em produção.

## Selecionados

### Gitleaks CLI — `gitleaks/gitleaks`

**Decisão:** selecionado para secret scanning do repositório e histórico relevante.

- núcleo do projeto sob licença MIT verificada em 15/09/2026;
- versão pesquisada: `v8.30.1`;
- usar CLI/binário verificado por checksum, não `gitleaks-action`;
- motivo: o `gitleaks-action` atual declara EULA comercial própria, portanto não será introduzido automaticamente no AgroLog;
- falha de secret scan bloqueia release.

### Trivy — `aquasecurity/trivy` / `aquasecurity/trivy-action`

**Decisão:** selecionado como scanner principal de vulnerabilidades, filesystem, imagens e IaC/configuração.

- action pesquisada: `v0.36.0`;
- tag verificada aponta para commit `ed142fd0673e97e23eac54620cfb913e5ce36c25`;
- usar action somente pinada pelo SHA completo;
- evita adoção simultânea de múltiplos scanners com a mesma responsabilidade;
- vulnerabilidade crítica/alta fora da política de exceções bloqueia release.

### Syft / Anchore SBOM Action — `anchore/syft`, `anchore/sbom-action`

**Decisão:** selecionado para SBOM de código/dependências e imagens finais.

- action pesquisada: `v0.24.2`;
- tag aponta para commit `3ad7283483fc7af8ff2b4ea19663c2d5ca935e26`;
- formato padrão preferido: SPDX JSON;
- SBOM faz parte da evidência de release, não substitui scanner de vulnerabilidades.

### Sigstore Cosign — `sigstore/cosign`

**Decisão:** selecionado para a fase de promoção de imagem no Artifact Registry, após bootstrap GCP.

- finalidade: assinatura/attestation de imagens e vínculo entre imagem promovida e evidência de release;
- não será simulado antes de existir Artifact Registry/WIF operacional;
- assinatura passa a ser requisito do release final depois da primeira homologação da cadeia de build.

### SLSA GitHub Generator — `slsa-framework/slsa-github-generator`

**Decisão:** POC direcionado para provenance de build, posterior à estabilização do Actions e Artifact Registry.

- não substitui Cosign/SBOM;
- só promove a CORE se a integração puder operar com mínimo privilégio e sem aumentar fragilidade do pipeline.

### OpenTelemetry — `open-telemetry/opentelemetry-python`

**Decisão:** manter como padrão de observabilidade a integrar ao Gateway/collectors depois do runtime GCP estar homologado.

- objetivo: traces/metrics/log correlation para collector → storage → Gateway;
- não introduzir backend adicional antes de usar Cloud Logging/Monitoring como destino inicial.

### OpenLineage — `OpenLineage/OpenLineage`

**Decisão:** manter como padrão de lineage em POC, com adoção incremental no evento de coleta/transformação.

- o AgroLog já preserva source/hash/snapshot/version; OpenLineage deve transportar esses fatos, não criar uma segunda fonte de verdade;
- promoção depende de provar utilidade operacional no BigQuery/Cloud Run.

### OpenSSF Scorecard — `ossf/scorecard`

**Decisão:** auditoria periódica de postura do repositório, não gate primário de cada PR.

- motivo: complementa os controles próprios de action pinning, branch protection, dependências e token permissions;
- não substituir os testes internos do AgroLog.

## Avaliados e não selecionados como CORE

### OSV-Scanner — `google/osv-scanner`

**Decisão:** referência/segundo diagnóstico, não scanner principal.

Trivy já cobre a responsabilidade central de vulnerabilidades e imagens. Rodar ambos como gates obrigatórios aumentaria duplicidade e ruído sem ganho proporcional. Pode ser usado para investigação de divergências.

### Dagster / Airflow / Prefect

**Decisão:** não selecionados.

O AgroLog já possui Cloud Run Jobs, Scheduler, Data Source Registry e estado operacional em BigQuery. Introduzir um segundo orquestrador neste momento aumenta superfície operacional, permissões, manutenção e custo. Reavaliar apenas se houver requisito concreto que a arquitetura atual não consiga atender.

### dbt/SQLMesh/dlt

**Decisão:** não promover todo o stack por antecipação.

- SQLMesh permanece POC para transformação/versionamento SQL quando houver ganho comprovado;
- dlt permanece POC para novas fontes onde reduza boilerplate sem reescrever collectors homologados;
- não criar migração geral só para padronização tecnológica.

## Melhorias aplicadas à versão final

1. **Full Project Release Gate** único para o projeto inteiro.
2. descoberta automática de todos os arquivos Python/testes/configs/workflows/scripts, reduzindo listas manuais incompletas;
3. separação explícita entre testes determinísticos e testes live, mas ambos obrigatórios para `FINAL RELEASE: PASS`;
4. secret scan obrigatório;
5. vulnerability/IaC/image scan obrigatório;
6. SBOM obrigatório;
7. containers não-root e builds reproduzíveis obrigatórios;
8. frontend só passa com `package-lock.json` + `npm ci`;
9. GCP preflight + restore drill + freshness/quality real + `N6 CORE HOMOLOGATION: PASS` no mesmo critério final;
10. qualquer stage ausente gera `BLOCKED`, nunca aprovação parcial.

## Bloqueios atuais encontrados pela auditoria

- GitHub Actions não recebe runner (#159), impedindo executar o gate hospedado;
- bootstrap GCP/WIF/service accounts ainda não foi homologado (#160);
- `maritime_ui/package-lock.json` ainda não existe; enquanto isso o build frontend não é reprodutível e a versão final permanece bloqueada;
- assinatura/provenance de imagem depende do Artifact Registry/WIF real.

Esses bloqueios não autorizam reduzir o gate. Eles definem exatamente o que falta para a versão final.
