# IMEA Agro — Migração seletiva para N6

## Decisão

O branch histórico `bootstrap/v3-conab-imea` permanece como evidência pré-produção. Ele **não será mergeado integralmente** na arquitetura atual.

A migração usa apenas artefatos e regras que continuam válidos, submetendo-os novamente aos contratos, QA e point-in-time atuais.

## O que é reutilizado

- hashes e conceito append-only por snapshot/vintage;
- separação entre registro RAW estruturado e registro confiável;
- bloqueio de multiplicidade ambígua;
- QA de escala ×100;
- preservação de unidade de origem e unidade canônica;
- Oferta & Demanda com revisões por data de publicação;
- Estimativas com revisão/publicação;
- Custo de Produção dedicado;
- regra auditada para produtividade de algodão: `1 @ = 15 kg`;
- merge idempotente por hash de registro.

## O que é substituído

- árvore RAW local → RAW binário no Google Drive via `DriveBigQueryStore`;
- dataset operacional legado `ingestao` → `agrolog_ops` para snapshots/estrutura de QA de migração;
- scripts monolíticos antigos → módulos do coletor N6 atual;
- projeto GCP hardcoded → projeto resolvido pelo runtime/ADC;
- qualquer fluxo que pudesse depender de credencial em arquivo → autenticação segura fora do código.

## Tabelas N6

| Grupo | Destino atual | Merge key | Gate adicional |
|---|---|---|---|
| snapshots | `agrolog_ops.imea_snapshots` | `hash_snapshot` | linhagem completa |
| RAW estruturado | `agrolog_ops.imea_registros_raw` | `hash_snapshot_registro` | não substituir RAW binário |
| indicadores | `agro.imea_indicadores` | `hash_registro` | QA confiável |
| custos | `agro.imea_custo_producao` | `hash_registro` | unicidade + unidade |
| Oferta & Demanda | `agro.imea_oferta_demanda` | `hash_registro` | revisões point-in-time + identidade |
| estimativas | `agro.imea_estimativas_relatorios` | `hash_registro` | publicação + safra + unidade |

## Evidência histórica conhecida

A versão antiga documentou, antes de qualquer BigQuery real:

- 40.190 linhas estruturadas RAW;
- 40.046 registros no core confiável;
- 40.030 registros correntes confiáveis;
- 24 chaves correntes bloqueadas por ambiguidade;
- 16 grupos de erro ×100 tratados;
- 35.848 registros únicos de custo de produção;
- 88 relatórios de Oferta & Demanda / 3.666 observações;
- 88 relatórios de Estimativas / 2.431 observações;
- 16 conversões de produtividade de algodão de arroba/ha para kg/ha;
- 1 divergência interna material documentada;
- 2 grupos O&D fora da tolerância de identidade.

Esses números são **benchmark de migração**, não prova de que a base corrente já foi revalidada.

## Validador N6

`collector/imea_migration.py` e `scripts/validate_imea_migration.py` verificam o pacote antes de carga:

1. cabeçalhos obrigatórios por grupo;
2. merge key não vazia;
3. duplicidade de merge key;
4. QA bloqueado em tabelas confiáveis;
5. hashes do artefato de migração;
6. grupos ausentes;
7. contagens para reconciliação com a evidência antiga.

O migrador não corrige silenciosamente linha ambígua e não inventa arquivos ausentes.

## Gates restantes

Para promover IMEA a produtivo:

1. recuperar apenas artefatos permitidos/autorizados;
2. executar o validador N6;
3. reconciliar contagens com os benchmarks históricos;
4. repetir os crosschecks de escala, unidade, multiplicidade, O&D e Estimativas;
5. validar datas de publicação/coleta para point-in-time;
6. somente após homologação P0/P1 executar o loader no BigQuery real;
7. repetir a carga e comprovar inserção zero na segunda execução;
8. materializar views correntes sem carregar silenciosamente versões antigas.

## Credenciais e conteúdo protegido

Usuário/senha IMEA não devem ser colocados em prompt, GitHub, `.env` versionado, BigQuery ou Cloud Run. Conteúdo autenticado só entra quando houver autorização/licença compatível e por fluxo seguro. Conteúdo proprietário não deve ser republicado integralmente; o AgroLog MT deve armazenar dados/metadados autorizados e sínteses conforme direitos de uso.
