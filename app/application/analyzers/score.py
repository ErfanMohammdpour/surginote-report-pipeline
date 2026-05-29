from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from app.application.analyzers.base import AnalysisResult, BaseAnalyzer, Provenance


class ScoreAnalyzer(BaseAnalyzer):
    name = "ScoreAnalyzer"
    version = "2.0.1"

    def analyze(self, normalized_data: dict[str, Any]) -> AnalysisResult:
        by_skill: dict[str, list[float]] = defaultdict(list)
        records: dict[str, list[str]] = defaultdict(list)

        for i, sk in enumerate(normalized_data.get("skills") or []):
            key = sk.get("name") or f"skill_{i}"
            val = float(sk["score"])
            by_skill[key].append(val)
            records[key].append(f"skill_{i:03d}")

        data: dict[str, Any] = {}
        all_vals: list[float] = []
        prov_inputs: dict[str, list[float]] = {}

        for skill, vals in sorted(by_skill.items()):
            all_vals.extend(vals)
            prov_inputs[skill] = vals
            mean = statistics.mean(vals)
            stdev = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            outliers = [v for v in vals if abs(v - mean) > 2 * stdev] if stdev else []
            data[skill] = {
                "mean": round(mean, 3),
                "median": round(statistics.median(vals), 3),
                "std_dev": round(stdev, 3),
                "min": min(vals),
                "max": max(vals),
                "outliers": outliers,
                "sample_count": len(vals),
            }

        overall_mean = round(statistics.mean(all_vals), 3) if all_vals else None
        data["overall_average"] = overall_mean

        return AnalysisResult(
            analyzer_name=self.name,
            analyzer_version=self.version,
            data=data,
            provenance=Provenance(
                source_records=[r for recs in records.values() for r in recs],
                calculation_method="arithmetic_mean",
                input_values=all_vals,
                analyzer_version=self.version,
            ),
        )
