# ANTT — dados ferroviários oficiais (Issue #17)

Avaliação do Portal de Dados Abertos da ANTT (`dados.antt.gov.br`) como
fonte de dados ferroviários oficiais para o AgroLog MT, conforme pedido
pela Issue #17: "fontes e licença documentadas, PoC concluída, schema e
dicionário definidos, observado e modelado separados, atualização
validada, DQ aprovado antes do BigQuery". **Nenhum dado foi carregado no
BigQuery nesta avaliação** — aprovação de DQ (`docs/DATA_GOVERNANCE.md`,
seção "Qualidade mínima por carga") ainda está pendente.

## Portal e acesso

`dados.antt.gov.br` expõe a API padrão do CKAN (`/api/3/action/...`), a
mesma já usada por `dadosabertos.aneel.gov.br`. O portal `"antt"` já está
validado em `ckan_connector/portals.py` (`KNOWN_PORTALS`), consolidado na
Issue #19 no mesmo dia desta avaliação — este trabalho reaproveita o
`CkanClient` existente em vez de reimplementar descoberta/download.

## Datasets avaliados

### 1. SIADE — Produção Origem Destino (dataset principal)

- Nome no CKAN: `sistema-de-acompanhamento-do-desempenho-operacional-das-concessionarias-siade`
- Título: "Sistema de Acompanhamento do Desempenho Operacional das
  Concessionárias - SIADE"
- Organização: Agência Nacional de Transportes Terrestres — ANTT
- Licença declarada pela API: `Creative Commons Atribuição` (`license_id:
  cc-by`)
- Descrição (`notes`): "Histórico da movimentação mensal de cargas nas
  ferrovias federais concedidas."
- 41 recursos: um par CSV+JSON de "Produção Origem Destino" por ano
  (2006–2025) mais um dicionário de dados em PDF
  (`producao_origem_destino_dicionario_dados.pdf`).

**Schema real** (confirmado baixando `producao_origem_destino_2025.csv`,
601.148 bytes, 7.799 linhas de dados + cabeçalho):

```
Mes_Ano;Ferrovia;Mercadoria_ANTT;Estacao_Origem;UF_Origem;Estacao_Destino;UF_Destino;TU;TKU
01/2025;RMN;Farelo de Soja;Alto Araguaia;MT;Santos;SP;82.776;115.953.447
01/2025;RMN;Grãos - Milho;Rondonópolis;MT;Santos;SP;4.154;6.829.997
```

- Delimitador `;`, **encoding `cp1252`, não UTF-8** — confirmado nesta
  avaliação decodificando o arquivo inteiro das duas formas: como UTF-8
  estrito, a decodificação falha (`UnicodeDecodeError`); como `cp1252`,
  decodifica sem nenhum caractere de substituição e produz acentuação
  portuguesa correta (`Álcool`, `Rondonópolis`). O teste
  `ckan_connector/tests/test_antt_ferrovias_live.py` reproduz essa mesma
  verificação contra o recurso real. Qualquer parser precisa declarar
  `cp1252` explicitamente.
- `TU` = toneladas úteis; `TKU` = toneladas-quilômetro útil. Números usam
  `.` como separador de milhar (formato BR), sem separador decimal visível
  nas amostras — precisa de validação adicional linha a linha antes de
  qualquer parsing numérico definitivo.
- `Mes_Ano` no formato `MM/AAAA` — competência mensal.
- O arquivo de 2025 cobre os 12 meses (01/2025 a 12/2025) por completo; não
  havia recurso para 2026 no momento desta avaliação. Os recursos CSV/JSON
  de 2025 têm `last_modified` em `2026-04-30`. **Inferência, não fato
  observado repetido**: um único `last_modified` mostra apenas a última
  modificação/republicação registrada no CKAN para esse recurso — não prova
  a data da primeira publicação nem que ~4 meses de defasagem seja uma
  cadência recorrente do processo da ANTT. Tratar como hipótese de
  planejamento (revisar quando o recurso de 2026 for publicado), não como
  cadência validada.

**Relevância para MT** (medida no arquivo de 2025 completo, não estimada):
427 das 7.799 linhas (bases anual) têm `UF_Origem` ou `UF_Destino` igual a
`MT`. As duas ferrovias que atendem MT nesse arquivo são `RMN` (Rumo Malha
Norte) e `RMP` (Rumo Malha Paulista). Principais mercadorias em linhas que
tocam MT (contagem de linhas, não volume): Contêiner Cheio de 40 Pés (65),
**Soja (58)**, Contêiner Vazio de 40 Pés (45), Cloreto de Potássio (36),
Adubo Orgânico a Granel (35), **Grãos - Milho (30)**, **Farelo de Soja
(29)**, Óleo Diesel (24), Ureia (20). Estações de origem em MT incluem
Rondonópolis, Alto Araguaia e Itiquira. **Inferência analítica** (leitura
das linhas observadas, não um fato declarado pela fonte): o padrão de
origem/destino e mercadoria sugere um corredor Rumo Malha Norte de
escoamento de soja/milho até Santos, com fertilizantes (cloreto de
potássio, ureia, fosfato) no sentido inverso — hipótese razoável a
confirmar com mais anos de dados antes de qualquer uso operacional.

