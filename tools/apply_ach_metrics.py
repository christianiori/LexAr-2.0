#!/usr/bin/env python3
"""Apply the audited metrical pilot to ``xml/ach.xml``.

The versioned sidecar is the review surface.  This script verifies every
target against a structural hash, adds the project-level TEI declarations and
copies only the approved attributes onto the corresponding ``l`` elements.
It never changes the Greek wording and is safe to run more than once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEI_PATH = ROOT / "xml" / "ach.xml"
METRICS_PATH = ROOT / "tools" / "data" / "ach-metrics.json"

TEI_NAMESPACE = "http://www.tei-c.org/ns/1.0"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
XML_ID = f"{{{XML_NAMESPACE}}}id"
METRIC_ATTRIBUTES = frozenset(
    {"ana", "met", "real", "resp", "cert", "source"}
)
METRIC_PATTERN = re.compile(r"^[-ux|]+$")


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def normalise_text(value: str | None) -> str:
    return unicodedata.normalize("NFC", value or "")


def structural_payload(element: ET.Element, *, root: bool = True) -> dict:
    """Return content/markup data independent of line-level annotations."""

    payload: dict[str, object] = {
        "tag": local_name(element.tag),
        "text": normalise_text(element.text),
        "children": [],
    }
    if not root:
        payload["attributes"] = sorted(
            (local_name(name), normalise_text(value))
            for name, value in element.attrib.items()
        )

    children = payload["children"]
    assert isinstance(children, list)
    for child in element:
        children.append(
            {
                "node": structural_payload(child, root=False),
                "tail": normalise_text(child.tail),
            }
        )
    return payload


def structural_hash(element: ET.Element) -> str:
    serialised = json.dumps(
        structural_payload(element),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def metric_attributes(entry: dict, fragment: dict) -> dict[str, str]:
    pointers = [f"#met-{entry['meter_id']}", f"#metric-{entry['status']}"]
    attributes = {
        "ana": " ".join(pointers),
        "met": str(entry["met"]),
        "resp": str(entry["resp"]),
        "cert": str(entry["cert"]),
        "source": " ".join(str(value) for value in entry["sources"]),
    }
    real = str(fragment.get("real") or "")
    if real:
        attributes["real"] = real
    return attributes


def load_and_validate(
    tei_root: ET.Element, payload: dict
) -> dict[str, dict[str, str]]:
    if payload.get("schema") != 1 or payload.get("work") != "acarnesi":
        raise ValueError("Sidecar metrico non riconosciuto")
    scope = payload.get("scope") or {}
    if scope != {"from": 1, "to": 46}:
        raise ValueError(f"Ambito metrico inatteso: {scope!r}")

    lines = payload.get("lines")
    if not isinstance(lines, list) or len(lines) != 46:
        raise ValueError("Il pilot deve contenere esattamente i vv. 1-46")
    labels = [str(entry.get("label")) for entry in lines]
    expected = [str(number) for number in range(1, 47)]
    if labels != expected:
        raise ValueError("Le etichette del pilot non coprono in ordine i vv. 1-46")

    elements = {
        element.get(XML_ID): element
        for element in tei_root.findall(f".//{{{TEI_NAMESPACE}}}l")
        if element.get(XML_ID)
    }
    assignments: dict[str, dict[str, str]] = {}
    for entry in lines:
        label = str(entry["label"])
        meter_id = str(entry.get("meter_id") or "")
        status = str(entry.get("status") or "")
        cert = str(entry.get("cert") or "")
        met = str(entry.get("met") or "")
        if meter_id not in {"ia3", "ia1-hypercat"}:
            raise ValueError(f"v. {label}: metro non ammesso {meter_id!r}")
        if status not in {"proposed", "verified", "unscannable"}:
            raise ValueError(f"v. {label}: stato non ammesso {status!r}")
        if cert not in {"low", "medium", "high", "unknown"}:
            raise ValueError(f"v. {label}: @cert non ammesso {cert!r}")
        if not METRIC_PATTERN.fullmatch(met):
            raise ValueError(f"v. {label}: schema metrico non valido {met!r}")
        if status == "verified":
            review = entry.get("review")
            required_review_fields = {"reviewer", "date", "source_note"}
            if not isinstance(review, dict) or any(
                not str(review.get(field) or "").strip()
                for field in required_review_fields
            ):
                raise ValueError(
                    f"v. {label}: scansione verificata senza revisore, data "
                    "e nota sulla fonte"
                )
            if cert != "high":
                raise ValueError(
                    f"v. {label}: scansione verificata senza @cert='high'"
                )

        fragments = entry.get("fragments")
        if not isinstance(fragments, list) or not fragments:
            raise ValueError(f"v. {label}: nessun frammento")
        parts: list[str] = []
        for fragment in fragments:
            target = str(fragment.get("target") or "")
            if target in assignments:
                raise ValueError(f"Target metrico duplicato: {target}")
            element = elements.get(target)
            if element is None:
                raise ValueError(f"Target metrico non risolto: {target}")
            if element.get("n") != label:
                raise ValueError(
                    f"{target}: @n={element.get('n')!r}, atteso {label!r}"
                )
            actual_hash = structural_hash(element)
            expected_hash = str(fragment.get("structural_sha256") or "")
            if actual_hash != expected_hash:
                raise ValueError(
                    f"{target}: firma strutturale cambiata "
                    f"({actual_hash} != {expected_hash})"
                )
            real = str(fragment.get("real") or "")
            if real and not METRIC_PATTERN.fullmatch(real):
                raise ValueError(f"{target}: realizzazione non valida {real!r}")
            if status == "verified" and not real:
                raise ValueError(
                    f"{target}: scansione verificata senza realizzazione"
                )
            if (
                status != "unscannable"
                and not real
                and not (
                    status == "proposed"
                    and cert == "low"
                    and str(entry.get("note") or "").strip()
                )
            ):
                raise ValueError(
                    f"{target}: manca la realizzazione metrica senza una "
                    "nota esplicita e @cert='low'"
                )
            parts.append(str(element.get("part") or ""))
            assignments[target] = metric_attributes(entry, fragment)

        expected_parts = (
            [""]
            if len(fragments) == 1
            else ["I", *(["M"] * (len(fragments) - 2)), "F"]
        )
        if parts != expected_parts:
            raise ValueError(
                f"v. {label}: sequenza dei frammenti {parts!r}, "
                f"attesa {expected_parts!r}"
            )

    expected_targets = {f"ach-frag-{number:04d}" for number in range(1, 52)}
    if set(assignments) != expected_targets:
        missing = sorted(expected_targets - set(assignments))
        extra = sorted(set(assignments) - expected_targets)
        raise ValueError(
            f"Copertura target errata; mancanti={missing!r}, extra={extra!r}"
        )
    return assignments


def add_header(xml: str) -> str:
    if 'xml:id="metric-pilot"' not in xml:
        marker = "\t\t\t</titleStmt>"
        block = """\t\t\t\t<respStmt xml:id="metric-pilot">
