from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from .clinical_phrases import (
    STRENGTH_PHRASES,
    WEAKNESS_PHRASES,
    SATISFACTORY_PHRASES,
    PHASE_SPECIFIC_TEMPLATES,
    SUMMARY_TEMPLATES,
    RECOMMENDATIONS_BY_EMPHASIS,
)


def format_time(seconds: Optional[float]) -> str:
    if seconds is None:
        return "--:--"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def get_duration(start: Optional[float], end: Optional[float]) -> Optional[float]:
    if start is None or end is None:
        return None
    return end - start


def get_metric_status(score: float) -> Tuple[str, str]:
    if score <= 0:
        return ("Not Rated", "—")
    elif score >= 4.5:
        return ("Excellence", "★")
    elif score >= 4.0:
        return ("Strength", "✓")
    elif score >= 3.0:
        return ("Satisfactory", "✓")
    elif score >= 2.0:
        return ("Needs Practice", "⚠")
    else:
        return ("Critical", "✗")


def get_average_score(phase_id: str, scores: Dict, metrics: Dict) -> float:
    phase_scores = scores.get(phase_id, {})
    phase_metrics = metrics.get(phase_id, [])
    scored_values = []
    for metric in phase_metrics:
        metric_id = metric["id"]
        score = phase_scores.get(metric_id, 0)
        if score > 0:
            scored_values.append(score)
    if not scored_values:
        return 0.0
    return round(sum(scored_values) / len(scored_values), 1)


def get_overall_statistics(phases: List[Dict], scores: Dict, metrics: Dict) -> Dict:
    total_score = 0.0
    scored_count = 0
    total_duration = 0.0
    for phase in phases:
        pid = phase["id"]
        avg = get_average_score(pid, scores, metrics)
        if avg > 0:
            total_score += avg
            scored_count += 1
        duration = get_duration(phase.get("startTime"), phase.get("endTime"))
        if duration:
            total_duration += duration
    overall_avg = round(total_score / scored_count, 1) if scored_count > 0 else 0.0
    return {
        "avg_score": overall_avg,
        "total_duration": total_duration,
        "phases_count": len(phases),
        "phases_with_scores": scored_count,
    }


def get_score_category(avg_score: float) -> str:
    if avg_score >= 4.0:
        return "high"
    elif avg_score >= 3.0:
        return "medium"
    return "low"


def get_tone_label(tone: int) -> str:
    labels = {
        0: "Very Critical",
        1: "Critical",
        2: "Balanced",
        3: "Encouraging",
        4: "Very Encouraging",
    }
    return labels.get(tone, "Balanced")


def generate_phase_narrative(
    phase: Dict,
    phase_metrics: List[Dict],
    phase_scores: Dict[str, float],
    avg_score: float,
    tone: int,
) -> str:
    phase_id = phase["id"]
    phase_name = phase["name"]
    strengths = []
    weaknesses = []
    satisfactory = []
    for metric in phase_metrics:
        mid = metric["id"]
        score = phase_scores.get(mid, 0)
        mname = metric["name"]
        if score <= 0:
            continue
        if score >= 4.0:
            strengths.append((mname, score))
        elif score <= 2.5:
            weaknesses.append((mname, score))
        else:
            satisfactory.append((mname, score))
    strengths.sort(key=lambda x: x[1], reverse=True)
    weaknesses.sort(key=lambda x: x[1])
    sentences = []
    phase_specific = PHASE_SPECIFIC_TEMPLATES.get(phase_id, {})

    if strengths and not weaknesses:
        if phase_specific.get("strength"):
            sentences.append(phase_specific["strength"])
        else:
            strength_names = [s[0] for s in strengths]
            opener = STRENGTH_PHRASES["opener"].get(tone, STRENGTH_PHRASES["opener"][2])
            execution = STRENGTH_PHRASES["execution"].get(tone, STRENGTH_PHRASES["execution"][2])
            if len(strength_names) > 1:
                sentences.append(
                    f"{opener} {', '.join(strength_names[:-1])} and {strength_names[-1]}, "
                    f"{execution}"
                )
            else:
                sentences.append(f"{opener} {strength_names[0]}, {execution}")
    elif weaknesses and not strengths:
        if phase_specific.get("weakness"):
            sentences.append(phase_specific["weakness"])
        else:
            weakness_names = [w[0] for w in weaknesses]
            opener = WEAKNESS_PHRASES["opener"].get(tone, WEAKNESS_PHRASES["opener"][2])
            if len(weakness_names) > 1:
                sentences.append(
                    f"{opener} {', '.join(weakness_names[:-1])} and {weakness_names[-1]}."
                )
            else:
                sentences.append(f"{opener} {weakness_names[0]}.")
    else:
        if phase_specific.get("general"):
            sentences.append(phase_specific["general"])
        if strengths:
            strength_names = [s[0] for s in strengths[:3]]
            if len(strength_names) > 1:
                sentences.append(
                    f"Notable strengths include {', '.join(strength_names[:-1])} "
                    f"and {strength_names[-1]}, where performance was well-executed."
                )
            else:
                sentences.append(
                    f"A notable strength was {strength_names[0]}, "
                    f"where performance was well-executed."
                )
        if weaknesses:
            weakness_names = [w[0] for w in weaknesses[:3]]
            if len(weakness_names) > 1:
                sentences.append(
                    f"However, {', '.join(weakness_names[:-1])} and {weakness_names[-1]} "
                    f"would benefit from additional focused practice."
                )
            else:
                sentences.append(
                    f"However, {weakness_names[0]} would benefit from additional focused practice."
                )

    if weaknesses:
        closing = WEAKNESS_PHRASES["closing"].get(tone, WEAKNESS_PHRASES["closing"][2])
        sentences.append(closing)
    elif strengths and satisfactory:
        sentences.append(
            "Continued practice and refinement will help elevate this "
            "performance to an advanced level."
        )
    elif strengths:
        sentences.append(
            "This level of performance reflects solid training and should be "
            "maintained through consistent practice."
        )
    elif satisfactory:
        sentences.append(
            "Continued focused practice is recommended to develop greater consistency."
        )
    return " ".join(sentences)


