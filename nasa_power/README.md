# nasa_power

Avaliação/PoC da API [NASA POWER](https://power.larc.nasa.gov/) (Prediction
Of Worldwide Energy Resources), endpoint `temporal/daily/point`, para dados
agroclimatológicos diários (temperatura, precipitação, umidade relativa) em
pontos de referência do Mato Grosso.

Implementa o subconjunto sem exigência de chave nova da Issue #15
("Integrar fontes complementares de clima e hidrologia"): entre as fontes
candidatas aprovadas pela Issue (NASA POWER, ERA5/AgERA5 via Copernicus,
ANA HidroWebService, NASA FIRMS, NOAA/USGS Water, USACE Rivergages), esta
avaliação cobre **apenas o NASA POWER**. Ver
`docs/sources/nasa_power/README.md` para a avaliação completa, incluindo o
resultado do teste direto das demais fontes.

## O que este módulo faz

- `build_client()` — `NasaPowerClient` travado no host oficial
  `https://power.larc.nasa.gov` (sem parâmetro `base_url`, mesma garantia
  usada em `cftc_cot.build_client`).
- `daily_point(...)` — consulta `GET /api/temporal/daily/point`, valida
  latitude/longitude/community/datas antes de montar a query, e normaliza
  o resultado: valores iguais a `fill_value` (`-999.0`) viram `None` em vez
  de serem lidos como leitura real.
- `points.py` (`KNOWN_POINTS`, `CORE_PARAMETERS`) — pontos de referência e
  conjunto de parâmetros agroclimatológicos já validados nesta avaliação.

## O que este módulo *não* faz

- Não carrega nada no BigQuery. Avaliação de termos, cadência, schema e
  qualidade antes de qualquer decisão de carga.
- Não requer chave/token: os endpoints usados são de leitura pública.
- Não cobre ERA5/AgERA5, ANA HidroWebService, NASA FIRMS, NOAA/USGS Water
  nem USACE Rivergages — fora do escopo desta avaliação (ver
  `docs/sources/nasa_power/README.md`).
- Não cobre `temporal/monthly`, `temporal/climatology` nem `regional` —
  só o endpoint `temporal/daily/point`.

## Uso básico

```python
from nasa_power import build_client, CORE_PARAMETERS, KNOWN_POINTS

client = build_client()
point = KNOWN_POINTS["sorriso_mt"]

result = client.daily_point(
    latitude=point.latitude,
    longitude=point.longitude,
    start="20260101",
    end="20260107",
    parameters=CORE_PARAMETERS,
)
print(result.units["T2M"], result.values["T2M"])
```

## Testes

```bash
pip install -r nasa_power/requirements-dev.txt
python -m pytest -q nasa_power/tests
```

`tests/test_client.py` cobre validação de entrada, parsing (inclusive
normalização de `fill_value`) e tratamento de erro com HTTP mockado,
determinístico, sem rede. `tests/test_points_live.py` faz chamadas reais à
API NASA POWER e usa `pytest.skip` automaticamente, em toda chamada de
rede, se a plataforma estiver inacessível no ambiente — não falha o build
por indisponibilidade externa. Inclui regressão de faixa fisicamente
plausível e de classificação observado/modelado (fontes declaradas pela
API precisam continuar incluindo satélite/reanálise, não virar estação
terrestre silenciosamente).