### 2. RAAF — Acidentes Ferroviários (dataset secundário)

- Nome no CKAN: `relatorio-de-acompanhamento-de-acidentes-ferroviarios-raaf`
- Licença: `Creative Commons Atribuição` (CC-BY)
- Cadência declarada: semestral
- 5 recursos: dicionário de dados (PDF), série 2004–2020 (CSV), série
  dez/2020–jan/2026 (CSV), índice 2006–2019 (CSV) e índice 2006–2025
  (JSON). Recursos mais recentes com `last_modified` em `2026-04-10`.
- Uso previsto: indicador complementar de risco operacional por
  ferrovia/trecho, não substitui a Produção Origem Destino como fonte de
  volume.

### Datasets identificados mas não avaliados a fundo nesta passada

Via `package_search?q=ferrovia` no mesmo portal: `projeto-concessao-ferrovias`,
`projetos-autorizados`, `material-rodante`, `controle-de-penalidades-aplicadas`
— candidatos a PoC futura (contexto de malha/infraestrutura), fora do
escopo priorizado desta avaliação (mesmo critério de priorização usado na
avaliação USDA AgTransport, Issue #20: subconjunto relevante, não o
catálogo inteiro).

### Achado: link obtido por busca estava obsoleto

O dataset `transporte-ferroviario-de-cargas-e-passageiros` (encontrado via
busca web, referenciado como painel/dashboard) retorna `HTTP 403
"Acesso negado"` via `package_show` da API CKAN e `HTTP 404` na página do
portal — confirmado nesta avaliação, não apenas citado de memória. Não
apareceu nos resultados de `package_search?q=ferrovia`. O dataset
correspondente e atualmente acessível para o mesmo propósito (movimentação
de cargas ferroviárias) é o SIADE acima.

## Observado vs. modelado

Seguindo `docs/DATA_GOVERNANCE.md`:

- **Observado**: `TU` e `TKU` do SIADE são valores declarados pelas
  concessionárias à ANTT no cumprimento de obrigação regulatória de
  acompanhamento de desempenho — dado oficial primário, não inferido nem
  estimado pelo AgroLog. Mesmo tratamento já dado a CONAB/ANEEL/ANTT no
  projeto.
- **Observado**: registros do RAAF (acidentes) são igualmente declaração
  regulatória direta, não modelagem.
- Nenhum campo modelado/inferido/estimado foi produzido nesta avaliação —
  nenhuma carga foi feita.

## Campos temporais (mapeamento para carga futura)

- `data_referencia` → `Mes_Ano` (competência mensal, SIADE) ou o período do
  acidente (RAAF).
- `data_publicacao` → `last_modified`/`revision_timestamp` do recurso no
  CKAN (proxy: reflete a última republicação no portal, não
  necessariamente a data de emissão original do arquivo pela ANTT).
- `data_coleta` → timestamp da coleta pelo AgroLog (a definir no momento da
  implementação da carga real).
- `competencia` → mês/ano para o SIADE (`Mes_Ano` é o próprio período do
  dado). Para o RAAF, **proposta não confirmada**: a cadência de
  *publicação* do dataset é semestral, mas cada acidente tem sua própria
  data de ocorrência — frequência de publicação da fonte não define
  competência analítica do registro. O dicionário de dados do RAAF (PDF, não
  aberto nesta avaliação) precisa ser lido antes de fixar esse mapeamento.

## ONTL / Infra S.A. — bloqueio de rede nesta avaliação

`ontl.infrasa.gov.br` (fonte complementar citada na Issue #17 para
matrizes O/D multimodais) não pôde ser acessado a partir deste ambiente
nesta sessão: `WebFetch` retornou falha de resolução DNS
(`getaddrinfo ETIMEOUT ontl.infrasa.gov.br`). Não foi possível confirmar
diretamente formato de download, licença ou mecanismo de API — o que a
busca web indica (matrizes O/D 2017 e 2035, GeoPortal próprio, "sem
restrições" declaradas) **não foi verificado de primeira mão** e não deve
ser tratado como confirmado. Como o SIADE já fornece dado observado real
de movimentação ferroviária com granularidade mensal por rota, ONTL fica
como fonte complementar de menor prioridade, não bloqueante para o
restante da Issue #17. Registrado também em
`docs/NIGHT_RUN_BLOCKERS.md`.

## Termos de uso

Dado público federal (ANTT), licença CC-BY declarada pela API para os dois
datasets avaliados (SIADE e RAAF) — exige atribuição, sem exigência de
chave de API para os endpoints de leitura usados nesta avaliação.

## Próximos passos (fora do escopo desta avaliação)

1. Definir schema de destino no BigQuery (dataset `logistica`) e obter
   aprovação de DQ conforme `docs/DATA_GOVERNANCE.md` antes de qualquer
   carga.
2. Implementar parser específico (`cp1252`, `;`, formato numérico BR) sobre
   o `ckan_connector` genérico, análogo ao que já existe para CONAB
   Armazéns.
3. Reavaliar ONTL quando o portal estiver acessível a partir do ambiente de
   execução.
