# AgroLog MT — Beta Operacional — Evidências de entrada — 25/08/2026

Corte operacional usado para a primeira edição Beta: manhã de 25/08/2026, horário de Mato Grosso.

## Hidrologia — OBSERVADO / SOURCE_LAG CONTROLADO

Fonte primária: ANA, Sala de Situação do Rio Madeira, boletim de 24/08/2026.

- Porto Velho (15400000): 24/08/2026, cota 4,23 m; vazão 6.987 m³/s.
- Humaitá (15630000): 24/08/2026, cota 11,94 m; vazão 8.396 m³/s.
- Porto Velho em 23/08/2026: 4,21 m; 6.961 m³/s.
- Humaitá em 23/08/2026: 12,01 m; 8.517 m³/s.
- Portanto, usando apenas os dois pontos publicados, Porto Velho variou +0,02 m no dia e Humaitá -0,07 m no dia. Não interpolar.
- O boletim informa que os dados de 24/08 são médias parciais do próprio dia e estão sujeitos a revisão.
- A ANA também lista boletim diário do Amazonas de 24/08/2026, mas os valores individuais não foram promovidos nesta evidência enquanto o arquivo detalhado não foi materializado/validado pelo pipeline.

Classificação: valores de cota/vazão = `OBSERVADO`; delta aritmético entre dois valores observados = `OBSERVADO_DERIVADO`; condição atual intradiária de 25/08 não é inferida a partir de 24/08.

## Comércio exterior — RELEASE_CHANGE / PRELIMINAR

Fonte primária: MDIC/SECEX, Informativo nº 040/2026, publicado em 24/08/2026 às 15h10 e atualizado às 15h11.

- O MDIC/SECEX confirmou resultados parciais da balança comercial com dados preliminares da 3ª semana de agosto/2026.
- Próxima divulgação consolidada informada para 04/09/2026, entre 15h e 15h30.
- O fato de a publicação existir pode gerar `RELEASE_CHANGE`.
- Números de produto/volume/valor não devem ser preenchidos a partir de fonte secundária quando o detalhe primário não estiver materializado no pipeline.

Classificação: existência/publicação = `OBSERVADO`; conteúdo mensal = `PRELIMINAR`; números não materializados = `BLOCKED_PRIMARY_DETAIL`.

## Câmbio — NOT_YET_PUBLISHED

Fonte primária e regra: BCB/PTAX.

- Na manhã de 25/08/2026 o fechamento PTAX do próprio dia ainda não deve ser tratado como publicado antes do boletim oficial de fechamento.
- Cotação intraday não substitui fechamento.
- Fechamento anterior nunca é rotulado como fechamento atual.

Classificação: `NOT_YET_PUBLISHED` até existir registro oficial `tipoBoletim=Fechamento` para 25/08/2026.

## Portos / line-up — PARTIAL_MULTI_PORT

Gate canônico: Santos + Paranaguá/Antonina + Arco Norte com observações oficiais recentes.

- A existência de páginas oficiais de programação não é suficiente para promover `MULTIPORT_VALIDATED`.
- Sem uma observação recente e materializada nos três sistemas, o status permanece `PARTIAL_MULTI_PORT`.
- `PROGRAMADO`, `ATRACADO`, `DESATRACADO` e `CONCLUIDO` são estados distintos.
- Tonelagem programada não vira realizada sem evidência explícita.

## Resultado editorial esperado da Beta

A edição deve mostrar os dados efetivamente observados, os deltas derivados reproduzíveis e, principalmente, as lacunas como estados explícitos. O objetivo desta Beta não é parecer completa; é provar que o sistema recusa substituir dado ausente por dado antigo, inferência ou programação.
