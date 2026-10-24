import re

_URL = re.compile(r"https?://[^\s)\]>,]+")
_MARKER = re.compile(r"\[r:[0-9a-f]{12}\.[a-z_]+\]")
_DISCLAIMER = re.compile(
    r"(?i)\b(?:this|it|figures|results|they) (?:is|are) not "
    r"(?:a |financial |personal |tax |legal )*(?:recommendation|advice)\b"
)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction to the person",
        re.compile(
            r"(?i)\byou (?:should|ought to|need to|must|might want to|"
            r"may want to|could|should consider)\b"
        ),
    ),
    (
        "recommendation",
        re.compile(r"(?i)\b(?:I|we) (?:recommend|advise|suggest)\w*\b"),
    ),
    (
        "recommendation",
        re.compile(r"(?i)\b(?:my|our) (?:recommendation|advice)\b"),
    ),
    (
        "recommendation",
        re.compile(
            r"(?i)\b(?:recommend\w*|advis(?:e\w*|able|ory)|advice|suggest\w*)\b"
        ),
    ),
    ("recommendation", re.compile(r"(?i)\bif I were you\b")),
    ("recommendation", re.compile(r"(?i)\b(?:I|we)(?:['’]d| would)\b")),
    ("recommendation", re.compile(r"(?i)\b(?:I|we) (?:prefer|like|favour|favor)\b")),
    ("recommendation", re.compile(r"(?i)\b(?:my|our) preference\b")),
    (
        "ranking",
        re.compile(
            r"(?i)\b(?:best|better|worst|worse|optimal|optimum|ideal|preferred|"
            r"strongest|safest|safer|sensible|prudent|attractive|wise|smart)\b"
        ),
    ),
    (
        "ranking",
        re.compile(
            r"(?i)\b(?:most|least) "
            r"(?:tax[- ]efficient|suitable|advantageous|beneficial|appropriate)\b"
        ),
    ),
    (
        "ranking",
        re.compile(r"(?i)\b(?:right|correct) (?:choice|option|fit)\b"),
    ),
    ("ranking", re.compile(r"(?i)\brank(?:ed|ing)?\b")),
    ("ranking", re.compile(r"(?i)\bwinner\b")),
    (
        "selection",
        re.compile(
            r"(?i)\b(?:choose|choosing|chose|pick|picking|go with|go for|opt for)\b"
        ),
    ),
    ("selection", re.compile(r"(?i)\b(?:consider|worth it|worth considering)\b")),
    (
        "selection",
        re.compile(r"(?i)\bworth (?:taking|choosing|doing|investing|contributing)\b"),
    ),
    (
        "recommendation",
        re.compile(
            r"(?i)\b(?:most|many) people "
            r"(?:in your position|in your situation|like you)\b"
        ),
    ),
    (
        "instruction to the person",
        re.compile(
            r"(?i)(?:^|[.!?]\s+|\n)"
            r"(?:take|pay|put|invest|contribute|withdraw|choose|pick|prefer|go|use|"
            r"avoid|claim|leave)"
            r"\s+(?:the|a|an|your|yourself|it|them|this|that|more|less|£|₦)"
        ),
    ),
)


def recommendation_violations(text: str) -> list[str]:
    """
    Return the phrases in a report that recommend, rank or select an option.

    Args:
        text: The report text, including figure markers and source URLs.

    Returns:
        One message per distinct violation, in the order the phrases appear.
        An empty list means the report describes options without choosing one.
    """
    cleaned = _URL.sub(" ", text)
    cleaned = _MARKER.sub(" ", cleaned)
    cleaned = _DISCLAIMER.sub(" ", cleaned)
    violations: list[str] = []
    seen: list[str] = []
    for label, pattern in _PATTERNS:
        for match in pattern.finditer(cleaned):
            phrase = " ".join(match.group(0).split())
            key = phrase.casefold()
            if any(key in other or other in key for other in seen):
                continue
            seen.append(key)
            violations.append(f"recommendation language ({label}): {phrase!r}")
    return violations
