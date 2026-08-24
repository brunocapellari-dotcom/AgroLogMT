#!/usr/bin/env python3
from __future__ import annotations

from zoneinfo import ZoneInfo

from scripts import generate_soy_mt_beta as beta01
from scripts import generate_soy_mt_beta_v02 as beta02

MT_TIMEZONE = "America/Cuiaba"


def configure_mt_timezone() -> None:
    # O beta V0.2 ainda reutiliza o helper de timezone do V0.1.
    # Centralizamos aqui a execução operacional em Mato Grosso sem reescrever o histórico do módulo antigo.
    beta01.SAO_PAULO = ZoneInfo(MT_TIMEZONE)


def main() -> int:
    configure_mt_timezone()
    return beta02.main()


if __name__ == "__main__":
    raise SystemExit(main())
