#!/usr/bin/env python3
"""Apply the audited verse-coordinate map to ``xml/ach.xml``.

The operation is idempotent.  It removes two mechanically repeated speeches,
verifies every surviving line against the map, then assigns stable ``xml:id``,
``n`` and (where necessary) ``part`` attributes without changing the Greek
wording.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEI_PATH = ROOT / "xml" / "ach.xml"
MAP_PATH = ROOT / "tools" / "data" / "ach-verse-alignment.json"

TEI_NAMESPACE = "http://www.tei-c.org/ns/1.0"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
XML_ID = f"{{{XML_NAMESPACE}}}id"
DUPLICATE_SPEECH_IDS = ("ach-sp-0163", "ach-sp-0164")
REFERENCE_URN = "urn:cts:greekLit:tlg0019.tlg001.perseus-grc2"


def element_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def short_hash(text: str) -> str:
    return hashlib.sha256(
        unicodedata.normalize("NFC", text).encode("utf-8")
    ).hexdigest()[:16]


def remove_duplicate_speeches(xml: str) -> tuple[str, list[str]]:
    removed = []
    for speech_id in DUPLICATE_SPEECH_IDS:
        pattern = re.compile(
            rf"\n[ \t]*<sp xml:id=\"{re.escape(speech_id)}\"[^>]*>"
            r".*?</sp>",
            re.DOTALL,
        )
        xml, count = pattern.subn("", xml, count=1)
        if count:
            removed.append(speech_id)
    return xml, removed


def surviving_lines(xml: str) -> list[ET.Element]:
    root = ET.fromstring(xml)
    return root.findall(f".//{{{TEI_NAMESPACE}}}l")


def remove_managed_gaps(xml: str) -> str:
    """Remove generated lacuna rows before an idempotent re-application."""

    return re.sub(
        r'\n[ \t]*<l xml:id="ach-gap-(?:1202|1206)"[^>]*>'
        r'\s*<gap reason="lost"\s*/>\s*</l>',
        "",
        xml,
    )


def add_header_documentation(xml: str) -> str:
    if 'xml:id="alignment-perseus-hg-1906"' not in xml:
        marker = "\t\t\t</sourceDesc>"
        reference = """\t\t\t\t<biblStruct xml:id="alignment-perseus-hg-1906" type="alignment">
\t\t\t\t\t<monogr>
\t\t\t\t\t\t<author>Aristophanes</author>
\t\t\t\t\t\t<title level="m">Aristophanis Comoediae</title>
\t\t\t\t\t\t<editor>F. W. Hall</editor>
\t\t\t\t\t\t<editor>W. M. Geldart</editor>
\t\t\t\t\t\t<imprint>
\t\t\t\t\t\t\t<pubPlace>Oxford</pubPlace>
\t\t\t\t\t\t\t<publisher>Clarendon Press</publisher>
\t\t\t\t\t\t\t<date when="1906">1906</date>
\t\t\t\t\t\t</imprint>
\t\t\t\t\t\t<biblScope unit="volume">1</biblScope>
\t\t\t\t\t</monogr>
\t\t\t\t\t<ref target="https://github.com/PerseusDL/canonical-greekLit/blob/master/data/tlg0019/tlg001/tlg0019.tlg001.perseus-grc2.xml">
\t\t\t\t\t\tCodifica TEI Perseus usata esclusivamente per il riscontro
\t\t\t\t\t\tdelle coordinate numeriche (CC BY-SA 4.0).
\t\t\t\t\t</ref>
\t\t\t\t</biblStruct>
"""
        if marker not in xml:
            raise ValueError("Chiusura <sourceDesc> non trovata")
        xml = xml.replace(marker, reference + marker, 1)
    else:
        xml = xml.replace(
            "delle coordinate numeriche.\n\t\t\t\t\t</ref>",
            "delle coordinate numeriche (CC BY-SA 4.0).\n\t\t\t\t\t</ref>",
            1,
        )

    new_refs = """\t\t\t<refsDecl>