\t\t\t\t\t<resp>Proposta di scansione metrica assistita da calcolo e soggetta a revisione filologica</resp>
\t\t\t\t\t<name ref="#christian-iori">Christian Iori</name>
\t\t\t\t</respStmt>
"""
        if marker not in xml:
            raise ValueError("Chiusura <titleStmt> non trovata")
        xml = xml.replace(marker, block + marker, 1)

    if 'xml:id="source-starkie-1909"' not in xml:
        marker = "\t\t\t</sourceDesc>"
        block = """\t\t\t\t<biblStruct xml:id="source-starkie-1909" type="metrical-reference">
\t\t\t\t\t<monogr>
\t\t\t\t\t\t<author>Aristophanes</author>
\t\t\t\t\t\t<title level="m">The Acharnians of Aristophanes</title>
\t\t\t\t\t\t<editor>W. J. M. Starkie</editor>
\t\t\t\t\t\t<imprint>
\t\t\t\t\t\t\t<pubPlace>London</pubPlace>
\t\t\t\t\t\t\t<publisher>Macmillan</publisher>
\t\t\t\t\t\t\t<date when="1909">1909</date>
\t\t\t\t\t\t</imprint>
\t\t\t\t\t</monogr>
\t\t\t\t\t<ref target="https://upload.wikimedia.org/wikipedia/commons/6/63/The_Acharnians_of_Aristophanes_%28IA_achar00niansofarisarisrich%29.pdf">Scansione pubblica dell'edizione.</ref>
\t\t\t\t</biblStruct>
\t\t\t\t<bibl xml:id="source-diorisis-scan" type="software">
\t\t\t\t\t<title>Diorisis Scan</title>
\t\t\t\t\t<ref target="https://github.com/alevatri/diorisisscan">Versione beta 0.2, impiegata per generare proposte non autoritative.</ref>
\t\t\t\t</bibl>
"""
        if marker not in xml:
            raise ValueError("Chiusura <sourceDesc> non trovata")
        xml = xml.replace(marker, block + marker, 1)

    if 'xml:id="lexar-quantitative-v1"' not in xml:
        marker = "\t\t\t<editorialDecl>"
        block = """\t\t\t<metDecl xml:id="lexar-quantitative-v1">
