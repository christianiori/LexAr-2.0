"""Genera il fallback statico dei testi a partire dai TEI autorevoli."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "script" / "data" / "work-texts.js"
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def main() -> None:
    server.initialise_database()
    works = {
        slug: {"speeches": server.speeches_for(slug)}
        for slug, work in server.WORKS.items()
        if work.get("tei")
    }
    payload = json.dumps(works, ensure_ascii=False, separators=(",", ":"))
    content = (
        "/* Generato dai TEI con tools/generate_work_texts.py. */\n"
        f"globalThis.LEXAR_WORK_DATA = {payload};\n"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(content)

    print(f"Creato {OUTPUT.relative_to(ROOT)} ({len(works)} opere).")


if __name__ == "__main__":
    main()
