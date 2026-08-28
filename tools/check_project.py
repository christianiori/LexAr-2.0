#!/usr/bin/env python3
"""Esegue l'intera suite di controlli locali di LexAr."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
CHECKS = (
    ("Sintassi Python", [PYTHON, "-m", "compileall", "-q", "server.py", "tools"]),
    ("Validazione TEI", [PYTHON, "tools/validate_tei.py"]),
    ("Pilot metrico", [PYTHON, "tools/apply_ach_metrics.py", "--check"]),
    ("Politica revisione metrica", [PYTHON, "tools/check_metric_review.py"]),
    ("Fallback statico", [PYTHON, "tools/generate_work_texts.py", "--check"]),
    ("Backend", [PYTHON, "tools/check_backend.py"]),
    ("Lettore Acarnesi", [PYTHON, "tools/check_reader.py"]),
    ("Link e risorse", [PYTHON, "tools/check_internal_links.py"]),
)


def main() -> int:
    failed: list[str] = []

    for label, command in CHECKS:
        print(f"\n== {label} ==", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            failed.append(label)

    if failed:
        print(
            "\nCONTROLLI NON SUPERATI: " + ", ".join(failed),
            file=sys.stderr,
        )
        return 1

    print("\nTUTTI I CONTROLLI SUPERATI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