def generate_summary(avg_score: float, tone: int, stats: Dict) -> str:
    category = get_score_category(avg_score)
    templates = SUMMARY_TEMPLATES.get(category, SUMMARY_TEMPLATES["medium"])
    summary = templates.get(tone, templates[2])
    stats_sentence = (
        f"The surgeon scored an average of {avg_score}/5 across "
        f"{stats['phases_with_scores']} evaluated phases."
    )
    return f"{stats_sentence} {summary}"


def generate_recommendations(
    phases: List[Dict], scores: Dict, metrics: Dict, emphasis: List[str]
) -> List[str]:
    recommendations = []
    all_low_metrics = []
    for phase in phases:
        pid = phase["id"]
        phase_scores = scores.get(pid, {})
        phase_metrics = metrics.get(pid, [])
        for metric in phase_metrics:
            mid = metric["id"]
            score = phase_scores.get(mid, 0)
            if 0 < score <= 2.5:
                all_low_metrics.append(
                    {"phase": phase["name"], "metric": metric["name"], "score": score}
                )
    all_low_metrics.sort(key=lambda x: x["score"])
    for item in all_low_metrics[:3]:
        recommendations.append(
            f"Improve {item['metric'].lower()} during the {item['phase']} phase "
            f"(current score: {item['score']}/5). "
            f"Focused simulation-based training is recommended."
        )
    for e in emphasis:
        emph_recs = RECOMMENDATIONS_BY_EMPHASIS.get(e, [])
        if emph_recs:
            recommendations.append(emph_recs[0])
    seen = set()
    unique = []
    for rec in recommendations:
        if rec not in seen:
            seen.add(rec)
            unique.append(rec)
    return unique[:5]


def build_header() -> str:
    today = datetime.now().strftime("%B %d, %Y")
    return (
        "# Surgical Procedure Evaluation Report\n\n"
        f"**Generated:** {today}\n"
        "**Procedure:** Cataract Surgery (Phacoemulsification)\n\n"
        "---"
    )


