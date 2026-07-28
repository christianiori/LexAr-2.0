#!/usr/bin/env python3
"""Validate the local LexAr TEI transcription.

The validator deliberately uses only Python's standard library.  With no
argument it checks ``xml/ach.xml``; a different TEI file can be supplied as
the first positional argument.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
XML_ID = f"{{{XML_NAMESPACE}}}id"
XML_LANG = f"{{{XML_NAMESPACE}}}lang"

ALLOWED_SPEAKER_TARGETS = frozenset({"role", "person", "personGrp"})
ALLOWED_DIV_TYPES = frozenset({"section", "subsection"})
ALLOWED_DIV_SUBTYPES = frozenset(
    {"scene", "choral", "strophe", "antistrophe", "unclassified"}
)
ALLOWED_DIV_COMBINATIONS = {
    "section": frozenset({"scene", "choral"}),
    "subsection": frozenset({"strophe", "antistrophe", "unclassified"}),
}
REQUIRED_HEADER_SECTIONS = ("fileDesc", "encodingDesc", "profileDesc", "revisionDesc")
EXPECTED_DEFAULT_COUNTS = {"l": 1329, "sp": 483, "div": 32}
RAW_INTEGRATION_MARKERS = frozenset({"\u2039", "\u203a"})
RAW_EDITORIAL_MARKERS = RAW_INTEGRATION_MARKERS | frozenset({"[", "]"})

DEFAULT_TEI = Path(__file__).resolve().parents[1] / "xml" / "ach.xml"


def local_name(name: str) -> str:
    """Return the local part of an expanded XML name."""

    return name.rsplit("}", 1)[-1]


def element_text(element: ET.Element) -> str:
    """Return all textual content below an element."""

    return "".join(element.itertext())


def format_characters(characters: set[str]) -> str:
    """Format offending characters with code points for useful diagnostics."""

    return ", ".join(
        f"{character!r} (U+{ord(character):04X})"
        for character in sorted(characters, key=ord)
    )


def is_latin_character(character: str) -> bool:
    """Recognise Latin letters, including accented and extended forms."""

    return unicodedata.category(character).startswith("L") and unicodedata.name(
        character, ""
    ).startswith("LATIN")


def build_locations(
    root: ET.Element,
) -> tuple[list[ET.Element], dict[int, str]]:
    """Give each element a stable, human-readable location."""

    elements = list(root.iter())
    counters: defaultdict[str, int] = defaultdict(int)
    locations: dict[int, str] = {}

    for element in elements:
        name = local_name(element.tag)
        counters[name] += 1
        identifier = (element.get(XML_ID) or "").strip()
        suffix = f" xml:id={identifier!r}" if identifier else ""
        locations[id(element)] = f"{name}[{counters[name]}]{suffix}"

    return elements, locations


def validate(path: Path) -> tuple[list[str], int, int]:
    """Return validation errors and the ``l``/``sp`` counts."""

    try:
        tree = ET.parse(path)
    except ET.ParseError as error:
        return [f"XML non ben formato: {error}"], 0, 0
    except OSError as error:
        return [f"Impossibile leggere {path}: {error}"], 0, 0

    root = tree.getroot()
    elements, locations = build_locations(root)
    errors: list[str] = []

    elements_by_name: defaultdict[str, list[ET.Element]] = defaultdict(list)
    id_targets: defaultdict[str, list[ET.Element]] = defaultdict(list)

    for element in elements:
        elements_by_name[local_name(element.tag)].append(element)
        if XML_ID in element.attrib:
            identifier = element.get(XML_ID, "").strip()
            if not identifier:
                errors.append(f"{locations[id(element)]}: xml:id vuoto")
            else:
                id_targets[identifier].append(element)

    for identifier, targets in sorted(id_targets.items()):
        if len(targets) > 1:
            occurrences = ", ".join(locations[id(target)] for target in targets)
            errors.append(
                f"xml:id duplicato {identifier!r}: {occurrences}"
            )

    if local_name(root.tag) != "TEI":
        errors.append(
            f"radice non valida: trovato <{local_name(root.tag)}>, atteso <TEI>"
        )

    headers = elements_by_name["teiHeader"]
    if len(headers) != 1:
        errors.append(
            f"atteso un solo <teiHeader>, trovati {len(headers)}"
        )
    for section_name in REQUIRED_HEADER_SECTIONS:
        section_count = len(elements_by_name[section_name])
        if section_count != 1:
            errors.append(
                f"atteso un solo <{section_name}>, trovati {section_count}"
            )

    bodies = elements_by_name["body"]
    if len(bodies) != 1:
        errors.append(f"atteso un solo <body>, trovati {len(bodies)}")
    elif (bodies[0].get(XML_LANG) or "").strip() != "grc":
        errors.append("<body>: manca xml:lang='grc'")

    for speech in elements_by_name["sp"]:
        location = locations[id(speech)]
        if not (speech.get(XML_ID) or "").strip():
            errors.append(f"{location}: manca xml:id")

        who = (speech.get("who") or "").strip()
        if not who:
            errors.append(f"{location}: manca @who")
        else:
            for pointer in who.split():
                if not pointer.startswith("#") or len(pointer) == 1:
                    errors.append(
                        f"{location}: @who contiene il puntatore locale "
                        f"non valido {pointer!r} (atteso #id)"
                    )
                    continue

                target_id = pointer[1:]
                targets = id_targets.get(target_id, [])
                if not targets:
                    errors.append(
                        f"{location}: @who {pointer!r} non è risolto"
                    )
                elif len(targets) > 1:
                    errors.append(
                        f"{location}: @who {pointer!r} è ambiguo perché "
                        "l'xml:id è duplicato"
                    )
                else:
                    target_name = local_name(targets[0].tag)
                    if target_name not in ALLOWED_SPEAKER_TARGETS:
                        allowed = ", ".join(sorted(ALLOWED_SPEAKER_TARGETS))
                        errors.append(
                            f"{location}: @who {pointer!r} punta a "
                            f"<{target_name}>, non a uno tra {allowed}"
                        )

        speakers = [
            child
            for child in speech
            if local_name(child.tag) == "speaker"
        ]
        if not speakers:
            errors.append(f"{location}: manca l'elemento <speaker>")
        elif not any(element_text(speaker).strip() for speaker in speakers):
            errors.append(f"{location}: l'elemento <speaker> è vuoto")
        for speaker in speakers:
            if (speaker.get(XML_LANG) or "").strip() != "it":
                errors.append(
                    f"{locations[id(speaker)]}: manca xml:lang='it'"
                )

        lines = [
            descendant
            for descendant in speech.iter()
            if local_name(descendant.tag) == "l"
        ]
        if not lines:
            errors.append(f"{location}: non contiene alcun elemento <l>")

    for division in elements_by_name["div"]:
        location = locations[id(division)]
        if not (division.get(XML_ID) or "").strip():
            errors.append(f"{location}: manca xml:id")

        division_type = (division.get("type") or "").strip()
        if division_type not in ALLOWED_DIV_TYPES:
            allowed = ", ".join(sorted(ALLOWED_DIV_TYPES))
            errors.append(
                f"{location}: @type={division_type!r} non ammesso "
                f"(valori ammessi: {allowed})"
            )

        division_subtype = (division.get("subtype") or "").strip()
        if division_subtype not in ALLOWED_DIV_SUBTYPES:
            allowed = ", ".join(sorted(ALLOWED_DIV_SUBTYPES))
            errors.append(
                f"{location}: @subtype={division_subtype!r} non ammesso "
                f"(valori ammessi: {allowed})"
            )
        elif (
            division_type in ALLOWED_DIV_COMBINATIONS
            and division_subtype not in ALLOWED_DIV_COMBINATIONS[division_type]
        ):
            allowed = ", ".join(
                sorted(ALLOWED_DIV_COMBINATIONS[division_type])
            )
            errors.append(
                f"{location}: @subtype={division_subtype!r} non è compatibile "
                f"con @type={division_type!r} (valori ammessi: {allowed})"
            )

    for attribute_name in ("resp", "corresp"):
        for element in elements:
            if attribute_name not in element.attrib:
                continue

            location = locations[id(element)]
            pointer_value = element.get(attribute_name, "").strip()
            if not pointer_value:
                errors.append(f"{location}: @{attribute_name} vuoto")
                continue

            for pointer in pointer_value.split():
                if not pointer.startswith("#") or len(pointer) == 1:
                    errors.append(
                        f"{location}: @{attribute_name} contiene il puntatore "
                        f"locale non valido {pointer!r} (atteso #id)"
                    )
                    continue

                target_id = pointer[1:]
                targets = id_targets.get(target_id, [])
                if not targets:
                    errors.append(
                        f"{location}: @{attribute_name} {pointer!r} non è risolto"
                    )
                elif len(targets) > 1:
                    errors.append(
                        f"{location}: @{attribute_name} {pointer!r} è ambiguo "
                        "perché l'xml:id è duplicato"
                    )

    for line in elements_by_name["l"]:
        text = element_text(line)
        latin = {character for character in text if is_latin_character(character)}
        digits = {character for character in text if character.isdigit()}
        raw_integrations = RAW_INTEGRATION_MARKERS.intersection(text)
        location = locations[id(line)]

        if latin:
            errors.append(
                f"{location}: caratteri latini nella linea greca: "
                f"{format_characters(latin)}"
            )
        if digits:
            errors.append(
                f"{location}: cifre nella linea greca: "
                f"{format_characters(digits)}"
            )
        if raw_integrations:
            errors.append(
                f"{location}: marcatori di integrazione raw: "
                f"{format_characters(set(raw_integrations))}"
            )

    for element_name in ("add", "del"):
        for editorial_element in elements_by_name[element_name]:
            text = element_text(editorial_element)
            raw_markers = RAW_EDITORIAL_MARKERS.intersection(text)
            if raw_markers:
                errors.append(
                    f"{locations[id(editorial_element)]}: marcatori editoriali "
                    f"raw dentro <{element_name}>: "
                    f"{format_characters(set(raw_markers))}"
                )

    if path.resolve() == DEFAULT_TEI.resolve():
        for element_name, expected_count in EXPECTED_DEFAULT_COUNTS.items():
            actual_count = len(elements_by_name[element_name])
            if actual_count != expected_count:
                errors.append(
                    f"conteggio <{element_name}> inatteso: "
                    f"{actual_count}, atteso {expected_count}"
                )

    return errors, len(elements_by_name["l"]), len(elements_by_name["sp"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida struttura e contenuto del TEI locale di LexAr."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_TEI,
        help=f"file TEI da validare (default: {DEFAULT_TEI})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = args.path.resolve()
    errors, line_count, speech_count = validate(path)

    print(f"{path}: {line_count} <l>, {speech_count} <sp>")
    if errors:
        print(f"VALIDAZIONE FALLITA: {len(errors)} errore/i", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("VALIDAZIONE SUPERATA: nessun errore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
