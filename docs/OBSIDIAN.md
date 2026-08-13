# Obsidian — Segundo Cérebro do AgroLog MT

Versão arquitetural: 1.0  
Data: 2026-08-13

O Obsidian é a camada permanente de conhecimento do AgroLog MT. Ele organiza conhecimento técnico, histórico e contextual, relações causais, evidências e sínteses. Não substitui o GitHub como fonte canônica de código e documentação técnica nem o BigQuery como fonte única de verdade analítica.

## Responsabilidades canônicas

- **BigQuery** = dados estruturados, séries históricas e camada analítica oficial.
- **Drive/armazenamento documental** = documentos-fonte e artefatos pesados.
- **GitHub** = código, contratos, schemas, SQL, testes, configuração e documentação técnica.
- **Obsidian** = significado dos dados, conceitos, metodologias, evidências, relações, memória histórica, estudos e sínteses.
- **AgroLog Gateway** = camada controlada de consulta/ações para dados e serviços homologados.

## Fluxos oficiais

### Dados estruturados

API / CSV / XLSX / dado tabular extraído  
→ coleta e validação  
→ BigQuery  
→ AgroLog Gateway/consultas  
→ análise ou síntese relevante  
→ Obsidian apenas quando houver conhecimento duradouro.

### Documentos

PDF / livro / artigo / tese / manual / relatório / norma  
→ Drive  
→ dados estruturáveis, quando existirem → BigQuery  
→ conhecimento, metodologia, contexto, relações e evidências → Obsidian.

## Regra de não duplicação

O Obsidian não é banco de dados. Não copiar séries diárias, semanais ou mensais do BigQuery para notas. Registrar no Obsidian:

- definição e interpretação de variáveis e indicadores;
- metodologia e limitações;
- eventos e quebras estruturais;
- relações causais e hipóteses;
- evidências com rastreabilidade;
- sínteses de estado atual;
- comparáveis históricos;
- decisões e ambiguidades.

Quando um valor pontual for necessário para explicar uma afirmação, ele deve estar ligado à fonte/evidência e à data de referência; isso não transforma a nota em repositório da série.

## Processamento de publicações recorrentes por diferença

Uma nova edição não cria automaticamente uma nova nota completa. Comparar com o estado anterior e registrar:

- o que mudou;
- o que permaneceu;
- o que foi revisado;
- o que foi superseded;
- impacto, evidência e grau de confiança.

Manter notas vivas quando a responsabilidade for o estado atual; manter notas de evento/estudo quando houver valor histórico próprio.

## Evidência e tempo

Toda afirmação material deve usar as classes de `docs/DATA_GOVERNANCE.md`:

- observado;
- cadastro;
- calculo;
- inferencia;
- estimativa;
- projecao;
- sinal_indireto;
- negociado_autorizado.

Separar sempre **qualidade da fonte** de **confiança da afirmação**.

Preservar quando aplicável:

- `competencia`;
- `data_referencia`;
- `data_publicacao`;
- `data_coleta`;
- `data_corte_estudo`.

`data_corte_estudo` é obrigatória em estudos retrospectivos/backtests quando for necessária para impedir look-ahead bias.

## Escopo canônico

O Segundo Cérebro pode abranger, de forma conectada e incremental:

1. produção agrícola e safras;
2. agronomia, solos e sistemas de produção;
3. sementes, genética, fitossanidade e bioinsumos;
4. clima e agroclima;
5. hidrologia, rios, irrigação e recursos hídricos;
6. uso da terra, ambiente e sustentabilidade;
7. fertilizantes, defensivos e demais insumos;
8. agropecuária, pastagens e alimentação animal;
9. agroindústria: soja, etanol, biodiesel, açúcar, ração, bioenergia e biomassa;
10. armazenagem, pós-colheita, secagem, aeração, classificação e qualidade de grãos;
11. comercialização, oferta e demanda;
12. preço físico, prêmio, basis, paridade e economia do produtor;
13. CBOT, futuros, opções, CFTC e gestão de risco;
14. comércio exterior, barreiras SPS/TBT e acesso a mercados;
15. portos, line-up, operação portuária e transporte marítimo;
16. rodovias, fretes, diesel, pedágios, ferrovias e hidrovias;
17. infraestrutura, investimentos, chokepoints e resiliência da cadeia;
18. petróleo, energia, macroeconomia, crédito e seguro rural;
19. política agrícola, regulação, contratos e práticas comerciais;
20. empresas, cooperativas, tradings e agentes da cadeia;
21. geopolítica e choques globais;
22. tecnologia agrícola, rastreabilidade e compliance;
23. estrutura fundiária, mão de obra e demografia rural;
24. saúde animal e bioseguridade;
25. estudos históricos, eventos extremos e relações causais;
26. inteligência científica e biblioteca técnico-científica;
27. metodologia e qualidade das fontes.

O conhecimento de pecuária pode existir e se conectar no Obsidian. O relatório operacional de gado de corte continua separado do relatório agrícola/logístico principal.

## Biblioteca técnico-científica

Para livros, artigos, teses, manuais e publicações relevantes, registrar quando disponível:

- título;
- autores;
- instituição/editora;
- ano/edição;
- DOI/ISBN;
- assunto;
- região;
- metodologia;
- principais resultados;
- limitações;
- qualidade da evidência;
- afirmações aproveitáveis;
- estudos que confirmam ou contradizem;
- página/seção de origem;
- referência ao documento original no Drive.

OpenAlex e Crossref podem apoiar descoberta e verificação bibliográfica, mas não substituem a leitura e avaliação da fonte original.

## Templates canônicos

Os templates ficam em `knowledge/_templates/` e devem funcionar em Markdown puro, sem dependência conceitual de Dataview, Templater, Bases ou plugins equivalentes.

Tipos iniciais:

- conceito;
- fonte;
- variável;
- indicador;
- evento;
- estudo;
- empresa;
- infraestrutura;
- estado atual/síntese.

Plugins podem automatizar preenchimento ou consultas, mas a informação essencial precisa permanecer legível em editor Markdown comum.

## Piloto vertical: Soja Mato Grosso

Não expandir o vault inteiro antes de validar uma cadeia completa. O piloto inicial está em `knowledge/20_PILOTOS/Soja MT/MOC - Soja MT.md` e conecta:

produção/safra → clima → comercialização → oferta/demanda → armazenagem → preço físico → CBOT/câmbio/prêmio/basis → BR-163/logística terrestre → ferrovia/hidrovia quando aplicável → Arco Norte/Santos/Paranaguá → line-up/exportação → China/EUA/Argentina → eventos históricos → relações causais.

Critérios do piloto:

- perguntas respondidas com evidência rastreável;
- citações recuperáveis até a fonte original;
- funcionamento em Markdown puro;
- retrabalho inferior a 10% na amostra do piloto;
- ambiguidades registradas;
- ausência de cópia de séries do BigQuery;
- relações entre notas úteis para análise.

A expansão deve ocorrer por cadeias completas após a validação do piloto, não por criação massiva de pastas ou notas rasas.
