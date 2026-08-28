#!/usr/bin/env python3
"""Genera il fallback statico delle schede lessicali interattive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lexicon_source import WORK_LABELS, lexicon_entries


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "script" / "data" / "lexicon-data.js"


def generated_content() -> str:
    payload = {
        slug: {
            "entry_count": len(entries := lexicon_entries(ROOT, slug)),
            "entries": entries,
        }
        for slug in WORK_LABELS
    }
    return (
        "/* File generato da tools/generate_lexicon_data.py. */\n"
        "globalThis.LEXAR_LEXICON_DATA = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verifica che il fallback versionato sia aggiornato.",
    )
    arguments = parser.parse_args()
    expected = generated_content()
    if arguments.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            print(f"Fallback lessicale non aggiornato: {OUTPUT.relative_to(ROOT)}")
            return 1
        print("Fallback lessicale aggiornato.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Generato {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
