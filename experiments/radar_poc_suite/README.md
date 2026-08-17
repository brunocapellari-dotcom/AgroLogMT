# Suite integrada de PoCs do Radar

Issue: #47

Este diretório concentra provas de conceito **isoladas, removíveis e sem dados reais** para ferramentas aprovadas no Radar Tecnológico do AgroLog MT. A suite não é runtime de produção e não cria nova fonte de verdade.

## Princípios

- BigQuery continua sendo a fonte única de verdade analítica.
- GitHub guarda somente código, contratos, fixtures artificiais e documentação.
- Nenhum PoC recebe credencial real por padrão.
- Nenhum PoC escreve no BigQuery.
- LibreChat/cockpit só pode alcançar dados por AgroLog Gateway ou mock compatível, nunca por credencial direta de BigQuery.
- Polymarket é somente leitura e representa sinal de expectativa de mercado, não fato futuro.
- VectorBT é laboratório; não é dependência de produto.
- Ollama e code-server ficam restritos a localhost/rede protegida no PoC.
- HyperFrames recebe conteúdo já aprovado; não recalcula indicadores nem cria conclusão analítica.

## PoCs

| Componente | Arquivo/pasta | Objetivo | Rede externa no teste básico |
|---|---|---|---|
| Crawl4AI | `crawl4ai_poc.py` | Extrair página pública para Markdown/JSON | opcional, quando executado com URL pública |
| Whisper | `whisper_poc.py` | Transcrever arquivo local autorizado | não, exceto eventual download inicial do modelo |
| LangGraph | `langgraph_poc.py` | Demonstrar grafo especialista → cético → auditor | não |
| LibreChat | `librechat/` | Validar boundary do cockpit por mock OpenAI-compatible | não |
| VectorBT | `vectorbt_poc.py` | Validar sinal point-in-time com série sintética | não |
| Polymarket | `polymarket_poc.py` | Ler mercado público pelo SDK oficial | sim, somente leitura |
| Ollama | `ollama_poc.py` | Health-check e geração opcional em localhost | somente localhost |
| HyperFrames | `hyperframes/` | Preparar conteúdo aprovado para renderização | não no fixture |
| code-server | `code_server/` | Definir PoC seguro de ambiente web de desenvolvimento | não por padrão |

## Instalação opcional

Crie um ambiente virtual específico para os PoCs. Não instale essas dependências no runtime principal apenas para testar a suite.

```bash
python -m venv .venv-radar
# Windows
.venv-radar\Scripts\activate
# Linux/macOS
# source .venv-radar/bin/activate

pip install -r experiments/radar_poc_suite/requirements-optional.txt
```

Dependências pesadas (Whisper/Crawl4AI) podem exigir passos adicionais do projeto original, como FFmpeg e navegador. O PoC deve falhar com mensagem clara se a dependência não estiver instalada.

## Diagnóstico rápido

```bash
python experiments/radar_poc_suite/doctor.py
```

O comando apenas verifica presença de módulos e arquivos locais. Não instala nada e não acessa serviços externos.

## Execução isolada

### LangGraph
```bash
python experiments/radar_poc_suite/langgraph_poc.py "Há pressão logística no corredor X?"
```

### VectorBT
```bash
python experiments/radar_poc_suite/vectorbt_poc.py
```

### Whisper
```bash
python experiments/radar_poc_suite/whisper_poc.py caminho/arquivo.mp3 --model turbo
```

### Crawl4AI
```bash
python experiments/radar_poc_suite/crawl4ai_poc.py https://exemplo-publico.gov.br
```

### Polymarket (somente leitura)
```bash
python experiments/radar_poc_suite/polymarket_poc.py "URL_PUBLICA_DO_MERCADO"
```

### Ollama local
```bash
python experiments/radar_poc_suite/ollama_poc.py --health
```

### Mock do AgroLog Gateway para LibreChat
```bash
python experiments/radar_poc_suite/librechat/mock_gateway.py
```

O mock expõe uma API OpenAI-compatible somente em `127.0.0.1:8765`. Ele não acessa BigQuery nem qualquer dado real.

## Critério de promoção

Nenhuma ferramenta sai desta pasta para produção apenas porque o PoC executou. Para promoção é obrigatório abrir Issue própria, revisar licença/termos, segurança, observabilidade, custo, estratégia de saída, teste com caso AgroLog autorizado e impacto na arquitetura canônica.

## Ordem de integração

Os PoCs podem ser desenvolvidos/testados em paralelo, mas a adoção de produção continua respeitando os gates do projeto. Esta suite não altera P0/P1 nem substitui CONAB → Gateway → IMEA como caminho crítico do núcleo.
