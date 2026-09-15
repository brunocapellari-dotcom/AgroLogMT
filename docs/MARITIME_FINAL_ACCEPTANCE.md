# AgroLog Maritime Intelligence — Final Acceptance

## Regra de produto

O AgroLog Maritime Intelligence é entregue como um sistema único. Não existe promoção de produção por módulo. Um componente pode ter métricas, versão de modelo ou evidência própria para diagnóstico, mas **nenhum subconjunto do sistema recebe o estado final**.

O único estado de liberação é `FINAL_READY`, calculado por `models/maritime_final_readiness.py` e regido por `contracts/maritime_final_acceptance.v1.json`.

Se qualquer gate obrigatório estiver ausente, falhar, perder freshness ou não possuir evidência rastreável, o produto permanece `BLOCKED`.

## Teste de 100% do projeto

O workflow `.github/workflows/maritime-final-acceptance.yml` não possui filtro por pasta no evento de PR. Toda alteração destinada a `main` executa uma aceitação única que cobre a superfície completa consumida pelo Maritime:

- collectors e streaming;
- preservação RAW;
- qualidade AIS e identidade;
- geofences e port calls;
- line-ups e reconciliação;
- ETA e filas;
- weather marítimo;
- trade flow;
- anomalias e alertas;
- source health;
- BigQuery/storage;
- Gateway/API;
- Maritime UI;
- segurança e supply chain;
- imagens de container;
- scripts, contratos e workflows.

O runner `scripts/maritime_final_acceptance.py --static-only` executa a aceitação completa de código/build/segurança sem fazer alegação de operação real. O retorno máximo deste modo é `STATIC_ACCEPTANCE_PASS_OPERATIONAL_EVIDENCE_REQUIRED`.

`FINAL_READY` exige adicionalmente evidência operacional externa para todos os gates definidos no contrato.

## Gates finais

Os gates obrigatórios são, em conjunto:

1. testes completos do repositório;
2. security gate;
3. supply-chain gate;
4. branch protection;
5. WIF com mínimo privilégio;
6. segredos externalizados;
7. Gateway privado;
8. AIS real nos cinco portos;
9. qualidade AIS validada;
10. resiliência de stream validada;
11. vessel identity validado;
12. line-up fresco nos cinco portos;
13. geofences validadas nos cinco portos;
14. port calls com validação >=95%;
15. ETA validado fora da amostra;
16. modelos de fila com histórico suficiente;
17. weather marítimo governado;
18. trade flow governado;
19. source health operacional;
20. backup/restore testado;
21. resposta a incidente testada;
22. homologação end-to-end contínua de sete dias.

A lista canônica existe simultaneamente no contrato JSON e no modelo Python. O teste `test_contract_and_runtime_gate_lists_are_identical` impede drift entre as duas representações.

## Evidência e epistemologia

Nenhum gate é satisfeito por texto declarativo. A evidência precisa conter referência e timestamp. As classificações permanecem distintas:

- `OBSERVADO` — medição/evento observado por fonte adequada;
- `INFORMADO` — informação publicada/programada pela fonte;
- `ESTIMADO` — cálculo a partir de observações e hipóteses;
- `PROJETADO` — forecast/cenário futuro;
- `INFERIDO` — conclusão indireta com incerteza explícita;
- `SOURCE_LAG` — atraso conhecido da própria fonte.

Programação não vira realizado. Uma mensagem AIS não vira estado físico. `SPOOFING_SUSPECTED` não vira `SPOOFING_CONFIRMED` sem evidência independente.

## Cinco portos piloto

A aceitação final cobre simultaneamente:

- Santos;
- Paranaguá;
- Barcarena / Vila do Conde;
- Santarém;
- Itaqui.

O produto não recebe `FINAL_READY` se apenas parte dos portos estiver homologada.

## Segurança

Security e supply chain são gates de release, não auditorias informativas. A aceitação cobre:

- segredos atuais e histórico Git;
- Bandit;
- auditoria de dependências Python;
- auditoria de dependências npm;
- análise de workflows GitHub Actions;
- containers não-root e build reproduzível na medida permitida pelas dependências;
- IAM/WIF e ausência de service-account keys persistentes;
- Gateway privado;
- direitos/licenciamento das fontes;
- incident response;
- backup e restore.

Findings críticos ou altos não tratados impedem `FINAL_READY`.

## Modelos

O produto pode ser final enquanto um modelo explícito permanece `V1`, desde que:

- a capacidade esteja claramente versionada;
- a incerteza seja exibida;
- o gate mínimo de validação do modelo esteja cumprido;
- não exista substituição silenciosa de dado observado por previsão;
- o modelo não seja promovido quando faltarem amostra, histórico ou benchmark.

Isso separa **completude do produto** de **maturidade estatística de cada modelo** sem aceitar uma entrega modular incompleta.
