"""Genera il fallback statico dei testi a partire dai TEI autorevoli."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "script" / "data" / "work-texts.js"
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def generated_content() -> tuple[str, int]:
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
    return content, len(works)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verifica il fallback senza riscriverlo",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    content, work_count = generated_content()

    if args.check:
        try:
            current = OUTPUT.read_text(encoding="utf-8")
        except OSError as error:
            print(f"Fallback statico non leggibile: {error}", file=sys.stderr)
            return 1
        if current != content:
            print(
                "Fallback statico non aggiornato: esegui "
                "python tools/generate_work_texts.py",
                file=sys.stderr,
            )
            return 1
        noun = "opera" if work_count == 1 else "opere"
        print(f"Fallback statico verificato: {work_count} {noun} con testo TEI.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(content)

    print(f"Creato {OUTPUT.relative_to(ROOT)} ({work_count} opere).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
