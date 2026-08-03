#!/usr/bin/env python3
"""Validate the local LexAr TEI transcription.

The validator deliberately uses only Python's standard library.  With no
argument it checks ``xml/ach.xml``; a different TEI file can be supplied as
the first positional argument.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

try:
    from tools.apply_ach_metrics import (
        METRIC_ATTRIBUTES,
        METRICS_PATH,
        load_and_validate as load_and_validate_metrics,
        metric_attributes,
    )
except ModuleNotFoundError:  # direct execution: python tools/validate_tei.py
    from apply_ach_metrics import (  # type: ignore[no-redef]
        METRIC_ATTRIBUTES,
        METRICS_PATH,
        load_and_validate as load_and_validate_metrics,
        metric_attributes,
    )


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
EXPECTED_DEFAULT_COUNTS = {"l": 1325, "sp": 481, "div": 32}
VERSE_NUMBER_PATTERN = re.compile(r"\d+")
CTS_REFERENCE_PATTERN = re.compile(
    r"urn:cts:greekLit:tlg0019\.tlg001\.perseus-grc2:(\d+)[a-z]*"
)
VERSE_MINIMUM = 1
VERSE_MAXIMUM = 1234
UNATTESTED_REFERENCE_BASES = frozenset(
    {
        209, 212, 213, 214, 218, 223, 224, 227, 228, 229, 233,
        287, 289, 292, 294, 297, 299, 304, 359, 361, 362,
        387, 388, 389, 489, 499, 666, 667, 669, 671, 672,
        693, 694, 699, 701, 972, 974, 989, 1013, 1014,
        1042, 1043, 1152, 1153, 1154, 1163, 1164, 1169,
        1191, 1192,
    }
)
ALLOWED_LINE_PARTS = frozenset({"I", "M", "F"})
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
    is_acharnenses = (root.get(XML_ID) or "").strip() == "acharnenses"

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

    for attribute_name in ("resp", "corresp", "ana", "source"):
        for element in elements:
            if attribute_name not in element.attrib:
                continue

            location = locations[id(element)]
            pointer_value = element.get(attribute_name, "").strip()
            if not pointer_value:
                errors.append(f"{location}: @{attribute_name} vuoto")
                continue

            for pointer in pointer_value.split():
                if attribute_name == "corresp" and (
                    CTS_REFERENCE_PATTERN.fullmatch(pointer)
                    or re.match(r"^[a-z][a-z0-9+.-]*:", pointer, re.IGNORECASE)
                ):
                    continue
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

    previous_reference_base = 0
    covered_verses: set[int] = set()
    line_groups: defaultdict[str, list[tuple[int, ET.Element]]] = defaultdict(list)

    for line_index, line in enumerate(elements_by_name["l"], start=1):
        text = element_text(line)
        latin = {character for character in text if is_latin_character(character)}
        digits = {character for character in text if character.isdigit()}
        raw_integrations = RAW_INTEGRATION_MARKERS.intersection(text)
        location = locations[id(line)]
        if is_acharnenses:
            identifier = (line.get(XML_ID) or "").strip()
            number = (line.get("n") or "").strip()
            part = (line.get("part") or "").strip()
            correspondence = (line.get("corresp") or "").strip()
            reference_bases = [
                int(match.group(1))
                for pointer in correspondence.split()
                if (match := CTS_REFERENCE_PATTERN.fullmatch(pointer))
            ]

            if not identifier:
                errors.append(f"{location}: manca xml:id")
            elif not (
                identifier.startswith("ach-frag-")
                or identifier.startswith("ach-gap-")
            ):
                errors.append(
                    f"{location}: xml:id non appartiene allo spazio "
                    "ach-frag-* / ach-gap-*"
                )

            if not reference_bases:
                errors.append(
                    f"{location}: manca un @corresp CTS Hall–Geldart/Perseus"
                )
            else:
                first_base = min(reference_bases)
                if first_base < previous_reference_base:
                    errors.append(
                        f"{location}: riscontro CTS non monotono "
                        f"({first_base} dopo {previous_reference_base})"
                    )
                previous_reference_base = max(
                    previous_reference_base, max(reference_bases)
                )
                covered_verses.update(reference_bases)

            if number:
                if not VERSE_NUMBER_PATTERN.fullmatch(number):
                    errors.append(
                        f"{location}: @n={number!r} non è un numero-base valido"
                    )
                elif not (VERSE_MINIMUM <= int(number) <= VERSE_MAXIMUM):
                    errors.append(
                        f"{location}: @n={number!r} fuori da "
                        f"{VERSE_MINIMUM}-{VERSE_MAXIMUM}"
                    )
                elif reference_bases and set(reference_bases) != {int(number)}:
                    errors.append(
                        f"{location}: @n={number!r} non coincide con i "
                        f"riscontri CTS {reference_bases!r}"
                    )
                line_groups[number].append((line_index, line))
            elif len(set(reference_bases)) < 2:
                errors.append(
                    f"{location}: @n assente senza un crossover fra "
                    "coordinate-base diverse"
                )

            if part and part not in ALLOWED_LINE_PARTS:
                allowed = ", ".join(sorted(ALLOWED_LINE_PARTS))
                errors.append(
                    f"{location}: @part={part!r} non ammesso "
                    f"(valori ammessi: {allowed})"
                )

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

    for number, group in line_groups.items():
        indexes = [index for index, _ in group]
        parts = [(line.get("part") or "").strip() for _, line in group]
        if len(group) == 1:
            if parts[0]:
                errors.append(
                    f"{locations[id(group[0][1])]}: @part presente su un "
                    f"@n non condiviso ({number})"
                )
            continue

        if indexes != list(range(indexes[0], indexes[-1] + 1)):
            errors.append(
                f"@n={number!r}: i frammenti non sono contigui"
            )
        expected_parts = ["I", *(["M"] * (len(group) - 2)), "F"]
        if parts != expected_parts:
            errors.append(
                f"@n={number!r}: sequenza @part {parts!r}, "
                f"attesa {expected_parts!r}"
            )

    if is_acharnenses:
        if METRICS_PATH.exists():
            metric_payload: dict = {}
            try:
                metric_payload = json.loads(
                    METRICS_PATH.read_text(encoding="utf-8")
                )
                metric_assignments = load_and_validate_metrics(
                    root, metric_payload
                )
            except (OSError, json.JSONDecodeError, ValueError) as error:
                errors.append(f"pilot metrico non valido: {error}")
                metric_assignments = {}

            metric_lines = {
                (line.get(XML_ID) or ""): line
                for line in elements_by_name["l"]
                if any(name in line.attrib for name in METRIC_ATTRIBUTES)
            }
            unexpected_metric_lines = sorted(
                set(metric_lines) - set(metric_assignments)
            )
            if unexpected_metric_lines:
                errors.append(
                    "annotazioni metriche fuori dal pilot: "
                    + ", ".join(unexpected_metric_lines)
                )

            for entry in metric_payload.get("lines", []):
                for fragment in entry.get("fragments", []):
                    target = str(fragment.get("target") or "")
                    line = metric_lines.get(target)
                    if line is None:
                        errors.append(
                            f"{target}: annotazione metrica del sidecar assente"
                        )
                        continue
                    expected_attributes = metric_attributes(entry, fragment)
                    actual_attributes = {
                        name: line.get(name)
                        for name in METRIC_ATTRIBUTES
                        if line.get(name) is not None
                    }
                    if actual_attributes != expected_attributes:
                        errors.append(
                            f"{target}: attributi metrici {actual_attributes!r}, "
                            f"attesi {expected_attributes!r}"
                        )

            met_declarations = [
                element
                for element in elements_by_name["metDecl"]
                if element.get(XML_ID) == "lexar-quantitative-v1"
            ]
            if len(met_declarations) != 1:
                errors.append(
                    "il pilot metrico richiede un solo "
                    "metDecl xml:id='lexar-quantitative-v1'"
                )

        expected_coverage = (
            set(range(VERSE_MINIMUM, VERSE_MAXIMUM + 1))
            - UNATTESTED_REFERENCE_BASES
        )
        missing_verses = sorted(expected_coverage - covered_verses)
        unexpected_verses = sorted(covered_verses - expected_coverage)
        if missing_verses:
            errors.append(
                "coordinate di verso mancanti: "
                + ", ".join(map(str, missing_verses))
            )
        if unexpected_verses:
            errors.append(
                "coordinate-base inattese: "
                + ", ".join(map(str, unexpected_verses))
            )

        gaps = elements_by_name["gap"]
        gap_parents = {
            id(child): parent
            for parent in elements
            for child in parent
        }
        gap_numbers = sorted(
            int(parent.get("n"))
            for gap in gaps
            if (parent := gap_parents.get(id(gap))) is not None
            and (parent.get("n") or "").isdigit()
        )
        if gap_numbers != [1202, 1206]:
            errors.append(
                f"lacune attese ai vv. 1202 e 1206, trovate {gap_numbers!r}"
            )
        for gap in gaps:
            if gap.get("reason") != "lost":
                errors.append(
                    f"{locations[id(gap)]}: @reason deve essere 'lost'"
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
