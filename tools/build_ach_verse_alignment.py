#!/usr/bin/env python3
"""Build the compact verse-coordinate map used by the Acarnesi TEI.

The Greek wording in ``xml/ach.xml`` remains authoritative for LexAr.  This
tool compares only normalised Greek characters with the open Hall--Geldart
TEI distributed by Perseus, then records numeric coordinates and an audit
trail.  It never copies the reference wording into the local transcription.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "xml" / "ach.xml"
DEFAULT_OUTPUT = ROOT / "tools" / "data" / "ach-verse-alignment.json"

TEI_NAMESPACE = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
DUPLICATE_SPEECH_IDS = frozenset({"ach-sp-0163", "ach-sp-0164"})
REFERENCE_URL = (
    "https://github.com/PerseusDL/canonical-greekLit/blob/master/data/"
    "tlg0019/tlg001/tlg0019.tlg001.perseus-grc2.xml"
)
REFERENCE_URN = "urn:cts:greekLit:tlg0019.tlg001.perseus-grc2"


def greek_characters(text: str) -> str:
    """Return an accent-insensitive stream containing Greek letters only."""

    characters = []
    for character in unicodedata.normalize("NFD", text):
        name = unicodedata.name(character, "")
        if "GREEK" not in name or not unicodedata.category(character).startswith("L"):
            continue
        character = character.casefold()
        characters.append("σ" if character in {"ς", "ϲ"} else character)
    return "".join(characters)


def element_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def short_hash(text: str) -> str:
    return hashlib.sha256(
        unicodedata.normalize("NFC", text).encode("utf-8")
    ).hexdigest()[:16]


def source_lines(path: Path) -> list[ET.Element]:
    root = ET.parse(path).getroot()
    lines = []
    for speech in root.findall(".//tei:sp", TEI_NAMESPACE):
        if speech.get(XML_ID) in DUPLICATE_SPEECH_IDS:
            continue
        for line in speech.findall(".//tei:l", TEI_NAMESPACE):
            if (
                (line.get(XML_ID) or "").startswith("ach-gap-")
                or line.find("tei:gap", TEI_NAMESPACE) is not None
            ):
                continue
            lines.append(line)
    return lines


def reference_lines(path: Path) -> list[dict[str, object]]:
    """Read the non-empty reference lines and their exact CTS labels."""

    root = ET.parse(path).getroot()
    rows = []

    for line in root.findall(".//tei:l", TEI_NAMESPACE):
        label = (line.get("n") or "").strip()
        match = re.fullmatch(r"(\d+)[a-z]*", label)
        if not match:
            raise ValueError(f"Coordinata Perseus non riconosciuta: {label!r}")

        base = int(match.group(1))
        if base == 0:
            continue

        normalised = greek_characters(element_text(line))
        if not normalised:
            # Le lacune 1202 e 1206 restano coordinate senza testo locale.
            continue

        rows.append(
            {
                "label": label,
                "base": base,
                "text": normalised,
            }
        )

    return rows


def flatten(rows: list[str]) -> tuple[str, list[int]]:
    text_parts = []
    owners = []
    for index, text in enumerate(rows):
        text_parts.append(text)
        owners.extend([index] * len(text))
    return "".join(text_parts), owners


def build_map(source: Path, reference: Path) -> dict[str, object]:
    local_elements = source_lines(source)
    reference_rows = reference_lines(reference)
    local_texts = [element_text(line) for line in local_elements]
    local_normalised = [greek_characters(text) for text in local_texts]
    reference_normalised = [str(row["text"]) for row in reference_rows]

    local_stream, local_owners = flatten(local_normalised)
    reference_stream, reference_owners = flatten(reference_normalised)
    matcher = difflib.SequenceMatcher(
        None, local_stream, reference_stream, autojunk=False
    )

    matched_reference: list[list[int]] = [[] for _ in local_elements]
    matched_characters = [0 for _ in local_elements]
    for local_start, reference_start, size in matcher.get_matching_blocks():
        for offset in range(size):
            local_index = local_owners[local_start + offset]
            reference_index = reference_owners[reference_start + offset]
            matched_reference[local_index].append(reference_index)
            matched_characters[local_index] += 1

    entries = []
    for index, (text, normalised, matches) in enumerate(
        zip(local_texts, local_normalised, matched_reference, strict=True),
        start=1,
    ):
        if not matches:
            raise ValueError(f"Nessuna corrispondenza per il frammento {index}")

        confidence = matched_characters[index - 1] / max(len(normalised), 1)
        if confidence < 0.5:
            raise ValueError(
                f"Corrispondenza debole per il frammento {index}: "
                f"{confidence:.1%}"
            )

        reference_indexes = sorted(set(matches))
        labels = [
            str(reference_rows[reference_index]["label"])
            for reference_index in reference_indexes
        ]
        verses = sorted(
            {
                int(reference_rows[reference_index]["base"])
                for reference_index in reference_indexes
            }
        )
        entries.append(
            {
                "index": index,
                "refs": labels,
                "verses": verses,
                "corresp": [
                    f"{REFERENCE_URN}:{label}"
                    for label in labels
                ],
                "text_sha256": short_hash(text),
                "confidence": round(confidence, 4),
            }
        )

    groups: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in entries:
        verses = entry["verses"]
        if len(verses) == 1:
            entry["n"] = str(verses[0])
            groups[str(entry["n"])].append(entry)

    for number, group in groups.items():
        for group_index, entry in enumerate(group, start=1):
            if len(group) == 1:
                continue
            if group_index == 1:
                entry["part"] = "I"
            elif group_index == len(group):
                entry["part"] = "F"
            else:
                entry["part"] = "M"

    for entry in entries:
        entry["id"] = f'ach-frag-{int(entry["index"]):04d}'

    if matcher.ratio() < 0.98:
        raise ValueError(
            f"Allineamento globale troppo debole: {matcher.ratio():.2%}"
        )

    return {
        "schema": 1,
        "work": "acarnesi",
        "generated": date.today().isoformat(),
        "method": (
            "Allineamento monotono dei soli caratteri greci normalizzati; "
            "il testo del riferimento non viene importato. @n è assegnato "
            "solo quando tutti i riscontri condividono lo stesso numero-base; "
            "i crossover conservano più URI CTS in @corresp."
        ),
        "source": {
            "path": source.relative_to(ROOT).as_posix(),
            "excluded_duplicate_speeches": sorted(DUPLICATE_SPEECH_IDS),
            "line_count": len(local_elements),
            "greek_sha256": hashlib.sha256(
                local_stream.encode("utf-8")
            ).hexdigest(),
        },
        "reference": {
            "title": "Aristophanis Comoediae, vol. 1",
            "editors": ["F. W. Hall", "W. M. Geldart"],
            "publication": "Oxford, Clarendon Press, 1906",
            "digital_editor": "Perseus Digital Library",
            "url": REFERENCE_URL,
            "license": "https://creativecommons.org/licenses/by-sa/4.0/",
            "file_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
            "non_empty_line_count": len(reference_rows),
            "lacunae": [1202, 1206],
            "greek_sha256": hashlib.sha256(
                reference_stream.encode("utf-8")
            ).hexdigest(),
        },
        "alignment": {
            "character_ratio": round(matcher.ratio(), 6),
            "lines": entries,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Costruisce la mappa delle coordinate per xml/ach.xml."
    )
    parser.add_argument(
        "reference",
        type=Path,
        help="TEI greco Hall–Geldart/Perseus usato come controllo",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_map(args.source.resolve(), args.reference.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    alignment = payload["alignment"]
    print(
        f"Creata {args.output}: "
        f"{len(alignment['lines'])} frammenti, "
        f"corrispondenza {alignment['character_ratio']:.2%}."
    )


if __name__ == "__main__":
    main()
