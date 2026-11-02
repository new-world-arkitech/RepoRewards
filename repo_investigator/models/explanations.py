from __future__ import annotations

from typing import Dict, Any

PLAIN_ENGLISH_GLOSSARY: Dict[str, Dict[str, str]] = {
    "TOPOLOGY_CYCLIC_DEPENDENCY": {
        "title": "Chicken-and-Egg Loop (Circular Dependency)",
        "plain_english": "File A needs File B to work, but File B also needs File A. They are tangled in a loop.",
        "why_it_matters": "When two files depend on each other, you can't test or change one without risking breaking the other.",
        "how_to_fix": "Extract the shared code into a third file or create an interface/protocol that both files can use.",
    },
    "TOPOLOGY_ACYCLIC": {
        "title": "Clean One-Way Dataflow (Acyclic Graph)",
        "plain_english": "Your code flows cleanly in one direction without circular loops.",
        "why_it_matters": "This makes the codebase easy to understand, test in pieces, and refactor safely.",
        "how_to_fix": "Keep maintaining layered boundaries so higher layers call lower layers, never in reverse.",
    },
    "HIGH_CENTRALITY_HUB": {
        "title": "Busy Traffic Intersection (Central Hub)",
        "plain_english": "This file is imported and used by almost every other file in your project.",
        "why_it_matters": "Any small bug or change in this file has a massive ripple effect across the entire app.",
        "how_to_fix": "Break this large file into smaller, specialized modules so no single file carries all the weight.",
    },
    "INVARIANT_LAYER_BOUNDARY_BREACH": {
        "title": "Layer Boundary Leak",
        "plain_english": "Core business rules are directly communicating with external services (like databases or web APIs).",
        "why_it_matters": "If you change your database or API provider tomorrow, you will have to rewrite your core business logic.",
        "how_to_fix": "Use an adapter or repository pattern: business logic should call an abstract adapter, not the database directly.",
    },
    "COGNITIVE_CHURN": {
        "title": "Friction Hotspot (High Churn)",
        "plain_english": "Developers have modified and patched this file far more than any other file in Git history.",
        "why_it_matters": "Repeated emergency edits usually indicate a confusing design, hidden bugs, or changing requirements.",
        "how_to_fix": "Refactor this file to clarify its single responsibility and add automated unit tests.",
    },
    "HACK_OR_WORKAROUND": {
        "title": "Temporary Patch / Workaround",
        "plain_english": "Commits or comments contain markers like 'quickfix', 'temp hack', or 'workaround'.",
        "why_it_matters": "Temporary fixes often stay in code for years, creating technical debt and unexpected side effects.",
        "how_to_fix": "Replace the quick patch with an architecturally sound design.",
    },
}

def get_plain_english_insight(category: str) -> Dict[str, str]:
    """
    Returns an accessible, beginner-friendly explanation for an architectural insight category.
    """
    if category in PLAIN_ENGLISH_GLOSSARY:
        return PLAIN_ENGLISH_GLOSSARY[category]
    return {
        "title": category.replace("_", " ").title(),
        "plain_english": "An architectural pattern was observed in this component.",
        "why_it_matters": "Preserving clean separation of concerns ensures long-term codebase health.",
        "how_to_fix": "Consult architectural best practices for modular software design.",
    }

