# AgroLog Maritime Intelligence — GitHub Research — 2026-09-15

## Critério

Esta rodada não trata GitHub como catálogo de dependências. Cada projeto é avaliado por capacidade útil, sobreposição com o stack atual, manutenção, segurança, licença, risco de lock-in e benefício mensurável. O princípio é `best != most technologies`.

## Selecionados

### M0r13n/pyais — ADOPT / DECODER FALLBACK

**Uso:** decoder AIS/NMEA para feeds próprios futuros, SDR, TCP/UDP, arquivos NMEA e validação independente de mensagens.

**Por que importa:** suporta AIVDM/AIVDO, mensagens multipart, streams e sockets; pode servir como segunda implementação de parsing quando o AgroLog passar a receber NMEA bruto além do JSON estruturado do AISStream.

**Decisão:** aprovado como componente opcional/fallback. Não entra no caminho quente do AISStream apenas para duplicar o parser atual. Deve ser ativado quando existir fonte NMEA/SDR real.

**Licença:** MIT.

### movingpandas/movingpandas — REFERENCE / ANALYTICAL POC

**Uso:** QA de trajetórias, stop detection, segmentação, limpeza/smoothing, generalização e agregação de tracks.

**Por que importa:** é diretamente aplicável à validação offline de trajetórias AIS, calibração de port calls e benchmark das nossas heurísticas.

**Decisão:** usar como referência/POC analítico separado, não como dependência obrigatória do runtime. O stack GeoPandas aumenta peso operacional e não é necessário para o caminho quente atual.

**Licença:** BSD-3-Clause.

### cut-dicl/ais2eta — REFERENCE / ETA BENCHMARK

**Uso:** benchmark metodológico para ETA por machine learning.

**Por que importa:** trabalha com AIS, dataset volumoso, diferentes modelos, tuning e cross-validation. Reforça o desenho do AgroLog de nunca promover ETA proprietário sem benchmark e teste fora da amostra.

**Decisão:** usar metodologia/feature ideas como referência. Não copiar dataset/modelo para produção; o AgroLog deve treinar e validar com histórico próprio e condições dos portos brasileiros.

**Licença:** Apache-2.0.

### eurostat/searoute — POC / ROUTE BASELINE

**Uso:** distância e rota marítima aproximada, visualização e baseline de ETA/rota.

**Por que importa:** calcula shortest maritime routes e permite redes marítimas customizadas, inclusive passagens/chokepoints.

**Decisão:** manter como POC/reference. Não usar como verdade de navegação, geofence oficial ou rota operacional de segurança. Qualquer incorporação de código requer revisão jurídica da EUPL-1.2 e revisão da origem/licença da rede subjacente.

**Licença:** EUPL-1.2.

### jvde-github/AIS-catcher — FUTURE EDGE RECEIVER

**Uso:** estação AIS terrestre própria por SDR/receptor, NMEA por UDP/TCP/HTTP, segunda fonte física independente.

**Por que importa:** pode reduzir dependência de um único provedor e criar evidência própria em áreas de cobertura terrestre. Também possui catálogo de places e flags de qualidade de mensagem/checksum que servem como boa referência operacional.

**Decisão:** futuro edge collector independente; não embutir no produto central agora. Se usado, manter processo/serviço separado e validar legislação local, recepção de RF e GPL-3.0.

**Licença:** GPL-3.0.

### MAPS-Lab/AISdb — REFERENCE ARCHITECTURE ONLY

**Uso potencial:** histórico AIS, tracks, H3, enrichment ambiental, PostgreSQL/TimescaleDB e serviços realtime.

**Ponto forte:** arquitetura marítima muito próxima das necessidades futuras do AgroLog e excelente referência para hot storage/track analytics.

**Decisão:** não incorporar diretamente ao core proprietário neste momento. Motivos: forte sobreposição com BigQuery + motores próprios e licença AGPL-3.0. Utilizar padrões arquiteturais e benchmarks, não código, salvo decisão jurídica explícita.

**Licença:** AGPL-3.0.

## Segurança selecionada

### zizmorcore/zizmor — ADOPT CI

**Uso:** análise estática específica de GitHub Actions/CI-CD.

**Cobertura adicional:** template injection, persistência/leak de credenciais, permissões excessivas, refs/commits suspeitos e outras classes específicas de workflows que Bandit/pip-audit/npm audit não cobrem.

**Decisão:** incorporar ao security gate com action/versão imutáveis, `advanced-security: false` no repositório privado e findings relevantes bloqueando release.

**Licença:** MIT.

### aquasecurity/trivy — ADOPT SECURITY GATE

**Uso:** filesystem/container/dependency/misconfiguration scanning.

**Decisão:** adicionar como camada independente após os scanners existentes, com pin por commit e `HIGH,CRITICAL` bloqueando o release. Não substituir Bandit, pip-audit ou npm audit; as ferramentas cobrem superfícies diferentes.

### gitleaks/gitleaks — NÃO NECESSÁRIO COMO DEPENDÊNCIA IMEDIATA

A pesquisa mostrou uma lacuna real: nosso scanner verificava somente arquivos atuais. A correção foi incorporada no scanner interno: agora o histórico Git alcançável também é varrido por assinaturas de segredo, inclusive linhas removidas. Gitleaks permanece referência e poderá ser usado como auditor externo periódico, mas adicionar mais um scanner para o mesmo gate agora não agrega valor suficiente.

### anchore/syft — FUTURE SBOM GATE

**Uso:** SBOM de imagens/artefatos.

**Decisão:** útil quando as imagens finais do collector/Gateway estiverem sendo construídas consistentemente no CI/Artifact Registry. O SBOM deve entrar antes da promoção da imagem para produção, e não como ferramenta ornamental enquanto os runners não executam.

## Melhorias incorporadas nesta rodada

1. Aceitação final all-or-nothing: nenhum módulo é promovido isoladamente.
2. Workflow de aceitação do projeto inteiro em todo PR para `main`, sem path filters.
3. Compilação recursiva de toda a superfície Python relevante.
4. Todos os unit tests em uma mesma aceitação.
5. Todos os contratos JSON e workflows YAML validados.
6. Shell syntax em todos os scripts `.sh`.
7. Build real das duas imagens Docker.
8. Security policy + Bandit + pip-audit + npm audit no mesmo acceptance.
9. Histórico Git incluído no secret scanning; exclusão posterior do arquivo não apaga finding.
10. Contract drift test: JSON e runtime precisam manter exatamente os mesmos gates finais.
11. Probe live de line-up consolidado dentro do PR final, eliminando branch paralela.
12. PR #153 encerrado como superseded pelo PR final #155.

## Melhorias ainda elegíveis, com gate

- SBOM e assinatura/proveniência das imagens quando Artifact Registry estiver operacional;
- trajectory benchmark com MovingPandas no dataset proprietário, sem tornar a biblioteca dependência do runtime;
- pyais quando existir NMEA bruto real;
- AIS-catcher quando houver decisão de estação terrestre própria;
- SeaRoute somente após revisão de licença/dataset e como baseline, não verdade operacional;
- hot store PostgreSQL/TimescaleDB apenas se métricas reais mostrarem que BigQuery/Gateway não atendem latência; AISdb permanece referência por licença e duplicidade arquitetural.

Nenhuma dessas melhorias pode criar uma segunda fonte canônica de verdade ou permitir que o produto seja declarado final sem os gates operacionais do contrato.
