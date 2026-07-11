"""Multi-agent pipeline orchestrator — async parallel phase analysis + fallback."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.application.ai_pipeline.agents.data_extractor import DataExtractorAgent
from app.application.ai_pipeline.agents.markers_analyzer import MarkersAnalyzerAgent
from app.application.ai_pipeline.agents.phase_analyzer import PhaseAnalyzerAgent
from app.application.ai_pipeline.agents.quality_reviewer import QualityReviewerAgent
from app.application.ai_pipeline.agents.report_composer import ReportComposerAgent
from app.application.ai_pipeline.cache import get_llm_cache
from app.application.ai_pipeline.config import AIPipelineConfig, load_ai_pipeline_config
from app.application.ai_pipeline.fallback.report_service import generate_clinical_report
from app.application.ai_pipeline.schemas import NormalizedData, PipelineMetadata
from app.application.ai_pipeline.token_manager import TokenManager
from app.infrastructure.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(
        self,
        config: AIPipelineConfig | None = None,
        llm_client: LLMClient | None = None,
        *,
        data_extractor: DataExtractorAgent | None = None,
        phase_analyzer: PhaseAnalyzerAgent | None = None,
        markers_analyzer: MarkersAnalyzerAgent | None = None,
        report_composer: ReportComposerAgent | None = None,
        quality_reviewer: QualityReviewerAgent | None = None,
    ) -> None:
        self.config = config or load_ai_pipeline_config()
        self.llm_client = llm_client or LLMClient.from_settings(
            provider=self.config.provider.value,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout_seconds=self.config.timeout_seconds,
            fallback_provider=(
                self.config.fallback_provider.value if self.config.fallback_provider else None
            ),
        )
        self.cache = get_llm_cache(
            ttl_seconds=self.config.cache_ttl_seconds,
            enabled=self.config.enable_cache,
        )
        self.token_manager = TokenManager()
        agent_kwargs = {
            "temperature": self.config.temperature,
            "max_retries": self.config.max_retries,
            "cache": self.cache,
            "token_manager": self.token_manager,
            "max_tokens": self.config.max_tokens,
        }
        self.data_extractor = data_extractor or DataExtractorAgent(self.llm_client, **agent_kwargs)
        self.phase_analyzer = phase_analyzer or PhaseAnalyzerAgent(self.llm_client, **agent_kwargs)
        self.markers_analyzer = markers_analyzer or MarkersAnalyzerAgent(self.llm_client, **agent_kwargs)
        self.report_composer = report_composer or ReportComposerAgent(self.llm_client, **agent_kwargs)
        self.quality_reviewer = quality_reviewer or QualityReviewerAgent(self.llm_client, **agent_kwargs)

    async def run(
        self,
        phases: list[dict[str, Any]],
        metrics: dict[str, Any],
        scores: dict[str, Any],
        markers: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        agents_used: list[str] = ["data_extractor"]
        tokens_in = 0
        tokens_out = 0
        cache_hits = 0

        ai_config = settings.get("ai_config") or {}
        enable_review = (
            ai_config.get("enable_review")
            if ai_config.get("enable_review") is not None
            else self.config.enable_review
        )
        parallel_phases = (
            ai_config.get("parallel_phases")
            if ai_config.get("parallel_phases") is not None
            else True
        )
        enable_cache = (
            ai_config.get("enable_cache")
            if ai_config.get("enable_cache") is not None
            else self.config.enable_cache
        )
        self.cache.enabled = bool(enable_cache)
        cache_kw = {"enable_cache": bool(enable_cache)}
        tone = int(settings.get("tone", 2))
        locale = settings.get("locale", "en")

        try:
            raw = {
                "phases": phases,
                "metrics": metrics,
                "scores": scores,
                "markers": markers,
            }
            extracted = await asyncio.to_thread(self.data_extractor.process, raw)
            if extracted.get("error"):
                raise RuntimeError(str(extracted["error"]))

            normalized = NormalizedData.model_validate(extracted)
            tokens_in, tokens_out = self._accumulate_tokens(
                tokens_in, tokens_out, self.data_extractor
            )
            cache_hits += self._cache_hit_count(self.data_extractor)

            phase_analyses, phase_tin, phase_tout, phase_cache_hits = await self._analyze_phases(
                normalized=normalized,
                tone=tone,
                locale=locale,
                parallel=parallel_phases,
                cache_kw=cache_kw,
            )
            agents_used.append(f"phase_analyzer({len(phase_analyses)} parallel instances)")
            tokens_in += phase_tin
            tokens_out += phase_tout
            cache_hits += phase_cache_hits

            markers_analysis = await asyncio.to_thread(
                self.markers_analyzer.process,
                {
                    "markers": [m.model_dump(mode="json") for m in normalized.normalized_markers],
                    "scores": normalized.scores,
                    "phases": [p.model_dump(mode="json") for p in normalized.normalized_phases],
                    "tone": tone,
                },
            )
            agents_used.append("markers_analyzer")
            tokens_in, tokens_out = self._accumulate_tokens(
                tokens_in, tokens_out, self.markers_analyzer
            )
            cache_hits += self._cache_hit_count(self.markers_analyzer)

            composer_input = {
                "phase_analyses": phase_analyses,
                "markers_analysis": markers_analysis,
                "normalized": normalized.model_dump(mode="json"),
                "settings": settings,
            }
            report = await asyncio.to_thread(self.report_composer.process, composer_input)
            agents_used.append("report_composer")
            tokens_in, tokens_out = self._accumulate_tokens(
                tokens_in, tokens_out, self.report_composer
            )
            cache_hits += self._cache_hit_count(self.report_composer)

            quality_score = None
            if enable_review:
                review = await asyncio.to_thread(
                    self.quality_reviewer.process,
                    {"report": report.get("content", ""), "settings": settings},
                )
                agents_used.append("quality_reviewer")
                tokens_in, tokens_out = self._accumulate_tokens(
                    tokens_in, tokens_out, self.quality_reviewer
                )
                cache_hits += self._cache_hit_count(self.quality_reviewer)
                quality_score = review.get("overall_quality_score")
                if not review.get("approved", True):
                    retry_input = {
                        **composer_input,
                        "revision_notes": review.get("suggested_fixes", []),
                    }
                    report = await asyncio.to_thread(self.report_composer.process, retry_input)
                    agents_used.append("report_composer(revision)")
                    tokens_in, tokens_out = self._accumulate_tokens(
                        tokens_in, tokens_out, self.report_composer
                    )
                    cache_hits += self._cache_hit_count(self.report_composer)

            confidence = self._aggregate_confidence(phase_analyses, markers_analysis, report)
            elapsed = round(time.perf_counter() - started, 2)
            metadata = PipelineMetadata(
                pipeline="ai-agent-v2",
                agents_used=agents_used,
                model=self.llm_client.model,
                tokens_used={"input": tokens_in, "output": tokens_out, "total": tokens_in + tokens_out},
                generation_time_seconds=elapsed,
                confidence_score=confidence,
                fallback_used=False,
                cache_hits=cache_hits,
                quality_score=quality_score,
            )
            return {
                "content": report["content"],
                "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "metadata": metadata.model_dump(mode="json"),
            }
        except Exception as exc:
            logger.exception("pipeline failed — falling back to rule-based report")
            return self._fallback_to_rule_based(
                phases=phases,
                metrics=metrics,
                scores=scores,
                settings=settings,
                error=str(exc),
                started=started,
            )

    async def _analyze_phases(
        self,
        *,
        normalized: NormalizedData,
        tone: int,
        locale: str,
        parallel: bool,
        cache_kw: dict[str, bool],
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        phases = normalized.normalized_phases
        tokens_in = 0
        tokens_out = 0
        cache_hits = 0

        if not parallel:
            analyses = []
            for phase in phases:
                analysis, tin, tout, hit = await self._run_single_phase(
                    phase, normalized, tone, locale, cache_kw
                )
                analyses.append(analysis)
                tokens_in += tin
                tokens_out += tout
                cache_hits += hit
            return analyses, tokens_in, tokens_out, cache_hits

        sem = asyncio.Semaphore(max(1, self.config.max_parallel))

        async def _guarded(phase) -> tuple[dict[str, Any] | Exception, int, int, int]:
            async with sem:
                try:
                    return await self._run_single_phase(phase, normalized, tone, locale, cache_kw)
                except Exception as exc:
                    return exc, 0, 0, 0

        gathered = await asyncio.gather(*[_guarded(p) for p in phases], return_exceptions=False)
        analyses: list[dict[str, Any]] = []
        for phase, item in zip(phases, gathered, strict=True):
            if isinstance(item[0], Exception):
                logger.warning("phase_analyzer failed phase_id=%s error=%s", phase.id, item[0])
                analyses.append(PhaseAnalyzerAgent.failure_template(phase.id))
            else:
                analysis, tin, tout, hit = item
                analyses.append(analysis)
                tokens_in += tin
                tokens_out += tout
                cache_hits += hit
        return analyses, tokens_in, tokens_out, cache_hits

    async def _run_single_phase(
        self,
        phase,
        normalized: NormalizedData,
        tone: int,
        locale: str,
        cache_kw: dict[str, bool],
    ) -> tuple[dict[str, Any], int, int, int]:
        agent = PhaseAnalyzerAgent(
            self.llm_client,
            temperature=self.config.temperature,
            max_retries=self.config.max_retries,
            cache=self.cache,
            token_manager=self.token_manager,
            max_tokens=self.config.max_tokens,
            **cache_kw,
        )
        payload = {
            "phase": phase.model_dump(mode="json"),
            "metrics": [m.model_dump(mode="json") for m in normalized.metrics.get(phase.id, [])],
            "scores": normalized.scores.get(phase.id, {}),
            "tone": tone,
            "locale": locale,
        }
        result = await asyncio.to_thread(agent.process, payload)
        chat = agent.last_chat
        tin = int(chat.tokens_in or 0) if chat else 0
        tout = int(chat.tokens_out or 0) if chat else 0
        hit = self._cache_hit_count(agent)
        return result, tin, tout, hit

    @staticmethod
    def _cache_hit_count(agent) -> int:
        return int(getattr(agent, "last_cache_hit", False))

    @staticmethod
    def _accumulate_tokens(tokens_in: int, tokens_out: int, agent) -> tuple[int, int]:
        chat = getattr(agent, "last_chat", None)
        if chat:
            tokens_in += int(chat.tokens_in or 0)
            tokens_out += int(chat.tokens_out or 0)
        return tokens_in, tokens_out

    @staticmethod
    def _aggregate_confidence(
        phase_analyses: list[dict[str, Any]],
        markers_analysis: dict[str, Any],
        report: dict[str, Any],
    ) -> float:
        scores = [float(a.get("confidence_score", 0)) for a in phase_analyses]
        scores.append(float(markers_analysis.get("confidence_score", 0)))
        scores.append(float(report.get("confidence_score", 0)))
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 2)

    def _fallback_to_rule_based(
        self,
        *,
        phases: list[dict[str, Any]],
        metrics: dict[str, Any],
        scores: dict[str, Any],
        settings: dict[str, Any],
        error: str,
        started: float,
    ) -> dict[str, Any]:
        try:
            content = generate_clinical_report(phases, metrics, scores, settings)
        except Exception as fallback_exc:
            logger.exception("rule-based fallback also failed")
            content = (
                "# Surgical Procedure Evaluation Report\n\n"
                "_Report generation failed. Please verify annotation_data "
                "includes at least one phase with startTime and endTime._\n\n"
                f"**Error:** {error}\n\n"
                f"**Fallback error:** {fallback_exc}"
            )
        elapsed = round(time.perf_counter() - started, 2)
        metadata = PipelineMetadata(
            pipeline="ai-agent-v2",
            agents_used=["rule_based_fallback"],
            model="rule_based",
            tokens_used={"input": 0, "output": 0, "total": 0},
            generation_time_seconds=elapsed,
            confidence_score=0.5,
            fallback_used=True,
            fallback_reason=error,
        )
        return {
            "content": content,
            "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "metadata": metadata.model_dump(mode="json"),
        }
