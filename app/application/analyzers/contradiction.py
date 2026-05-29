from __future__ import annotations

from typing import Any

from app.application.analyzers.base import AnalysisResult, BaseAnalyzer, Provenance
from app.application.rules.engine import evaluate_rules, load_rules_config


class ContradictionAnalyzer(BaseAnalyzer):
    name = "ContradictionAnalyzer"
    version = "1.5.0"

    def __init__(self, *, rules_config: dict | None = None, locale: str = "en"):
        self._rules_config = rules_config
        self._locale = locale

    def analyze(self, normalized_data: dict[str, Any]) -> AnalysisResult:
        cfg = self._rules_config or load_rules_config()
        hits = evaluate_rules(normalized_data, config=cfg, locale=self._locale)
        flags = [
            {
                "id": f"{h.rule_id}_{i}",
                "rule_id": h.rule_id,
                "severity": h.severity,
                "message": h.message,
                "linkage": h.linkage,
                "evidence": h.evidence,
            }
            for i, h in enumerate(hits)
        ]
        return AnalysisResult(
            analyzer_name=self.name,
            analyzer_version=self.version,
            data={"flags": flags, "count": len(flags)},
            provenance=Provenance(
                source_records=[f["id"] for f in flags],
                calculation_method="yaml_rule_engine",
                input_values=[h.rule_id for h in hits],
                analyzer_version=self.version,
                config_snapshot={"rules_version": cfg.get("version")},
            ),
        )
