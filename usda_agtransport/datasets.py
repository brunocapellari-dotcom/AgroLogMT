from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetConfig:
    """Identidade de um dataset AgTransport/USDA já validado (Issue #20).

    Guarda só o necessário para descoberta/consulta genérica. Regras de
    mapeamento para tabelas do BigQuery ficam fora deste módulo até que haja
    decisão de carga (fora do escopo desta avaliação/PoC).
    """

    dataset_id: str
    name: str
    cadence: str
    date_field: str
    relevance_mt: str
    notes: str = ""


# Tolerância (em dias) usada para validar, contra dados reais, que o
# intervalo entre os dois registros mais recentes é compatível com a
# cadência declarada. Generosa de propósito: datasets oficiais têm atraso
# de publicação (feriados, revisões), então o objetivo é pegar regressão
# grosseira (ex.: cadência trocada de trimestral para anual), não
# flutuação normal de calendário.
CADENCE_TOLERANCE_DAYS: dict[str, tuple[int, int]] = {
    "weekly": (1, 21),
    "monthly": (15, 100),
    "quarterly": (60, 200),
}


KNOWN_DATASETS: dict[str, DatasetConfig] = {
    "grain_transportation_cost_indicators": DatasetConfig(
        dataset_id="8uye-ieij",
        name="Grain Transportation Cost Indicators",
        cadence="weekly",
        date_field="date",
        relevance_mt="indireta",
        notes=(
            "Índices semanais de custo por modal (caminhão, ferrovia, "
            "barcaça, navio) nos EUA, base 2017=100. Referência de contexto "
            "para custos logísticos globais de grãos, não específico do MT."
        ),
    ),
    "brazil_us_soybean_transportation_cost_spreads": DatasetConfig(
        dataset_id="3j5w-mz4e",
        name="U.S. vs Brazil Soybean Transportation Cost Spreads",
        cadence="quarterly",
        date_field="date",
        relevance_mt="direta",
        notes=(
            "Spreads trimestrais de custo de transporte de soja "
            "(EUA vs. Brasil, incluindo origem 'north_mt') até Xangai. "
            "Série é derivada por cálculo de spread; dataset-base do valor "
            "publicado é o mesmo endpoint tabular."
        ),
    ),
    "brazil_soybean_truck_route_rates": DatasetConfig(
        dataset_id="wcku-8yrp",
        name="Quarterly Truck Rates for Selected Brazilian Soybean Export Transportation Routes",
        cadence="quarterly",
        date_field="quarter_ending_date",
        relevance_mt="direta",
        notes=(
            "Fretes rodoviários trimestrais por rota nomeada, incluindo "
            "rotas de origem 'North MT (Sorriso)' até Santos e Paranaguá — "
            "dataset mais diretamente relevante ao MT encontrado nesta "
            "avaliação."
        ),
    ),
    "brazil_soybean_monthly_truck_price_index": DatasetConfig(
        dataset_id="i4ty-m7hq",
        name="Monthly Brazilian Weighted Average Truck Prices for Exported Soybeans",
        cadence="monthly",
        date_field="month_year",
        relevance_mt="direta",
        notes=(
            "Índice mensal de preço médio ponderado de frete rodoviário "
            "para soja de exportação no Brasil (série agregada nacional, "
            "não desagregada por UF)."
        ),
    ),
    "downbound_grain_barge_rates": DatasetConfig(
        dataset_id="deqi-uken",
        name="Downbound Grain Barge Rates",
        cadence="weekly",
        date_field="date",
        relevance_mt="indireta",
        notes=(
            "Fretes de barcaça no sistema fluvial dos EUA (rio Mississippi "
            "e afluentes). Referência de contexto para escoamento "
            "concorrente ao Brasil, sem rota brasileira."
        ),
    ),
}
