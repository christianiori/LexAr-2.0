#!/usr/bin/env python3
"""Esegue controlli rapidi sul database e sulle API interne di LexAr."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


EXPECTED_SLUGS = {
    "acarnesi",
    "cavalieri",
    "donne",
    "lisistrata",
    "nuvole",
    "pace",
    "pluto",
    "rane",
    "tesmoforie",
    "uccelli",
    "vespe",
}
EXPECTED_ACHARNIANS_LINES = 1325
EXPECTED_ACHARNIANS_SPEECHES = 481


def main() -> int:
    errors: list[str] = []
    server.initialise_database()

    slugs = set(server.WORKS)
    if slugs != EXPECTED_SLUGS:
        errors.append(
            "catalogo backend inatteso: "
            f"mancanti={sorted(EXPECTED_SLUGS - slugs)!r}, "
            f"extra={sorted(slugs - EXPECTED_SLUGS)!r}"
        )

    for slug, work in server.WORKS.items():
        page = ROOT / str(work["page"])
        if not page.is_file():
            errors.append(f"{slug}: pagina mancante {page.relative_to(ROOT)}")

        for field in ("tei", "metadata"):
            source = work.get(field)
            if source and not Path(source).is_file():
                errors.append(f"{slug}: sorgente {field} mancante: {source}")

        try:
            summary = server.work_summary(slug)
        except KeyError:
            errors.append(f"{slug}: opera assente dal database")
            continue
        if summary.get("page") != work["page"]:
            errors.append(f"{slug}: pagina incoerente nella risposta API")

    try:
        acharnians = server.work_summary("acarnesi")
        speeches = server.speeches_for("acarnesi")
        terms = server.frequent_terms("acarnesi", 30)
    except (KeyError, ValueError) as error:
        errors.append(f"acarnesi: API interna non disponibile: {error}")
    else:
        if acharnians.get("line_count") != EXPECTED_ACHARNIANS_LINES:
            errors.append(
                "acarnesi: conteggio versi/frammenti inatteso "
                f"({acharnians.get('line_count')} != {EXPECTED_ACHARNIANS_LINES})"
            )
        if len(speeches) != EXPECTED_ACHARNIANS_SPEECHES:
            errors.append(
                "acarnesi: conteggio battute inatteso "
                f"({len(speeches)} != {EXPECTED_ACHARNIANS_SPEECHES})"
            )
        if len(terms) != 30:
            errors.append(
                f"acarnesi: attesi 30 termini frequenti, trovati {len(terms)}"
            )

    if errors:
        print("CONTROLLO BACKEND NON SUPERATO", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "CONTROLLO BACKEND SUPERATO: 11 opere, "
        f"{EXPECTED_ACHARNIANS_LINES} versi/frammenti, "
        f"{EXPECTED_ACHARNIANS_SPEECHES} battute."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
