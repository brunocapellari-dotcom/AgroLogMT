# AgroLog MT — Base IMEA Agro v1.2

**Status:** candidato pré-produção local. **Ainda não carregado no BigQuery real.**

Escopo: soja, milho e algodão. A base IMEA de pecuária permanece separada por arquitetura/editorial do AgroLog MT.

## O que esta versão entrega

- RAW auditável de snapshots estruturados, com membership hash específico por snapshot;
- core confiável sem multiplicidade não resolvida;
- Oferta & Demanda histórica com revisões por data de publicação;
- Estimativas de Safra extraídas das tabelas dos relatórios O&D;
- Custo de Produção dedicado;
- materializações `current/` que não carregam silenciosamente linhas antigas para o estado corrente;
- parser BIFF8 para XLS legado sem Excel/LibreOffice;
- parsers reproduzíveis dos PDFs O&D/Estimativas;
- QA de escala x100, multiplicidade, identidades O&D e crosscheck Estimativas x O&D;
- DDL, views, loader BigQuery e validações do piloto;
- coleta pública com allowlist IMEA e sessão autenticada somente local/supervisionada.

## Números auditados

- séries estruturadas RAW: **40.190** linhas;
- core confiável: **40.046** registros;
- current confiável: **40.030** registros;
- chaves correntes bloqueadas por ambiguidade: **24**;
- grupos de erro de escala x100 tratados: **16**;
- Custo de Produção: **35.848** registros únicos / **25.741** séries correntes;
- Oferta & Demanda: **88 relatórios / 3.666 observações / 130 linhas no relatório corrente**;
- Estimativas: **88 relatórios / 322 tabelas / 2.431 observações / 83 linhas na publicação corrente**;
- produtividade de algodão convertida de `@/ha` para `kg/ha`: **16 linhas**, preservando a unidade de origem e a regra `1 @ = 15 kg`;
- crosscheck de safra: **1 correção de cabeçalho** (Milho 07/10/2024, tabela de produção);
- divergência interna material: **1 tabela** (Algodão 01/04/2024, produção de pluma);
- identidades O&D fora da tolerância: **2 grupos**, preservados e sinalizados.

## Estrutura

- `core/`: histórico normalizado e auditável;
- `current/`: composição atual pelas regras oficiais desta base;
- `audit/`: QA, bloqueios e crosschecks;
- `documentos/`: cobertura e manifestos;
- `operacional/`: `imea-1` atualizado;
- `src/`: parsers reproduzíveis;
- `collector/`: coleta pública e navegador assistido;
- `config/`: contrato de tabelas/recursos e mapa de categorias;
- `schemas/`: schemas BigQuery por tabela;
- `sql/`: DDL, views e validações;
- `tests/`: testes locais antes de qualquer carga.

## BigQuery

Projeto previsto: `project-61334ffa-ea5c-4c3a-82f`  
Localização obrigatória: `southamerica-east1`.

Datasets esperados: `agro`, `mercado`, `logistica`, `ingestao`. O pacote não cria datasets, IAM, Service Account, Cloud Run, Scheduler ou Storage por iniciativa própria.

A carga deve ser append-only por `MERGE`. A segunda execução idêntica deve inserir **0 linhas**.

## IMEA e credenciais

Não coloque usuário/senha do IMEA em prompt, código, `.env`, BigQuery ou Cloud Run. Para recurso autenticado, a estratégia é sessão local visível, com o próprio usuário digitando as credenciais diretamente no site, e somente quando a licença/autorização permitir o download assistido.

Referências de governança:
- https://imea.com.br/imea-site/termo-de-uso.html
- https://www.imea.com.br/imea-site/calendario
- https://www.imea.com.br/imea-site/relatorios-mercado
- https://www.imea.com.br/imea-site/metodologia
