from __future__ import annotations

from dataclasses import dataclass

# Parâmetros agroclimatológicos avaliados nesta PoC (Issue #15), todos
# confirmados via chamada real (comunidade "ag"). Escopo deliberadamente
# pequeno: temperatura e precipitação (sinal agroclimático mínimo) mais
# umidade relativa (relevante para janela de colheita/secagem). Radiação
# solar (``ALLSKY_SFC_SW_DWN``) e vento (``WS2M``) foram testados e
# respondem normalmente, mas ficam fora do conjunto padrão desta PoC —
# ver `docs/sources/nasa_power/README.md` para a lista completa avaliada.
CORE_PARAMETERS: tuple[str, ...] = ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M")


@dataclass(frozen=True)
class PointConfig:
    """Ponto de referência (lat/lon) já validado nesta avaliação (Issue #15).

    Guarda só o necessário para consulta genérica ao endpoint
    ``temporal/daily/point``. Regras de mapeamento para tabelas do
    BigQuery ficam fora deste módulo até que haja decisão de carga (fora
    do escopo desta avaliação/PoC).
    """

    municipio: str
    uf: str
    latitude: float
    longitude: float
    relevance_mt: str
    notes: str = ""


# Coordenadas aproximadas da sede municipal (não do centroide da área
# plantada); suficiente para uma PoC de série climática regional — a
# resolução nativa da API é ~0.5° (~50 km), então precisão de poucos km no
# ponto de consulta não muda o pixel de origem retornado.
KNOWN_POINTS: dict[str, PointConfig] = {
    "sorriso_mt": PointConfig(
        municipio="Sorriso",
        uf="MT",
        latitude=-12.5453,
        longitude=-55.7217,
        relevance_mt="direta",
        notes=(
            "Um dos maiores produtores de soja e milho do Brasil, região "
            "norte/centro do MT (cinturão soja-milho safrinha)."
        ),
    ),
    "rondonopolis_mt": PointConfig(
        municipio="Rondonópolis",
        uf="MT",
        latitude=-16.4708,
        longitude=-54.6356,
        relevance_mt="direta",
        notes=(
            "Polo logístico e de esmagamento de soja do sul do MT, "
            "relevante para o recorte de armazéns/logística do AgroLog."
        ),
    ),
}
