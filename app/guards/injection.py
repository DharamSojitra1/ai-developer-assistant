"""Heuristic prompt-injection screening.

Flag-only: matches are logged so attacks can be noticed, but requests are
never rejected (regexes have false positives, and the hardened system
prompts are the actual defence). Logs carry pattern names, never the text.
"""

import re

from app.utils.agent_logger import logger

INJECTION_PATTERNS: dict[str, re.Pattern] = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in {
        "override_instructions": (
            r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}"
            r"\b(previous|prior|above|earlier|all|your|system)\b[^.\n]{0,20}"
            r"\b(instructions?|prompts?|rules?|directives?|guidelines?)\b"
        ),
        "reveal_system_prompt": (
            r"\b(reveal|show|print|repeat|output|leak|display|tell me)\b"
            r"[^.\n]{0,40}\b(system prompt|hidden prompt|initial prompt|"
            r"your (instructions|rules|prompt))\b"
        ),
        "role_reassignment": (
            r"\byou are now\b|\bact as (dan|an? unrestricted)\b|"
            r"\b(developer|god|jailbreak) mode\b|\bdo anything now\b"
        ),
        "fake_role_marker": (
            r"(^|\n)\s*(system|assistant)\s*:|<\|im_start\|>|<\|system\|>|"
            r"\[/?(INST|SYS)\]"
        ),
        "exfiltration": (
            r"\b(send|post|upload|forward|exfiltrate)\b[^.\n]{0,60}"
            r"\bhttps?://"
        ),
    }.items()
}


def detect_injection(text: str) -> list[str]:
    """Names of the injection patterns `text` matches, in a stable order."""
    if not text:
        return []

    return [
        name
        for name, pattern in INJECTION_PATTERNS.items()
        if pattern.search(text)
    ]


def screen_input(text: str, source: str, **context) -> list[str]:
    """Detect and log; returns the matched pattern names."""
    flags = detect_injection(text)

    if flags:
        logger.warning(
            "Possible prompt injection",
            extra={
                "injection_source": source,
                "injection_flags": flags,
                **context,
            },
        )

    return flags