\t\t\t\t<p xml:lang="it">
\t\t\t\t\tNegli attributi met e real il segno - indica una sillaba lunga,
\t\t\t\t\tu una breve, x un elemento anceps, | un confine di piede e ||
\t\t\t\t\tuna cesura editoriale. Nei versi distribuiti fra più battute,
\t\t\t\t\treal descrive soltanto il frammento corrente e la scansione
\t\t\t\t\tcompleta si ricostruisce seguendo la sequenza I, M, F.
\t\t\t\t</p>
\t\t\t</metDecl>
\t\t\t<classDecl>
\t\t\t\t<taxonomy xml:id="lexar-metrical-taxonomy">
\t\t\t\t\t<category xml:id="met-ia3"><catDesc>Trimetro giambico acataletto</catDesc></category>
\t\t\t\t\t<category xml:id="met-ia1-hypercat"><catDesc>Monometro giambico ipercatalettico, interpretazione dubbia</catDesc></category>
\t\t\t\t\t<category xml:id="metric-proposed"><catDesc>Scansione proposta, non ancora verificata</catDesc></category>
\t\t\t\t\t<category xml:id="metric-verified"><catDesc>Scansione verificata</catDesc></category>
\t\t\t\t\t<category xml:id="metric-unscannable"><catDesc>Scansione non ricostruibile dal testo disponibile</catDesc></category>
\t\t\t\t</taxonomy>
\t\t\t</classDecl>
\t\t\t<appInfo>
\t\t\t\t<application xml:id="software-diorisis-scan" ident="diorisis-scan" version="0.2">
\t\t\t\t\t<label>Diorisis Scan</label>
\t\t\t\t\t<ptr target="https://github.com/alevatri/diorisisscan"/>
\t\t\t\t\t<desc xml:lang="it">Generazione assistita delle proposte metriche; l'output non equivale a una verifica filologica.</desc>
\t\t\t\t</application>
\t\t\t</appInfo>
"""
        if marker not in xml:
            raise ValueError("<editorialDecl> non trovato")
        xml = xml.replace(marker, block + marker, 1)

    if "Avvio del pilot metrico sui vv. 1-46" not in xml:
        marker = "\t\t<revisionDesc>\n"
        change = """\t\t\t<change when="2026-08-03" resp="#metric-pilot">
\t\t\t\tAvvio del pilot metrico sui vv. 1-46: proposte di scansione
\t\t\t\tquantitativa, provenienza e grado di certezza espliciti.
\t\t\t</change>
"""
        if marker not in xml:
            raise ValueError("<revisionDesc> non trovato")
        xml = xml.replace(marker, marker + change, 1)
    return xml


def apply_attributes(xml: str, assignments: dict[str, dict[str, str]]) -> str:
    pattern = re.compile(r'<l\b(?P<attrs>[^>]*)\bxml:id="(?P<id>[^"]+)"(?P<tail>[^>]*)>')
    seen: set[str] = set()

    def replacement(match: re.Match[str]) -> str:
        target = match.group("id")
        if target not in assignments:
            return match.group(0)
        seen.add(target)
        opening = match.group(0)[:-1]
        for name in METRIC_ATTRIBUTES:
            opening = re.sub(rf'\s+{name}="[^"]*"', "", opening)
        for name, value in assignments[target].items():
            opening += f' {name}="{value}"'
        return opening + ">"

    xml = pattern.sub(replacement, xml)
    missing = sorted(set(assignments) - seen)
    if missing:
        raise ValueError(f"Elementi <l> non aggiornati: {missing!r}")
    return xml


def verify_applied(root: ET.Element, assignments: dict[str, dict[str, str]]) -> None:
    elements = {
        element.get(XML_ID): element
        for element in root.findall(f".//{{{TEI_NAMESPACE}}}l")
        if element.get(XML_ID)
    }
    for target, expected in assignments.items():
        element = elements[target]
        actual = {
            name: element.get(name)
            for name in METRIC_ATTRIBUTES
            if element.get(name) is not None
        }
        if actual != expected:
            raise ValueError(f"{target}: attributi metrici {actual!r}, attesi {expected!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verifica sidecar e annotazioni senza modificare il TEI",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    source_bytes = TEI_PATH.read_bytes()
    line_ending = "\r\n" if b"\r\n" in source_bytes else "\n"
    xml = source_bytes.decode("utf-8").replace("\r\n", "\n")
    root = ET.fromstring(xml)
    assignments = load_and_validate(root, payload)

    if args.check:
        verify_applied(root, assignments)
        print(f"Pilot metrico verificato: {len(assignments)} frammenti.")
        return

    xml = add_header(xml)
    xml = apply_attributes(xml, assignments)
    xml = xml.rstrip("\n") + "\n"
    result = ET.fromstring(xml)
    verify_applied(result, assignments)
    TEI_PATH.write_bytes(xml.replace("\n", line_ending).encode("utf-8"))
    print(f"Applicato il pilot metrico a {len(assignments)} frammenti in {TEI_PATH}.")


if __name__ == "__main__":
    main()
