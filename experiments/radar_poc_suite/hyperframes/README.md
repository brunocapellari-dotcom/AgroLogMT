# HyperFrames publication PoC

Objetivo: validar HyperFrames somente como **camada de publicação**, nunca como motor de dados ou análise.

## Entrada do PoC

`approved_report.json` é um fixture sintético com `approved_for_render=true`.

Contrato obrigatório antes de qualquer render:

- `approved_for_render = true`;
- `governance.may_recalculate_indicators = false`;
- `governance.may_change_conclusions = false`;
- revisão humana obrigatória antes de publicação externa automática.

## Execução futura

O ambiente deve usar a versão oficial corrente do HyperFrames e seguir a documentação do projeto no momento do teste. A ferramenta atualmente requer runtime Node moderno e FFmpeg para renderização local.

Fluxo desejado:

```text
relatório aprovado
    ↓
JSON/roteiro congelado
    ↓
HyperFrames
    ↓
preview
    ↓
revisão humana
    ↓
MP4/publicação
```

## O que medir

- tempo de render;
- fidelidade dos números e textos ao fixture aprovado;
- ausência de recalculação/reinterpretação;
- legibilidade em celular;
- capacidade de usar gráficos/mapas já produzidos pelo AgroLog;
- custo operacional de renderização;
- facilidade de substituir a ferramenta.

## Fora de escopo

- gerar conclusão analítica;
- buscar dados;
- alterar números;
- publicar automaticamente conteúdo real sem revisão;
- transformar HyperFrames em dependência do pipeline de dados.
