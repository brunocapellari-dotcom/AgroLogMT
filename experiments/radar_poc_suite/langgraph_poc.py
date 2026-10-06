from __future__ import annotations

import argparse
from typing import TypedDict


class AgroLogState(TypedDict, total=False):
    question: str
    evidence: list[str]
    specialist: str
    skeptic: str
    decision: str
    audit_status: str


def specialist_node(state: AgroLogState) -> dict:
    evidence = state.get("evidence") or ["fixture_sintetico_sem_dado_real"]
    return {
        "specialist": (
            f"Hipótese inicial para '{state['question']}'. "
            f"Base disponível: {', '.join(evidence)}."
        )
    }


def skeptic_node(state: AgroLogState) -> dict:
    return {
        "skeptic": (
            "Contraponto obrigatório: a hipótese ainda não prova causalidade, "
            "pode sofrer viés de amostra e deve ser confrontada com evidência temporal."
        )
    }


def auditor_node(state: AgroLogState) -> dict:
    has_evidence = bool(state.get("evidence"))
    status = "PASS_WITH_LIMITATIONS" if has_evidence else "BLOCKED_NO_EVIDENCE"
    decision = (
        "Conclusão experimental permitida, preservando limitações e sem promoção a fato observado."
        if has_evidence
        else "Conclusão bloqueada: nenhuma evidência foi fornecida."
    )
    return {"audit_status": status, "decision": decision}


def build_graph():
    try:
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise SystemExit(
            "LangGraph não instalado. Use o ambiente isolado e requirements-optional.txt."
        ) from exc

    builder = StateGraph(AgroLogState)
    builder.add_node("specialist", specialist_node)
    builder.add_node("skeptic", skeptic_node)
    builder.add_node("auditor", auditor_node)
    builder.set_entry_point("specialist")
    builder.add_edge("specialist", "skeptic")
    builder.add_edge("skeptic", "auditor")
    builder.add_edge("auditor", END)
    return builder.compile(checkpointer=MemorySaver())


def main() -> int:
    parser = argparse.ArgumentParser(description="PoC LangGraph — AgroLog MT")
    parser.add_argument("question")
    args = parser.parse_args()

    graph = build_graph()
    initial: AgroLogState = {
        "question": args.question,
        "evidence": ["fixture_sintetico_sem_dado_real"],
    }
    result = graph.invoke(
        initial,
        config={"configurable": {"thread_id": "agrolog-radar-poc"}},
    )

    print("SPECIALIST:", result.get("specialist"))
    print("SKEPTIC:", result.get("skeptic"))
    print("AUDIT:", result.get("audit_status"))
    print("DECISION:", result.get("decision"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
