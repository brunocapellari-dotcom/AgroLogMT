from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]


def module_present(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def run_step(name: str, command: list[str], allow_unavailable: bool = False) -> tuple[str, str]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode == 0:
        return "PASS", output
    if allow_unavailable:
        return "SKIP", output
    return "FAIL", output


def load_config(path: str | None) -> dict:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    return json.loads(config_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgroLog MT Radar PoCs in one command")
    parser.add_argument(
        "--config",
        default=None,
        help="JSON opcional. Sem config, nenhuma chamada de rede externa é feita.",
    )
    args = parser.parse_args()
    config = load_config(args.config)

    py = sys.executable
    results: list[tuple[str, str, str]] = []

    status, output = run_step(
        "contracts",
        [py, "-m", "unittest", "-v", "experiments.radar_poc_suite.tests.test_contracts"],
    )
    results.append(("contracts", status, output))

    status, output = run_step(
        "doctor",
        [py, "experiments/radar_poc_suite/doctor.py"],
    )
    results.append(("doctor", status, output))

    if module_present("langgraph"):
        status, output = run_step(
            "langgraph",
            [
                py,
                "experiments/radar_poc_suite/langgraph_poc.py",
                "Pergunta sintética de validação da orquestração AgroLog",
            ],
        )
    else:
        status, output = "SKIP", "LangGraph não instalado"
    results.append(("langgraph", status, output))

    if module_present("vectorbt"):
        status, output = run_step(
            "vectorbt",
            [py, "experiments/radar_poc_suite/vectorbt_poc.py"],
        )
    else:
        status, output = "SKIP", "VectorBT não instalado"
    results.append(("vectorbt", status, output))

    crawl_url = config.get("crawl_url")
    if crawl_url and module_present("crawl4ai"):
        status, output = run_step(
            "crawl4ai",
            [py, "experiments/radar_poc_suite/crawl4ai_poc.py", str(crawl_url)],
        )
    elif crawl_url:
        status, output = "SKIP", "Crawl4AI não instalado"
    else:
        status, output = "SKIP", "crawl_url não configurada; rede externa não acionada"
    results.append(("crawl4ai", status, output))

    media = config.get("whisper_media")
    if media and module_present("whisper"):
        command = [py, "experiments/radar_poc_suite/whisper_poc.py", str(media)]
        model = config.get("whisper_model")
        if model:
            command += ["--model", str(model)]
        status, output = run_step("whisper", command)
    elif media:
        status, output = "SKIP", "Whisper não instalado"
    else:
        status, output = "SKIP", "whisper_media não configurada"
    results.append(("whisper", status, output))

    market_url = config.get("polymarket_url")
    if market_url and module_present("polymarket"):
        status, output = run_step(
            "polymarket",
            [py, "experiments/radar_poc_suite/polymarket_poc.py", str(market_url)],
        )
    elif market_url:
        status, output = "SKIP", "Polymarket SDK não instalado"
    else:
        status, output = "SKIP", "polymarket_url não configurada; rede externa não acionada"
    results.append(("polymarket", status, output))

    if config.get("run_ollama_health", True):
        status, output = run_step(
            "ollama",
            [py, "experiments/radar_poc_suite/ollama_poc.py", "--health"],
            allow_unavailable=True,
        )
    else:
        status, output = "SKIP", "Ollama health desabilitado na configuração"
    results.append(("ollama", status, output))

    # LibreChat mock, HyperFrames e code-server são validados por contratos estáticos
    # no teste determinístico para não abrir servidores/serviços no executor único.
    results.append(("librechat", "PASS" if results[0][1] == "PASS" else "BLOCKED", "validado por contratos estáticos"))
    results.append(("hyperframes", "PASS" if results[0][1] == "PASS" else "BLOCKED", "fixture/governança validados por contratos"))
    results.append(("code-server", "PASS" if results[0][1] == "PASS" else "BLOCKED", "bind localhost validado por contratos"))

    print("\nAgroLog MT — Radar PoC Suite")
    print("=" * 72)
    for name, status, output in results:
        first_line = output.splitlines()[0] if output else ""
        print(f"{name:14} {status:8} {first_line[:90]}")

    failed = [name for name, status, _ in results if status in {"FAIL", "BLOCKED"}]
    if failed:
        print("\nFalhas:", ", ".join(failed))
        return 1
    print("\nSuite concluída. SKIP significa dependência/entrada externa ainda não disponível.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