\t\t\t\t<p xml:lang="it">
\t\t\t\t\tDivisioni, battute e frammenti di verso possiedono identificatori
\t\t\t\t\tXML stabili. L'attributo n registra un numero-base soltanto
\t\t\t\t\tquando il riscontro Hall–Geldart/Perseus è univoco; corresp
\t\t\t\t\tconserva le etichette CTS esatte, comprese quelle suffissate e
\t\t\t\t\ti crossover fra due coordinate. La lezione greca e le attribuzioni
\t\t\t\t\tdei parlanti restano quelle di LexAr, fondate sull'edizione Coulon.
\t\t\t\t\tQueste coordinate non sostituiscono una collazione integrale della
\t\t\t\t\tlineazione Coulon.
\t\t\t\t</p>
\t\t\t</refsDecl>"""
    xml, refs_count = re.subn(
        r"\t\t\t<refsDecl>.*?\t\t\t</refsDecl>",
        new_refs,
        xml,
        count=1,
        flags=re.DOTALL,
    )
    if refs_count != 1:
        raise ValueError("<refsDecl> non riconosciuto")

    change = """\t\t\t<change when="2026-07-28">
\t\t\t\tRimozione di due ripetizioni meccaniche e assegnazione di
\t\t\t\tidentificatori stabili e coordinate numeriche ai frammenti di verso.
\t\t\t</change>
"""
    if "Rimozione di due ripetizioni meccaniche" not in xml:
        marker = "\t\t<revisionDesc>\n"
        if marker not in xml:
            raise ValueError("<revisionDesc> non riconosciuto")
        xml = xml.replace(marker, marker + change, 1)

    return xml


def serialise_attribute_name(name: str) -> str:
    """Return an ElementTree attribute name in source-friendly form."""

    if name == XML_ID:
        return "xml:id"
    if name.startswith("{"):
        namespace, local = name[1:].split("}", 1)
        if namespace == XML_NAMESPACE:
            return f"xml:{local}"
        raise ValueError(f"Namespace attributo non gestito: {name!r}")
    return name


def line_opening(entry: dict[str, object], current: ET.Element) -> str:
    """Build a line start tag while preserving non-coordinate attributes.

    The coordinate workflow owns only ``xml:id``, ``n``, ``part`` and
    ``corresp``.  Metrical and future project attributes must survive an
    idempotent re-run of this script.
    """

    attributes = [f'xml:id="{entry["id"]}"']
    if entry.get("n"):
        attributes.append(f'n="{entry["n"]}"')
    if entry.get("part"):
        attributes.append(f'part="{entry["part"]}"')
    corresp = " ".join(str(value) for value in entry["corresp"])
    attributes.append(f'corresp="{corresp}"')

    managed = {XML_ID, "n", "part", "corresp"}
    for name, value in current.attrib.items():
        if name in managed:
            continue
        attributes.append(f'{serialise_attribute_name(name)}="{value}"')
    return "<l " + " ".join(attributes) + ">"


def apply_map(xml: str, entries: list[dict[str, object]]) -> str:
    lines = surviving_lines(xml)
    if len(lines) != len(entries):
        raise ValueError(
            f"La mappa contiene {len(entries)} frammenti, "
            f"il TEI ne contiene {len(lines)}"
        )

    for index, (line, entry) in enumerate(zip(lines, entries, strict=True), start=1):
        if entry.get("index") != index:
            raise ValueError(f"Indice non coerente nella mappa: {entry!r}")
        actual_hash = short_hash(element_text(line))
        if actual_hash != entry.get("text_sha256"):
            raise ValueError(
                f"Il testo del frammento {index} non coincide con la mappa "
                f"({actual_hash} != {entry.get('text_sha256')})"
            )

    opening_pattern = re.compile(r"<l(?:\s+[^>]*)?>")
    iterator = iter(zip(entries, lines, strict=True))

    def replacement(_: re.Match[str]) -> str:
        try:
            entry, current = next(iterator)
            return line_opening(entry, current)
        except StopIteration as error:
            raise ValueError("Il TEI contiene più <l> della mappa") from error

    xml, count = opening_pattern.subn(replacement, xml)
    if count != len(entries):
        raise ValueError(
            f"Sostituite {count} aperture <l>, attese {len(entries)}"
        )
    try:
        next(iterator)
    except StopIteration:
        pass
    else:
        raise ValueError("La mappa contiene più <l> del TEI")
    return xml


def add_lacunae(xml: str) -> str:
    """Insert the two lost verses present in the control edition."""

    for gap_number, next_number in ((1202, 1203), (1206, 1207)):
        pattern = re.compile(
            rf'^(?P<indent>[ \t]*)(?P<line><l [^>]*\bn="{next_number}"[^>]*>)',
            re.MULTILINE,
        )
        match = pattern.search(xml)
        if match is None:
            raise ValueError(
                f"Impossibile collocare la lacuna {gap_number} prima di {next_number}"
            )
        indentation = match.group("indent")
        gap = (
            f'{indentation}<l xml:id="ach-gap-{gap_number}" n="{gap_number}" '
            f'corresp="{REFERENCE_URN}:{gap_number}">'
            '<gap reason="lost"/></l>\n'
        )
        xml = xml[: match.start()] + gap + xml[match.start() :]
    return xml


def validate_result(xml: str, entries: list[dict[str, object]]) -> None:
    root = ET.fromstring(xml)
    lines = root.findall(f".//{{{TEI_NAMESPACE}}}l")
    speeches = root.findall(f".//{{{TEI_NAMESPACE}}}sp")
    if len(lines) != 1325 or len(speeches) != 481:
        raise ValueError(
            f"Conteggi finali inattesi: {len(lines)} <l>, {len(speeches)} <sp>"
        )

    identifiers = [
        element.get(XML_ID)
        for element in root.iter()
        if element.get(XML_ID)
    ]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("La numerazione ha prodotto xml:id duplicati")

    text_lines = [
        line
        for line in lines
        if (line.get(XML_ID) or "").startswith("ach-frag-")
    ]
    for line, entry in zip(text_lines, entries, strict=True):
        if (
            line.get(XML_ID) != entry["id"]
            or line.get("n") != entry.get("n")
            or line.get("part") != entry.get("part")
            or line.get("corresp") != " ".join(entry["corresp"])
        ):
            raise ValueError(f"Attributi non applicati correttamente: {entry!r}")

    gap_ids = {
        line.get(XML_ID)
        for line in lines
        if line.find(f"{{{TEI_NAMESPACE}}}gap") is not None
    }
    if gap_ids != {"ach-gap-1202", "ach-gap-1206"}:
        raise ValueError(f"Lacune finali inattese: {sorted(gap_ids)}")


def main() -> None:
    payload = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    entries = payload["alignment"]["lines"]

    source_bytes = TEI_PATH.read_bytes()
    line_ending = "\r\n" if b"\r\n" in source_bytes else "\n"
    xml = source_bytes.decode("utf-8").replace("\r\n", "\n")
    xml, removed = remove_duplicate_speeches(xml)
    xml = remove_managed_gaps(xml)
    xml = add_header_documentation(xml)
    xml = apply_map(xml, entries)
    xml = add_lacunae(xml)
    xml = xml.rstrip("\n") + "\n"
    validate_result(xml, entries)

    TEI_PATH.write_bytes(xml.replace("\n", line_ending).encode("utf-8"))
    removal_note = (
        f"; rimosse {', '.join(removed)}" if removed else "; duplicati già assenti"
    )
    print(
        f"Aggiornato {TEI_PATH}: {len(entries)} frammenti identificati e allineati"
        f"{removal_note}."
    )


if __name__ == "__main__":
    main()
