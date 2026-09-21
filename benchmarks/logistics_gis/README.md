# Benchmark unificado de Logistica, GIS e Maritime

Objetivo: testar o stack selecionado sem manter duas ferramentas com a mesma funcao em producao.

## Componentes

- **Valhalla**: rotas rodoviarias, matriz/rota e plausibilidade frente ao limite geodesico.
- **OSMnx**: conectividade/topologia de uma amostra OSM quando acesso de rede for explicitamente permitido.
- **PyOsmium**: leitura bulk de PBF e contagem estrutural.
- **PyVRP**: caso deterministico de frota/capacidade/janela.
- **H3**: determinismo e validade do grid espacial.
- **pyais**: decode de NMEA conhecido.
- **port_call_engine AgroLog**: reproducibilidade/idempotencia da reconstrucao de port call.

As dependencias ficam em `requirements-benchmarks.txt`, fora dos containers de producao.

## Execucao local parcial

```bash
python -m pip install -r requirements-benchmarks.txt
python scripts/run_logistics_gis_benchmarks.py
```

Sem Valhalla/PBF/rede, esses componentes sao `SKIP` e o resultado e `PARTIAL`.

## Gate integral

```bash
python scripts/run_logistics_gis_benchmarks.py \
  --strict \
  --valhalla-url http://127.0.0.1:8002 \
  --osm-pbf /caminho/mato-grosso-latest.osm.pbf \
  --allow-network
```

Em `--strict`, qualquer `SKIP` ou `FAIL` bloqueia promocao.

## Regras

1. O manifest usa seeds de cidade/porto somente para benchmark. Nunca sao geofences/terminais operacionais.
2. Valhalla so vira CORE depois de benchmark com corredores reais e dados oficiais/observados.
3. PyVRP so vira CORE para VRP depois de caso operacional real e comparacao com baseline.
4. OSMnx/PyOsmium sao complementares: analise/QA versus leitura bulk.
5. H3 e o grid hierarquico padrao; nao adicionar segundo grid sem requisito medido.
6. pyais nao entra no caminho AISStream JSON atual.
7. Port-call continua engine proprio, com evidencia AIS separada de operacao oficial.
8. O relatorio JSON e evidencia de benchmark, nao dado canonico de producao.

Saida padrao: `outputs/benchmarks/logistics-gis.json`.
