from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.application.analyzers.base import AnalysisResult, BaseAnalyzer, Provenance


class TimelineAnalyzer(BaseAnalyzer):
    name = "TimelineAnalyzer"
    version = "1.0.0"

    def analyze(self, normalized_data: dict[str, Any]) -> AnalysisResult:
        comments = normalized_data.get("comments") or []
        phases = normalized_data.get("phases") or []

        timed = [c for c in comments if c.get("timestamp") is not None]
        density: dict[str, float] = {}

        for ph in phases:
            st, et = float(ph.get("start_time", 0)), float(ph.get("end_time", 0))
            dur_min = max((et - st) / 60.0, 0.01)
            cnt = sum(1 for c in timed if st <= float(c["timestamp"]) <= et)
            density[ph["name"]] = round(cnt / dur_min, 3)

        # clusters: 30s window, >=3 comments
        clusters = []
        timed_sorted = sorted(timed, key=lambda c: float(c["timestamp"]))
        i = 0
        while i < len(timed_sorted):
            j = i
            while j < len(timed_sorted) and float(timed_sorted[j]["timestamp"]) - float(timed_sorted[i]["timestamp"]) <= 30:
                j += 1
            if j - i >= 3:
                clusters.append(
                    {
                        "start": timed_sorted[i]["timestamp"],
                        "count": j - i,
                        "window_seconds": 30,
                    }
                )
                i = j
            else:
                i += 1

        by_minute: dict[int, int] = defaultdict(int)
        for c in timed:
            by_minute[int(float(c["timestamp"]) // 60)] += 1

        return AnalysisResult(
            analyzer_name=self.name,
            analyzer_version=self.version,
            data={
                "total_comments": len(comments),
                "timed_comments": len(timed),
                "phase_density_comments_per_minute": density,
                "activity_clusters": clusters,
                "distribution_by_minute": dict(sorted(by_minute.items())),
            },
            provenance=Provenance(
                source_records=[f"comment_{i:03d}" for i in range(len(comments))],
                calculation_method="phase_density_and_sliding_window",
                input_values=[c.get("timestamp") for c in timed],
                analyzer_version=self.version,
            ),
        )
