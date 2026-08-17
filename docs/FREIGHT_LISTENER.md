# Freight Listener — Especificação Canônica

## 1. Objetivo

O Freight Listener transforma mensagens e mídias de **canais autorizados** em observações estruturadas de ofertas de frete para uso analítico no AgroLog MT.

O módulo não presume contratação, execução ou pagamento. Seu produto primário é uma base de **ofertas observadas na amostra**, com evidência, deduplicação, confiança e limitações explícitas.

## 2. Escopo inicial

Entrada potencial:
- texto de mensagem;
- imagem com tabela/oferta;
- PDF ou documento;
- planilha;
- áudio em fase posterior.

Canal inicial candidato:
- WhatsApp, por adaptador isolado e somente em conta/grupo/canal cujo acesso e uso sejam autorizados.

Saída:
- evento normalizado de oferta observada;
- vínculo com evidência original armazenada fora do GitHub;
- cluster de deduplicação/reoferta;
- sinais agregados de mercado.

Fora do escopo inicial:
- enviar mensagens automaticamente;
- negociar frete;
- aceitar/contratar carga;
- estimar disponibilidade real de caminhão como fato;
- afirmar frete realizado ou preço pago sem fonte autorizada;
- armazenar mensagens reais no GitHub.

## 3. Princípios

1. **Fornecedor do WhatsApp é substituível.** O restante do sistema consome um evento canônico, não uma API proprietária específica.
2. **BigQuery é a fonte de verdade analítica.**
3. **RAW/Drive/Cloud Storage preserva evidência original quando necessário.**
4. **GitHub guarda código, schema, testes e documentação; nunca o conteúdo real dos grupos.**
5. **PII é minimizada.** Identidade pessoal não aparece em BI por padrão.
6. **Oferta observada ≠ frete realizado.**
7. **Repostagem ≠ nova carga automaticamente.**
8. **IA sem confiança suficiente não inventa valor.** Casos ambíguos são rejeitados ou enviados para revisão.

## 4. Arquitetura lógica

```text
WhatsApp/canal autorizado
        ↓
Adaptador isolado
(Evolution API / WPPConnect / WAHA ou equivalente aprovado)
        ↓
Webhook / fila
        ↓
Evento canônico de mensagem
        ↓
Classificador de relevância
        ├── ruído → métrica/descarte conforme política
        └── potencial oferta
                 ↓
        extração estruturada
          ├── texto
          ├── imagem/visão
          └── documento/Docling
                 ↓
        normalização de entidades
                 ↓
        deduplicação/reoferta
                 ↓
        auditoria + confiança
                 ↓
              BigQuery
                 ↓
      Freight Market Signal Engine
                 ↓
        Gateway / BI / mapa / agentes
```

## 5. Evento canônico de entrada

O adaptador de canal deve converter o provedor externo para um contrato independente, contendo apenas os campos necessários.

Campos mínimos sugeridos:

- `source_channel_type` — ex.: `whatsapp`;
- `source_provider` — provedor/adaptador usado;
- `source_channel_id_hash` — identificador pseudonimizado do grupo/canal;
- `source_message_id_hash` — identificador pseudonimizado/estável do evento;
- `sender_id_hash` — remetente pseudonimizado quando necessário;
- `published_at` — timestamp observado da mensagem;
- `collected_at` — timestamp de recebimento pelo AgroLog;
- `message_type` — texto, imagem, documento, planilha, áudio etc.;
- `text_content` — somente quando a política de tratamento permitir;
- `raw_artifact_ref` — referência controlada para artefato original fora do GitHub;
- `content_hash` — hash para integridade/deduplicação técnica.

## 6. Contrato analítico de oferta observada

Nome lógico sugerido: `freight_offer_observation`.

### Identificação e linhagem

- `observation_id`
- `source_channel_type`
- `source_provider`
- `source_channel_id_hash`
- `source_message_id_hash`
- `sender_id_hash`
- `raw_artifact_ref`
- `content_hash`
- `collector_version`
- `parser_version`

