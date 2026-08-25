# Onda sem Claude Code

Arquivos principais desta onda:

- `docs/NO_CLAUDE_EXECUTION_2026-08-25.md`: status operacional e blockers reais.
- `docs/BETA_OPERATIONAL_INPUTS_2026-08-25.md`: evidências usadas na primeira Beta.
- `collector/news_signal_producers.py`: produtores determinísticos de NEWS_SIGNAL v0.5.
- `tests/test_news_signal_producers.py`: gates dos produtores.

A onda não substitui a homologação GCP. Ela reduz o trabalho restante à execução autenticada e às fontes que exigem secret/runtime específico.
