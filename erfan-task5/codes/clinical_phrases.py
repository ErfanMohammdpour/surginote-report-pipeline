"""
Standard clinical wording for rule-based report generation (fallback path).

Used by report_service.py when LLM is unavailable — NOT by AI agents.
Tone keys 0–4: Very Critical → Very Encouraging.
"""

STRENGTH_PHRASES = {
    "opener": {
        0: "Adequate performance was noted in",
        1: "Competent handling was demonstrated in",
        2: "Strong proficiency was demonstrated in",
        3: "Excellent execution was observed in",
        4: "Outstanding mastery was demonstrated in",
    },
    "execution": {
        0: "though further refinement is required.",
        1: "with identifiable room for improvement.",
        2: "with consistent technique throughout the phase.",
        3: "showing clear clinical skill and control.",
        4: "reflecting exemplary surgical technique.",
    },
}

WEAKNESS_PHRASES = {
    "opener": {
        0: "Significant deficiencies were observed in",
        1: "Notable areas requiring improvement include",
        2: "Areas for improvement include",
        3: "Skills that would benefit from additional practice include",
        4: "Opportunities for continued growth include",
    },
    "closing": {
        0: "Immediate supervised remediation is strongly recommended.",
        1: "Focused supervised training is recommended to address these gaps.",
        2: "Additional focused practice is recommended to improve consistency.",
        3: "Continued deliberate practice will help strengthen these skills.",
        4: "With continued effort and guidance, these skills can be developed further.",
    },
}

SATISFACTORY_PHRASES: dict[str, dict[int, str]] = {}

PHASE_SPECIFIC_TEMPLATES: dict[str, dict[str, str]] = {
    "phase_3": {
        "strength": (
            "The capsulorhexis was executed with appropriate control and "
            "continuous curvilinear technique."
        ),
        "weakness": (
            "Capsulorhexis technique showed inconsistency that may increase "
            "risk during subsequent steps."
        ),
        "general": (
            "Capsulorhexis performance reflects the foundational importance "
            "of this phase for overall case safety."
        ),
    },
    "phase_rhexis": {
        "strength": (
            "The capsulorhexis was executed with appropriate control and "
            "continuous curvilinear technique."
        ),
        "weakness": (
            "Capsulorhexis technique showed inconsistency that may increase "
            "risk during subsequent steps."
        ),
        "general": (
            "Capsulorhexis performance reflects the foundational importance "
            "of this phase for overall case safety."
        ),
    },
    "phase_4": {
        "strength": (
            "Phacoemulsification was performed with effective energy management "
            "and stable chamber maintenance."
        ),
        "weakness": (
            "Phaco technique would benefit from improved energy efficiency "
            "and nuclear fragment handling."
        ),
        "general": (
            "Phacoemulsification performance is central to case efficiency "
            "and endothelial protection."
        ),
    },
    "phase_phaco": {
        "strength": (
            "Phacoemulsification was performed with effective energy management "
            "and stable chamber maintenance."
        ),
        "weakness": (
            "Phaco technique would benefit from improved energy efficiency "
            "and nuclear fragment handling."
        ),
        "general": (
            "Phacoemulsification performance is central to case efficiency "
            "and endothelial protection."
        ),
    },
    "phase_ia": {
        "general": (
            "Irrigation and aspiration performance affects cortical cleanup "
            "and preparation for lens implantation."
        ),
    },
}

SUMMARY_TEMPLATES: dict[str, dict[int, str]] = {
    "high": {
        0: "Overall performance meets expectations with minor refinements possible.",
        1: "Overall performance is solid with a few targeted improvements recommended.",
        2: "Overall performance demonstrates strong surgical competence across evaluated phases.",
        3: "Overall performance reflects skilled execution and good clinical judgment.",
        4: "Overall performance is excellent and reflects advanced surgical proficiency.",
    },
    "medium": {
        0: "Overall performance is acceptable but several skills require focused improvement.",
        1: "Overall performance is developing; targeted practice is recommended.",
        2: "Overall performance is satisfactory with clear opportunities for refinement.",
        3: "Overall performance shows promise with encouraging areas of competence.",
        4: "Overall performance is encouraging with a solid foundation to build upon.",
    },
    "low": {
        0: "Overall performance indicates significant gaps requiring structured remediation.",
        1: "Overall performance suggests substantial skill development is needed.",
        2: "Overall performance requires focused improvement across multiple skill areas.",
        3: "Overall performance shows effort; continued guided practice is essential.",
        4: "Overall performance demonstrates willingness to learn; keep building core skills.",
    },
}

RECOMMENDATIONS_BY_EMPHASIS: dict[str, list[str]] = {
    "technical": [
        "Review instrument handling and micro-movement efficiency through simulation drills.",
    ],
    "safety": [
        "Prioritize anterior chamber stability and wound integrity in all practice sessions.",
    ],
    "efficiency": [
        "Focus on reducing phase duration without compromising technique or safety.",
    ],
    "communication": [
        "Practice verbalizing key steps and potential complications during simulated cases.",
    ],
}
