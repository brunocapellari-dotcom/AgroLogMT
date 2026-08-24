from __future__ import annotations

import json
import unittest
from pathlib import Path

from collector.models import SourceSpec


class EvidenceClassTests(unittest.TestCase):
    def test_projection_and_qualitative_signal_are_supported(self) -> None:
        for evidence_class in ("observado", "estimado", "projetado", "inferido", "sinal_qualitativo", "negociado_autorizado"):
            spec = SourceSpec(
                source_id=f"fixture_{evidence_class}",
                name="Fixture",
                group="dados",
                method="http",
                evidence_class=evidence_class,
            )
            self.assertEqual(spec.evidence_class, evidence_class)

    def test_schema_enum_matches_runtime_contract(self) -> None:
        schema = json.loads(Path("contracts/canonical_record_metadata.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(schema["properties"]["evidence_class"]["enum"]),
            {"observado", "estimado", "projetado", "inferido", "sinal_qualitativo", "negociado_autorizado"},
        )


if __name__ == "__main__":
    unittest.main()
