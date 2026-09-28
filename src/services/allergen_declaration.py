"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph"""

# Deterministic parser for allergen avoidances stated in the request text
# ("avoid shellfish", "no dairy", "nut-free", "allergic to eggs"). The standalone
# /invoke entry point only forwards the text, so without this parser a request
# saying "avoid shellfish" reached the planner with no declared allergen at all.
#
# Scope is deliberately narrow: only terms from this template's allergen
# vocabulary are recognised, only after an avoidance cue (or before "-free" /
# "allergy"), and the input is length-bounded. Over-matching (e.g. "not allergic
# to fish" also excludes fish) errs on the safe side for a food-safety filter.
# Plain functions only (Tool per the Agent-vs-Tool boundary).

from __future__ import annotations

import re
from typing import Any

MAX_TEXT_CHARS = 2000
_CUE_WINDOW_CHARS = 80

# canonical allergen -> surface terms (singular/plural, common members)
ALLERGEN_SYNONYMS: dict[str, tuple[str, ...]] = {
    "shellfish": ("shellfish", "shrimp", "shrimps", "prawn", "prawns", "crab", "crabs", "lobster", "lobsters"),
    "fish": ("fish", "salmon", "tuna", "cod"),
    "milk": ("milk", "dairy", "lactose", "cheese", "yogurt", "yoghurt", "butter", "cream"),
    "egg": ("egg", "eggs"),
    "soy": ("soy", "soya", "soybean", "soybeans", "tofu"),
    "peanut": ("peanut", "peanuts"),
    "tree nut": ("tree nut", "tree nuts", "nut", "nuts", "almond", "almonds", "walnut", "walnuts", "cashew", "cashews"),
    "wheat": ("wheat", "gluten"),
    "sesame": ("sesame",),
}

_TERM_TO_CANONICAL: dict[str, str] = {
    term: canonical for canonical, terms in ALLERGEN_SYNONYMS.items() for term in terms
}
# longest terms first so "tree nuts" wins over "nuts"
_TERM_ALT = "|".join(re.escape(t) for t in sorted(_TERM_TO_CANONICAL, key=len, reverse=True))
_TERM_RE = re.compile(rf"\b(?:{_TERM_ALT})\b")

_CUE_RE = re.compile(
    r"\b(?:avoid(?:ing)?|without|no|exclude|excluding|skip|free of|"
    r"allergic to|allergy to|allergies to|intolerant to|intolerance to|"
    r"can't eat|cannot eat|can not eat|don't eat|do not eat|not eat)\b"
)
# a clause break or a positive connector ends the scope of an avoidance cue
_WINDOW_END_RE = re.compile(r"[.;!?\n]|\b(?:but|with|including|plus)\b")
_SUFFIX_RE = re.compile(rf"\b({_TERM_ALT})[\s-](?:free|allergy|allergies|intolerance)\b")


def canonical_allergen(value: Any) -> str | None:
    """Map a declared allergen (any surface form) to its canonical name."""
    if not isinstance(value, str):
        return None
    term = value.strip().lower()
    if not term:
        return None
    return _TERM_TO_CANONICAL.get(term, term)


def parse_declared_allergens(text: Any) -> list[str]:
    """Return canonical allergens the text asks to avoid, in first-seen order."""
    if not isinstance(text, str) or not text:
        return []
    lowered = text[:MAX_TEXT_CHARS].lower().replace("\u2019", "'")
    found: list[str] = []

    def _add(term: str) -> None:
        canonical = _TERM_TO_CANONICAL[term]
        if canonical not in found:
            found.append(canonical)

    for cue in _CUE_RE.finditer(lowered):
        window = lowered[cue.end() : cue.end() + _CUE_WINDOW_CHARS]
        end = _WINDOW_END_RE.search(window)
        if end:
            window = window[: end.start()]
        for term in _TERM_RE.findall(window):
            _add(term)
    for match in _SUFFIX_RE.finditer(lowered):
        _add(match.group(1))
    return found


def merge_declared_allergens(context_allergens: Any, text: Any) -> list[str]:
    """Merge input_context allergens with text-declared ones (canonical, deduped)."""
    merged: list[str] = []
    items = context_allergens if isinstance(context_allergens, (list, tuple)) else []
    for value in list(items) + parse_declared_allergens(text):
        canonical = canonical_allergen(value)
        if canonical and canonical not in merged:
            merged.append(canonical)
    return merged
