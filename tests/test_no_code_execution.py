"""Guard: application code never executes dynamic code or shell commands.

There is no code-execution tool; the coding worker only writes text. Any
future executor must run in an isolated sandbox (separate container, no
network, non-root, read-only filesystem, CPU/memory/time limits), not in
the API process, so these calls should never appear under app/.
"""

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"

FORBIDDEN = re.compile(
    r"\beval\(|\bexec\(|\bsubprocess\b|\bos\.system\(|\bos\.popen\(|"
    r"\bpickle\.loads?\(|\bmarshal\.loads\("
)


def test_app_code_does_not_execute_dynamic_code():
    offenders = [
        f"{path.relative_to(APP_DIR.parent)}:{number}: {line.strip()}"
        for path in APP_DIR.rglob("*.py")
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if FORBIDDEN.search(line)
    ]

    assert not offenders, "\n".join(offenders)


def test_no_registered_tool_executes_code():
    from app.tools.registry import TOOL_REGISTRY

    for spec in TOOL_REGISTRY:
        description = f"{spec.name} {spec.side_effects}".lower()
        assert "execut" not in description, spec.name
        assert "shell" not in description, spec.name
