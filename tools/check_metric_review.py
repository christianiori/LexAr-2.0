#!/usr/bin/env python3
"""Verifica i requisiti per promuovere una scansione metrica a verified."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

try:
    from tools.apply_ach_metrics import load_and_validate
except ModuleNotFoundError:
    from apply_ach_metrics import load_and_validate  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
TEI_PATH = ROOT / "xml" / "ach.xml"
METRICS_PATH = ROOT / "tools" / "data" / "ach-metrics.json"


def expect_rejection(root: ET.Element, payload: dict, expected: str) -> None:
    try:
        load_and_validate(root, payload)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(
                f"Errore inatteso: {error}; atteso un riferimento a {expected!r}"
            ) from error
        return
    raise AssertionError(f"Dato non valido accettato; atteso errore {expected!r}")


def main() -> int:
    root = ET.parse(TEI_PATH).getroot()
    payload = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    missing_review = deepcopy(payload)
    entry = missing_review["lines"][0]
    entry["status"] = "verified"
    entry["cert"] = "high"
    expect_rejection(root, missing_review, "senza revisore")

    medium_certainty = deepcopy(missing_review)
    entry = medium_certainty["lines"][0]
    entry["cert"] = "medium"
    entry["review"] = {
        "reviewer": "Revisore di prova",
        "date": "2026-08-28",
        "source_note": "Dato sintetico usato soltanto dal controllo.",
    }
    expect_rejection(root, medium_certainty, "senza @cert='high'")

    missing_realisation = deepcopy(medium_certainty)
    entry = missing_realisation["lines"][0]
    entry["cert"] = "high"
    entry["fragments"][0].pop("real")
    expect_rejection(root, missing_realisation, "senza realizzazione")

    valid_review = deepcopy(medium_certainty)
    valid_review["lines"][0]["cert"] = "high"
    load_and_validate(root, valid_review)

    print(
        "POLITICA DI REVISIONE SUPERATA: verified richiede revisore, data, "
        "fonte, cert=high e real."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
