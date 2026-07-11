"""Application service for AI report generation API."""

from __future__ import annotations

from app.api.schemas import GenerateReportRequest
from app.application.ai_pipeline.config import load_ai_pipeline_config, merge_ai_config
from app.application.ai_pipeline.orchestrator import PipelineOrchestrator
from app.infrastructure.llm.llm_client import LLMClient


def _ai_config_dict(request: GenerateReportRequest) -> dict:
    if not request.settings.ai_config:
        return {}
    return request.settings.ai_config.model_dump(exclude_none=True)


def build_orchestrator(request: GenerateReportRequest) -> PipelineOrchestrator:
    ai_cfg = _ai_config_dict(request)
    config = merge_ai_config(load_ai_pipeline_config(), ai_cfg)
    llm_client = LLMClient.from_settings(
        provider=config.provider.value,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout_seconds=config.timeout_seconds,
        fallback_provider=(
            config.fallback_provider.value if config.fallback_provider else None
        ),
    )
    return PipelineOrchestrator(config=config, llm_client=llm_client)


async def run_ai_report(request: GenerateReportRequest) -> dict:
    ai_cfg = _ai_config_dict(request)
    settings = {
        "tone": request.settings.tone,
        "emphasis": request.settings.emphasis,
        "locale": request.settings.locale,
        "ai_config": ai_cfg,
    }
    orchestrator = build_orchestrator(request)
    return await orchestrator.run(
        phases=[p.model_dump(mode="json") for p in request.phases],
        metrics={
            pid: [m.model_dump(mode="json") for m in metrics]
            for pid, metrics in request.metrics.items()
        },
        scores=request.scores,
        markers=[m.model_dump(mode="json") for m in request.markers],
        settings=settings,
    )