### Datas

- `data_referencia`
- `data_publicacao`
- `data_coleta`
- `competencia`

### Evidência

- `classe_evidencia = observado`
- `subtipo_evidencia = oferta_frete_observada`
- `contratado_status = desconhecido` por padrão
- `executado_status = desconhecido` por padrão

### Origem/coleta

- `origin_place_raw`
- `origin_municipality_id`
- `origin_municipality_name`
- `origin_state`
- `pickup_location_raw`
- `pickup_entity_id` quando resolvido

### Destino/entrega

- `destination_place_raw`
- `destination_municipality_id`
- `destination_municipality_name`
- `destination_state`
- `delivery_location_raw`
- `delivery_entity_id` quando resolvido

### Carga/operação

- `product_raw`
- `product_id`
- `equipment_raw`
- `equipment_id`
- `operation_notes`

### Valor anunciado

- `freight_value_raw`
- `freight_value_numeric`
- `freight_unit_raw`
- `freight_unit_id`
- `currency`

A unidade nunca deve ser inferida silenciosamente quando houver ambiguidade material. Exemplos possíveis incluem valor por tonelada, por viagem, por saca ou outras formas observadas na fonte.

### Entidades comerciais

- `company_raw`
- `company_id` quando resolvido de forma autorizada
- `contact_present` — booleano, sem expor telefone em camada analítica comum

### Qualidade

- `classification_confidence`
- `extraction_confidence`
- `normalization_confidence`
- `requires_review`
- `rejection_reason`

### Deduplicação e reoferta

- `dedup_cluster_id`
- `dedup_score`
- `is_probable_repost`
- `is_probable_reoffer`
- `reoffer_sequence`
- `previous_observation_id`
- `price_change_from_previous`

## 7. Normalização

A normalização deve usar identificadores canônicos e preservar o valor bruto recebido.

Exemplos:

- `Rondonopolis`, `Rondonópolis/MT`, `ROO` e formas equivalentes só podem convergir para `RONDONOPOLIS_MT` quando regra/dicionário/contexto sustentar a equivalência;
- abreviações ambíguas devem manter valor bruto e baixa confiança;
- nomes de fazenda, terminal e empresa devem ser resolvidos para entidade canônica somente quando houver evidência suficiente;
- produto, equipamento e unidade devem usar vocabulários controlados mantidos pelo AgroLog.

## 8. Deduplicação

Objetivo: separar **mensagens** de **oportunidades prováveis**.

Um cluster de deduplicação pode considerar:

- origem;
- coleta;
- destino;
- entrega;
- produto;
- equipamento;
- valor/unidade;
- empresa/fonte;
- proximidade temporal;
- similaridade textual;
- hash/mídia quando aplicável.

O algoritmo deve produzir `dedup_score`, não uma certeza artificial. Regras determinísticas devem ser preferidas onde forem suficientes; IA pode complementar casos ambíguos.

## 9. Reoferta, reajuste e persistência

Quando mensagens diferentes forem agrupadas como provável mesma oportunidade, preservar a sequência temporal.

Sinais possíveis:

- **repostagem** — provável mesma oferta repetida sem mudança material;
- **reoferta** — provável mesma oportunidade novamente anunciada após intervalo relevante;
- **reajuste** — provável mesma oportunidade com alteração no valor anunciado;
- **persistência** — duração observável entre primeira e última aparição do cluster.

Esses conceitos são sinais da amostra. Não provam dificuldade de contratação isoladamente.

## 10. Freight Market Signal Engine

Indicadores candidatos:

1. `raw_offer_message_count` — mensagens classificadas como oferta;
2. `unique_offer_cluster_count` — clusters de oportunidades prováveis;
3. `repost_rate` — mensagens repetidas / mensagens de oferta;
4. `reoffer_rate` — clusters com reoferta / clusters únicos;
5. `price_revision_rate` — clusters com mudança de valor / clusters únicos;
6. `offer_persistence` — tempo entre primeira e última observação do cluster;
7. `observed_offer_value_median` — mediana de valores **anunciados observados** em recorte homogêneo;
8. `route_offer_intensity` — intensidade de ofertas por rota/período;
9. `source_concentration` — concentração por canal/remetente pseudonimizado/empresa para medir viés da amostra;
10. `coverage_score` — qualidade/cobertura mínima da amostra antes de publicar conclusão.

