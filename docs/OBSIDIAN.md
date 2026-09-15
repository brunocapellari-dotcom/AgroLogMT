# Obsidian — Segundo Cérebro do AgroLog MT

O Obsidian é a camada permanente de conhecimento técnico, histórico, causal e contextual do AgroLog MT. Ele não substitui o GitHub como fonte canônica de código/documentação do sistema nem o BigQuery como fonte de verdade analítica.

## Papel operacional

O Segundo Cérebro deve permitir que agentes e analistas recuperem contexto anterior sem reprocessar todo o histórico, preservando evidência e temporalidade.

Ele organiza conhecimento sobre:

- agricultura, safra, fenologia, solos e produtividade;
- clima/agroclima e sensoriamento remoto;
- mercados Brasil, EUA, Argentina e global;
- oferta/demanda e marketing years;
- comércio exterior, preços, basis, prêmios e câmbio;
- logística terrestre, armazenagem, fretes e corredores;
- marítimo, portos, AIS, line-up, ETA e congestionamento;
- hidrologia, Madeira, Tapajós e navegabilidade;
- energia, petróleo, diesel, biodiesel e transmissão de custos;
- agroindústria, etanol e esmagamento;
- pecuária de corte;
- geopolítica, sanções, choques e eventos históricos;
- métodos, modelos, causalidade, forecast e auditoria.

## Regra de entrada de conhecimento

Nenhum conteúdo externo entra automaticamente como verdade.

Fluxo:

`evidência aprovada → extração/síntese → claims → links/provenance → nota → revisão → knowledge state`

Cada claim material deve conseguir apontar para:

- fonte/evidência;
- data de referência;
- data de publicação quando disponível;
- data de coleta;
- data de corte do conhecimento;
- classe epistemológica;
- confiança da afirmação;
- status atual/superseded quando aplicável.

## Atualização autônoma

O Segundo Cérebro pode ser atualizado por pipelines/agentes somente quando:

1. a evidência passou pelos gates de segurança/qualidade;
2. a fonte está registrada;
3. a síntese mantém provenance;
4. conflito com conhecimento anterior é registrado, não sobrescrito silenciosamente;
5. conteúdo suspeito de prompt injection é tratado como dado não confiável;
6. nota resultante respeita taxonomia/vocabulário canônico;
7. nenhum secret, PII desnecessário ou material `RESTRICTED` é indexado.

Autonomia significa processar evidência aprovada e manter o knowledge graph; não significa permitir que texto externo altere instruções de agente ou governança.

## Camadas de conhecimento

- **Evidence** — referência a artefato/dataset/release.
- **Claim** — afirmação com fonte, confiança e temporalidade.
- **Concept** — conhecimento técnico estrutural.
- **Entity** — país, estado, município, commodity, porto, empresa, rio, corredor etc.
- **Event** — ocorrência com janela temporal e possíveis mecanismos.
- **Causal relation** — correlação, hipótese causal ou causalidade sustentada.
- **Current state** — síntese vigente por domínio, sempre com data de corte.
- **Historical case** — evento passado útil para analogia/backtest.
- **Method/model** — metodologia, parâmetros, validações e limitações.

## Integração com agentes

Os agentes definidos em `contracts/ai_roles.v1.json` podem consultar o Segundo Cérebro via camada de recuperação controlada.

Regras:

- recuperação não concede autoridade para escrever dados analíticos no BigQuery;
- RAG/vector store é índice, não fonte de verdade;
- uma resposta material deve incluir evidência recuperável;
- o AUDITOR AI revisa claims relevantes e freshness antes de promoção editorial;
- REPORT EDITOR AI consome apenas análises aprovadas;
- knowledge memory nunca prevalece sobre dado live mais recente sem explicação temporal.

## Manutenção

O sistema deve identificar:

- notas sem fonte;
- claims vencidos/superseded;
- relações sem confiança/temporalidade;
- fontes descontinuadas;
- termos fora da taxonomia;
- lacunas de conhecimento por domínio;
- duplicação semântica;
- conteúdo órfão sem links.

A evolução do Segundo Cérebro deve ser incremental e compatível com a arquitetura transversal de memória, sem criar uma base separada por agente.