def build_executive_summary(
    phases: List[Dict], scores: Dict, metrics: Dict, stats: Dict, tone: int
) -> str:
    overall_avg = stats["avg_score"]
    total_dur = stats["total_duration"]
    dur_min = int(total_dur // 60)
    dur_sec = int(total_dur % 60)
    summary_text = generate_summary(overall_avg, tone, stats)
    return (
        "## Executive Summary\n\n"
        "This report evaluates the surgical performance across "
        f"**{stats['phases_count']} phases** with detailed skill metrics.\n\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        f"| Overall Average Score | **{overall_avg}/5.0** |\n"
        f"| Total Procedural Duration | **{dur_min}:{dur_sec:02d}** |\n"
        f"| Phases Evaluated | **{stats['phases_with_scores']}** |\n"
        f"| Report Tone | **{get_tone_label(tone)}** |\n\n"
        f"{summary_text}"
    )


def build_phase_section(phase: Dict, metrics: Dict, scores: Dict, tone: int) -> str:
    pid = phase["id"]
    name = phase["name"]
    start = format_time(phase.get("startTime"))
    end = format_time(phase.get("endTime"))
    duration = get_duration(phase.get("startTime"), phase.get("endTime"))
    duration_str = format_time(duration) if duration else "--:--"
    avg_score = get_average_score(pid, scores, metrics)
    technique = ""
    phaco_method = phase.get("phacoMethod")
    if phaco_method:
        method_display = phaco_method.replace("_", " ").title()
        technique = f"\n**Technique:** {method_display}"
    phase_metrics = metrics.get(pid, [])
    phase_scores = scores.get(pid, {})
    table_rows = []
    for metric in phase_metrics:
        mid = metric["id"]
        mname = metric["name"]
        mscore = phase_scores.get(mid, 0)
        status_label, status_icon = get_metric_status(mscore)
        score_display = f"{mscore}/5" if mscore > 0 else "—"
        table_rows.append(f"| {mname} | {score_display} | {status_icon} {status_label} |")
    table_header = "| Skill | Score | Status |\n|-------|-------|--------|"
    table_body = (
        "\n".join(table_rows)
        if table_rows
        else "| _No metrics evaluated_ | - | - |"
    )
    narrative = generate_phase_narrative(
        phase, phase_metrics, phase_scores, avg_score, tone
    )
    return (
        f"### {name} ({start} -> {end} | Duration: {duration_str}){technique}\n\n"
        "**Skills Assessment:**\n"
        f"{table_header}\n"
        f"{table_body}\n"
        f"**Phase Average: {avg_score}/5**\n\n"
        f"{narrative}"
    )


def build_strengths_weaknesses(
    phases: List[Dict], scores: Dict, metrics: Dict
) -> Tuple[List[str], List[str]]:
    all_strengths = []
    all_weaknesses = []
    for phase in phases:
        pid = phase["id"]
        phase_name = phase["name"]
        phase_scores = scores.get(pid, {})
        phase_metrics = metrics.get(pid, [])
        for metric in phase_metrics:
            mid = metric["id"]
            score = phase_scores.get(mid, 0)
            if score >= 4.5:
                all_strengths.append(
                    f"**{metric['name']}** during {phase_name} ({score}/5)"
                )
            elif score <= 2.5 and score > 0:
                all_weaknesses.append(
                    f"**{metric['name']}** during {phase_name} ({score}/5)"
                )
    return all_strengths, all_weaknesses


def build_overall_assessment(
    phases: List[Dict], scores: Dict, metrics: Dict
) -> str:
    strengths, weaknesses = build_strengths_weaknesses(phases, scores, metrics)
    sections = ["## Overall Assessment\n"]
    if strengths:
        sections.append("### Strengths\n")
        for s in strengths:
            sections.append(f"1. {s}")
        sections.append("")
    if weaknesses:
        sections.append("### Areas for Improvement\n")
        for w in weaknesses:
            sections.append(f"1. {w}")
        sections.append("")
    if not strengths and not weaknesses:
        sections.append(
            "_Insufficient data for comprehensive strength/weakness analysis. "
            "More skill evaluations are needed._\n"
        )
    return "\n".join(sections)


def build_recommendations_section(
    phases: List[Dict], scores: Dict, metrics: Dict, emphasis: List[str]
) -> str:
    recs = generate_recommendations(phases, scores, metrics, emphasis)
    if not recs:
        return (
            "## Recommendations\n\n"
            "_No specific recommendations generated. "
            "Add more skill evaluations for detailed feedback._"
        )
    lines = ["## Recommendations\n"]
    for i, rec in enumerate(recs, 1):
        lines.append(f"{i}. {rec}")
    return "\n".join(lines)


def build_footer() -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    return (
        "---\n\n"
        f"*Report generated by SurgiNote AI Clinical Report Service on {today}*\n"
        "*This is an AI-assisted evaluation. "
        "Final clinical assessment should be made by a qualified supervisor.*"
    )


def generate_clinical_report(
    phases: List[Dict],
    metrics: Dict[str, List[Dict]],
    scores: Dict[str, Dict[str, float]],
    settings: Dict,
) -> str:
    tone = settings.get("tone", 2)
    emphasis = settings.get("emphasis", ["technical", "safety"])
    recorded_phases = [
        p
        for p in phases
        if p.get("startTime") is not None and p.get("endTime") is not None
    ]
    if not recorded_phases:
        raise ValueError(
            "No recorded phases with valid time ranges found. "
            "At least one phase with startTime and endTime is required."
        )
    recorded_phases.sort(key=lambda p: p.get("startTime", 0))
    stats = get_overall_statistics(recorded_phases, scores, metrics)
    sections = [
        build_header(),
        build_executive_summary(recorded_phases, scores, metrics, stats, tone),
    ]
    for phase in recorded_phases:
        sections.append(build_phase_section(phase, metrics, scores, tone))
    sections.append(build_overall_assessment(recorded_phases, scores, metrics))
    sections.append(
        build_recommendations_section(recorded_phases, scores, metrics, emphasis)
    )
    sections.append(build_footer())
    return "\n\n".join(sections)