Toda métrica derivada deve declarar:
- janela temporal;
- rota/granularidade;
- produto/equipamento/unidade quando aplicável;
- número de mensagens brutas;
- número de clusters únicos;
- concentração da amostra;
- limitações conhecidas.

## 11. Mapa de ofertas

Origem e destino normalizados podem alimentar geointeligência agregada.

Aplicações:
- rotas com maior intensidade de ofertas observadas;
- mudança de fluxo por semana/safra;
- cruzamento com produção, armazenagem, indústria, line-up, rodovias e hidrovias;
- comparação entre sinais de WhatsApp e dados públicos/operacionais autorizados.

Nunca exibir telefone ou PII no mapa analítico comum.

## 12. Privacidade, segurança e retenção

Antes de conectar conta real:

- documentar finalidade e autorização de uso;
- revisar termos da plataforma e licença do adaptador;
- definir contas/ambientes isolados;
- armazenar credenciais em secret manager apropriado;
- definir política de retenção do RAW;
- restringir acesso aos artefatos originais;
- pseudonimizar remetentes para uso analítico;
- registrar auditoria de acesso;
- definir procedimento de exclusão/correção quando aplicável.

O adaptador de WhatsApp não deve possuir credenciais permanentes para BigQuery. Deve publicar apenas no ponto de entrada autorizado do pipeline.

## 13. Estratégia de implementação

### Fase FL-0 — benchmark sem conta real
- comparar Evolution API, WPPConnect e WAHA;
- avaliar licença, atividade, segurança, arquitetura, suporte a webhook/grupo/mídia e risco de quebra;
- definir adaptador canônico independente do provedor.

### Fase FL-1 — fixture artificial
- criar mensagens artificiais representando texto, tabela, abreviação, unidade ambígua, repostagem e reajuste;
- validar classificador e contrato sem usar dado pessoal real.

### Fase FL-2 — extração e normalização
- texto primeiro;
- imagem/PDF depois;
- revisão humana nos casos de baixa confiança.

### Fase FL-3 — deduplicação e sinais
- clusterizar provável mesma oportunidade;
- preservar todas as observações;
- calcular sinais somente com cobertura mínima definida.

### Fase FL-4 — piloto autorizado
- conectar um canal autorizado isolado;
- medir estabilidade, precisão, falsos positivos, perdas e custo operacional;
- validar política de retenção/PII.

### Fase FL-5 — BigQuery/Gateway/BI
- criar tabela somente após schema estabilizado;
- validar carga, idempotência e linhagem;
- expor consulta controlada via AgroLog Gateway;
- construir BI/mapa com agregação e limitações explícitas.

## 14. Critérios de sucesso do piloto

- nenhuma mensagem real no GitHub;
- ≥ 95% dos eventos tecnicamente recebidos sem perda no piloto controlado, ou limite revisado com justificativa;
- precisão de classificação e extração medida com conjunto rotulado;
- deduplicação avaliada separadamente de extração;
- PII não aparece em camada analítica comum;
- toda observação rastreável à evidência original autorizada;
- nenhuma conclusão publicada como frete realizado sem evidência correspondente;
- quebra do adaptador não afeta os demais módulos do AgroLog.

## 15. Decisões ainda abertas

- provedor/adaptador de WhatsApp;
- mecanismo de fila/event bus;
- política final de retenção de RAW;
- limites de confiança por tipo de campo;
- método de geocodificação e dicionário canônico de localidades;
- unidade mínima de publicação dos indicadores;
- cobertura mínima necessária por rota/período;
- necessidade de armazenamento de texto integral após extração e auditoria.

Essas decisões devem ser tomadas por evidência do piloto, não por preferência de ferramenta.
