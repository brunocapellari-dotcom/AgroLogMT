from __future__ import annotations

from dataclasses import dataclass


# "Disaggregated - Combined" (futuros + opções combinados, café da manhã de
# posições por classificação: Producer/Merchant, Swap Dealers, Managed
# Money, Other Reportables) — confirmado via
# ``GET /api/views/kh3c-gbw2.json`` como category "Commitments of Traders",
# distinto do relatório "Legacy" (mais agregado, sem separar
# produtor/comercial de fundo) e do "Disaggregated - Futures Only"
# (72hh-3qpy, sem opções). Combined foi escolhido por refletir a posição
# líquida real de mercado usada em análise de sinal especulativo/comercial.
DISAGGREGATED_COMBINED_DATASET_ID = "kh3c-gbw2"

DATE_FIELD = "report_date_as_yyyy_mm_dd"

# Intervalo (em dias) tolerado entre os dois relatórios semanais mais
# recentes e distintos. O CFTC publica toda sexta-feira com dados de
# posição de terça-feira; feriados podem adiar em alguns dias. Generoso de
# propósito — o objetivo é pegar regressão grosseira (cadência real virando
# mensal), não flutuação normal de calendário.
CADENCE_TOLERANCE_DAYS: tuple[int, int] = (5, 15)


@dataclass(frozen=True)
class ContractConfig:
    """Identidade de um contrato futuro já validado nesta avaliação (Issue #14).

    Guarda só o necessário para descoberta/consulta genérica dentro do
    dataset Disaggregated-Combined. Regras de mapeamento para tabelas do
    BigQuery ficam fora deste módulo até que haja decisão de carga (fora do
    escopo desta avaliação/PoC).
    """

    market_and_exchange_names: str
    cftc_contract_market_code: str
    commodity_name: str
    relevance_mt: str
    notes: str = ""


KNOWN_CONTRACTS: dict[str, ContractConfig] = {
    "soybeans_cbot": ContractConfig(
        market_and_exchange_names="SOYBEANS - CHICAGO BOARD OF TRADE",
        cftc_contract_market_code="005602",
        commodity_name="SOYBEANS",
        relevance_mt="direta",
        notes=(
            "Contrato padrão de soja da CBOT (não o 'MINI SOYBEANS'), maior "
            "open interest do grupo — referência de posicionamento "
            "especulativo/comercial para o principal produto de exportação "
            "do MT."
        ),
    ),
    "corn_cbot": ContractConfig(
        market_and_exchange_names="CORN - CHICAGO BOARD OF TRADE",
        cftc_contract_market_code="002602",
        commodity_name="CORN",
        relevance_mt="direta",
        notes=(
            "Contrato padrão de milho da CBOT — segundo produto prioritário "
            "do MT conforme ordem de prioridade da Fase B/D "
            "(soja, milho, comercialização)."
        ),
    ),
}
