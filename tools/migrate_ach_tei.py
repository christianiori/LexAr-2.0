#!/usr/bin/env python3
"""Migrate the legacy Acarnesi transcription to the first LexAr TEI model.

This is a deliberately narrow, one-shot migration.  It does not assign
canonical verse numbers: those require a separate collation with Coulon's
edition.  Before writing, the transformed document is parsed and checked so
that the number and order of speeches and verse fragments cannot change
silently.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEI_PATH = ROOT / "xml" / "ach.xml"

TEI_NAMESPACE = "http://www.tei-c.org/ns/1.0"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
XML_ID = f"{{{XML_NAMESPACE}}}id"

EXPECTED_SPEECHES = 483
EXPECTED_LINES = 1329
EXPECTED_DIVISIONS = 32

WHO_MAP = {
    "#Di": "#diceopoli",
    "#Ar": "#araldo",
    "Ar": "#araldo",
    "#An": "#anfiteo",
    "#Ve": "#vecchio",
    "#Ps": "#pseudoartabano",
    "#Te": "#teoro",
    "#Co": "#coro",
    "#Fi": "#figlia",
    "#Se": "#servo",
    "#Eu": "#euripide",
    "#SCA": "#semicoro-a",
    "#SCB": "#semicoro-b",
    "#La": "#lamaco",
    "#Ra": "#ragazza",
    "#Si": "#sicofante",
    "#Teb": "#tebano",
    "#Ni": "#nicarco",
    "#ML": "#messaggero-lamaco",
    "#Con": "#contadino",
    "#Da": "#damigella",
}

DIVISION_MAP = {
    "scena": ("section", "scene"),
    "Scena": ("section", "scene"),
    "Str": ("section", "choral"),
    "strofe": ("subsection", "strophe"),
    "antistrofe": ("subsection", "antistrophe"),
    "Str1a": ("subsection", "unclassified"),
    "Str1b": ("subsection", "unclassified"),
}

HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="acharnenses">
\t<teiHeader>
\t\t<fileDesc>
\t\t\t<titleStmt>
\t\t\t\t<title type="main" xml:lang="it">Gli Acarnesi</title>
\t\t\t\t<title type="original" xml:lang="grc">Ἀχαρνῆς</title>
\t\t\t\t<author ref="http://viaf.org/viaf/20962036">Aristofane</author>
\t\t\t\t<respStmt xml:id="lexar-project">
\t\t\t\t\t<resp>Creazione del progetto digitale LexAr</resp>
\t\t\t\t\t<name xml:id="christian-iori">Christian Iori</name>
\t\t\t\t</respStmt>
\t\t\t\t<respStmt xml:id="coulon">
\t\t\t\t\t<resp>Edizione critica di riferimento</resp>
\t\t\t\t\t<name ref="http://viaf.org/viaf/14813758">V. Coulon</name>
\t\t\t\t</respStmt>
\t\t\t</titleStmt>
\t\t\t<editionStmt>
\t\t\t\t<edition>Edizione digitale LexAr</edition>
\t\t\t</editionStmt>
\t\t\t<publicationStmt>
\t\t\t\t<publisher>LexAr</publisher>
\t\t\t\t<date when="2024">2024</date>
\t\t\t\t<idno type="URI">https://christianiori.github.io/LexAr/</idno>
\t\t\t\t<availability status="free">
\t\t\t\t\t<licence target="http://creativecommons.org/licenses/by/4.0/">
\t\t\t\t\t\tSalvo diversa indicazione, i contenuti originali di LexAr sono
\t\t\t\t\t\tdistribuiti con licenza Creative Commons Attribuzione 4.0
\t\t\t\t\t\tInternazionale.
\t\t\t\t\t</licence>
\t\t\t\t</availability>
\t\t\t</publicationStmt>
\t\t\t<sourceDesc>
\t\t\t\t<biblStruct xml:id="source-coulon-1923">
\t\t\t\t\t<monogr>
\t\t\t\t\t\t<author ref="http://viaf.org/viaf/20962036">Aristophanes</author>
\t\t\t\t\t\t<title level="m" xml:lang="la">Acharnenses</title>
\t\t\t\t\t\t<editor ref="http://viaf.org/viaf/14813758">V. Coulon</editor>
\t\t\t\t\t\t<edition>Ristampa 1967</edition>
\t\t\t\t\t\t<imprint>
\t\t\t\t\t\t\t<pubPlace>Paris</pubPlace>
\t\t\t\t\t\t\t<publisher>Les Belles Lettres</publisher>
\t\t\t\t\t\t\t<date when="1923">1923</date>
\t\t\t\t\t\t</imprint>
\t\t\t\t\t</monogr>
\t\t\t\t</biblStruct>
\t\t\t</sourceDesc>
\t\t</fileDesc>
\t\t<encodingDesc>
\t\t\t<projectDesc>
\t\t\t\t<p xml:lang="it">
\t\t\t\t\tLexAr è un progetto digitale dedicato alle commedie di Aristofane
\t\t\t\t\tche mette in relazione testi, lessico e informazioni di contesto
\t\t\t\t\tper sostenere lo studio del greco antico.
\t\t\t\t</p>
\t\t\t</projectDesc>
\t\t\t<editorialDecl>
\t\t\t\t<correction>
\t\t\t\t\t<p xml:lang="it">
\t\t\t\t\t\tSono corretti senza segnalazione nel testo soltanto errori
\t\t\t\t\t\tmeccanici di trascrizione inequivocabili. Le integrazioni e le
\t\t\t\t\t\tespunzioni già attribuite all'edizione di Coulon sono codificate
\t\t\t\t\t\trispettivamente con supplied e surplus.
\t\t\t\t\t</p>
\t\t\t\t</correction>
\t\t\t\t<normalization>
\t\t\t\t\t<p xml:lang="it">
\t\t\t\t\t\tLa grafia e l'accentazione greca della trascrizione sono
\t\t\t\t\t\tconservate; gli spazi tipografici privi di valore testuale sono
\t\t\t\t\t\tnormalizzati.
\t\t\t\t\t</p>
\t\t\t\t</normalization>
\t\t\t\t<hyphenation>
\t\t\t\t\t<p xml:lang="it">
\t\t\t\t\t\tLe parole spezzate alla fine di un elemento l restano conservate
\t\t\t\t\t\tin attesa della collazione con la numerazione dell'edizione.
\t\t\t\t\t</p>
\t\t\t\t</hyphenation>
\t\t\t\t<segmentation>
\t\t\t\t\t<p xml:lang="it">
\t\t\t\t\t\tLe battute sono rappresentate con sp, i frammenti di verso con
\t\t\t\t\t\tl e le divisioni con un vocabolario controllato di section e
\t\t\t\t\t\tsubsection. La terminologia non introduce categorie
\t\t\t\t\t\tfilologiche non documentate dalla trascrizione.
\t\t\t\t\t</p>
\t\t\t\t</segmentation>
\t\t\t</editorialDecl>
\t\t\t<refsDecl>
\t\t\t\t<p xml:lang="it">
\t\t\t\t\tDivisioni e battute possiedono identificatori XML stabili. I
\t\t\t\t\tnumeri canonici e gli identificatori dei versi saranno assegnati
\t\t\t\t\tdopo l'allineamento con l'edizione di riferimento.
\t\t\t\t</p>
\t\t\t</refsDecl>
\t\t</encodingDesc>
\t\t<profileDesc>
\t\t\t<langUsage>
\t\t\t\t<language ident="grc">Greco antico</language>
\t\t\t\t<language ident="it">Italiano</language>
\t\t\t\t<language ident="la">Latino</language>
\t\t\t</langUsage>
\t\t\t<textClass>
\t\t\t\t<keywords scheme="http://id.loc.gov/authorities/subjects/">
\t\t\t\t\t<term ref="http://id.loc.gov/authorities/subjects/sh85134522">Testo drammatico</term>
\t\t\t\t\t<term ref="http://id.loc.gov/authorities/subjects/sh85028845">Commedia</term>
\t\t\t\t</keywords>
\t\t\t</textClass>
\t\t\t<particDesc>
\t\t\t\t<listPerson type="dramatis-personae">
\t\t\t\t\t<person xml:id="diceopoli"><persName xml:lang="it">Diceopoli</persName></person>
\t\t\t\t\t<person xml:id="araldo"><persName xml:lang="it">Araldo</persName></person>
\t\t\t\t\t<person xml:id="anfiteo"><persName xml:lang="it">Anfiteo</persName></person>
\t\t\t\t\t<person xml:id="vecchio"><persName xml:lang="it">Vecchio</persName></person>
\t\t\t\t\t<person xml:id="pseudoartabano"><persName xml:lang="it">Pseudoartabano</persName></person>
\t\t\t\t\t<person xml:id="teoro"><persName xml:lang="it">Teoro</persName></person>
\t\t\t\t\t<personGrp xml:id="coro"><persName xml:lang="it">Coro</persName></personGrp>
\t\t\t\t\t<personGrp xml:id="semicoro-a" corresp="#coro"><persName xml:lang="it">Semicoro A</persName></personGrp>
\t\t\t\t\t<personGrp xml:id="semicoro-b" corresp="#coro"><persName xml:lang="it">Semicoro B</persName></personGrp>
\t\t\t\t\t<person xml:id="figlia"><persName xml:lang="it">Figlia</persName></person>
\t\t\t\t\t<person xml:id="servo"><persName xml:lang="it">Servo</persName></person>
\t\t\t\t\t<person xml:id="euripide"><persName xml:lang="it">Euripide</persName></person>
\t\t\t\t\t<person xml:id="lamaco"><persName xml:lang="it">Lamaco</persName></person>
\t\t\t\t\t<person xml:id="megarese"><persName xml:lang="it">Megarese</persName></person>
\t\t\t\t\t<person xml:id="ragazza"><persName xml:lang="it">Ragazza</persName></person>
\t\t\t\t\t<person xml:id="sicofante"><persName xml:lang="it">Sicofante</persName></person>
\t\t\t\t\t<person xml:id="tebano"><persName xml:lang="it">Tebano</persName></person>
\t\t\t\t\t<person xml:id="nicarco"><persName xml:lang="it">Nicarco</persName></person>
\t\t\t\t\t<person xml:id="messaggero-lamaco"><persName xml:lang="it">Messaggero di Lamaco</persName></person>
\t\t\t\t\t<person xml:id="contadino"><persName xml:lang="it">Contadino</persName></person>
\t\t\t\t\t<person xml:id="damigella"><persName xml:lang="it">Damigella</persName></person>
\t\t\t\t\t<person xml:id="messaggero-dioniso">
\t\t\t\t\t\t<persName xml:lang="it">Messaggero</persName>
\t\t\t\t\t\t<note xml:lang="it">Reca a Diceopoli l'invito del sacerdote di Dioniso.</note>
\t\t\t\t\t</person>
\t\t\t\t\t<person xml:id="messaggero-finale"><persName xml:lang="it">Messaggero</persName></person>
\t\t\t\t</listPerson>
\t\t\t</particDesc>
\t\t</profileDesc>
\t\t<revisionDesc>
\t\t\t<change when="2026-07-28">
\t\t\t\tNormalizzazione dell'intestazione, dei riferimenti ai personaggi,
\t\t\t\tdelle divisioni e degli interventi editoriali.
\t\t\t</change>
\t\t\t<change when="2024">Pubblicazione iniziale dichiarata del testo digitale.</change>
\t\t</revisionDesc>
\t</teiHeader>"""

FRONT = """\t\t<front xml:lang="it">
\t\t\t<castList xml:id="acharnenses-cast">
\t\t\t\t<head>Personaggi</head>
\t\t\t\t<castItem corresp="#diceopoli"><role>Diceopoli</role></castItem>
\t\t\t\t<castItem corresp="#araldo"><role>Araldo</role></castItem>
\t\t\t\t<castItem corresp="#anfiteo"><role>Anfiteo</role></castItem>
\t\t\t\t<castItem corresp="#vecchio"><role>Vecchio</role></castItem>
\t\t\t\t<castItem corresp="#pseudoartabano"><role>Pseudoartabano</role></castItem>
\t\t\t\t<castItem corresp="#teoro"><role>Teoro</role></castItem>
\t\t\t\t<castGroup>
\t\t\t\t\t<head>Coro</head>
\t\t\t\t\t<castItem corresp="#coro"><role>Coro</role></castItem>
\t\t\t\t\t<castItem corresp="#semicoro-a"><role>Semicoro A</role></castItem>
\t\t\t\t\t<castItem corresp="#semicoro-b"><role>Semicoro B</role></castItem>
\t\t\t\t</castGroup>
\t\t\t\t<castItem corresp="#figlia"><role>Figlia</role></castItem>
\t\t\t\t<castItem corresp="#servo"><role>Servo</role></castItem>
\t\t\t\t<castItem corresp="#euripide"><role>Euripide</role></castItem>
\t\t\t\t<castItem corresp="#lamaco"><role>Lamaco</role></castItem>
\t\t\t\t<castItem corresp="#megarese"><role>Megarese</role></castItem>
\t\t\t\t<castItem corresp="#ragazza"><role>Ragazza</role></castItem>
\t\t\t\t<castItem corresp="#sicofante"><role>Sicofante</role></castItem>
\t\t\t\t<castItem corresp="#tebano"><role>Tebano</role></castItem>
\t\t\t\t<castItem corresp="#nicarco"><role>Nicarco</role></castItem>
\t\t\t\t<castItem corresp="#messaggero-lamaco"><role>Messaggero di Lamaco</role></castItem>
\t\t\t\t<castItem corresp="#contadino"><role>Contadino</role></castItem>
\t\t\t\t<castItem corresp="#damigella"><role>Damigella</role></castItem>
\t\t\t\t<castItem corresp="#messaggero-dioniso">
\t\t\t\t\t<role>Messaggero</role>
\t\t\t\t\t<roleDesc>Reca l'invito del sacerdote di Dioniso.</roleDesc>
\t\t\t\t</castItem>
\t\t\t\t<castItem corresp="#messaggero-finale"><role>Messaggero</role></castItem>
\t\t\t</castList>
\t\t</front>"""


def count_elements(xml: str, local_name: str) -> int:
    root = ET.fromstring(xml)
    return len(root.findall(f".//{{{TEI_NAMESPACE}}}{local_name}"))


def replace_header(xml: str) -> str:
    pattern = re.compile(r"\A(?:<\?xml[^?]*\?>\s*)?<TEI\b[^>]*>.*?</teiHeader>", re.DOTALL)
    migrated, replacements = pattern.subn(HEADER, xml, count=1)
    if replacements != 1:
        raise ValueError("Intestazione TEI legacy non riconosciuta")
    return migrated


def add_front_and_languages(xml: str) -> str:
    migrated, replacements = re.subn(
        r"\t<text>\s*\n\t\t<body>",
        f'\t<text xml:id="acharnenses-text">\n{FRONT}\n\t\t<body xml:lang="grc">',
        xml,
        count=1,
    )
    if replacements != 1:
        raise ValueError("Apertura <text>/<body> legacy non riconosciuta")
    return migrated


def normalise_editorial_markup(xml: str) -> str:
    xml = re.sub(
        r'<add\s+resp="[^"]+">‹([^‹›]+)›</add>',
        r'<supplied reason="omitted" resp="#coulon">\1</supplied>',
        xml,
    )
    xml = re.sub(
        r"<del\s+resp=\"[^\"]+\">\[([^\[\]]+)\]</del>",
        r'<surplus resp="#coulon">\1</surplus>',
        xml,
    )
    xml = re.sub(
        r'<del\s+resp="[^"]+">([^<]+)</del>',
        r'<surplus resp="#coulon">\1</surplus>',
        xml,
    )
    xml = re.sub(
        r"‹([^‹›]+)›",
        r'<supplied reason="omitted" resp="#coulon">\1</supplied>',
        xml,
    )
    return xml


def repair_known_transcription_errors(xml: str) -> str:
    replacements = {
        "0καταπελτάσονται": "καταπελτάσονται",
        "Ἱερωνύμουz": "Ἱερωνύμου",
        "0εἶτα": "εἶτα",
        "0ὡς": "ὡς",
        "σελαγοῖντ' ἂν ὑπὸ τίφης τε καὶ θρυαλλίδος;.": (
            "σελαγοῖντ' ἂν ὑπὸ τίφης τε καὶ θρυαλλίδος;"
        ),
    }
    for source, target in replacements.items():
        if xml.count(source) != 1:
            raise ValueError(f"Refuso atteso non trovato una sola volta: {source!r}")
        xml = xml.replace(source, target)

    xml = xml.replace("\u2007", "")
    xml = re.sub(r"<l> +", "<l>", xml)
    xml = re.sub(r" +</l>", "</l>", xml)
    xml = re.sub(r"[ \t]+(?=\n)", "", xml)
    return xml


def add_missing_speaker(xml: str) -> str:
    pattern = re.compile(
        r'(<sp who="#Teb">\s*)(<l>Ὅ τι γ\' ἔστ\' Ἀθάνασ\')'
    )
    migrated, replacements = pattern.subn(
        r"\1<speaker>Tebano</speaker>\n\t\t\t\t\t\2",
        xml,
        count=1,
    )
    if replacements != 1:
        raise ValueError("Intervento del Tebano senza <speaker> non riconosciuto")
    return migrated


def disambiguate_messengers(xml: str) -> str:
    pattern = re.compile(
        r'(<sp who=")#Me(">\s*<speaker>Messaggero</speaker>)'
    )
    seen = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal seen
        seen += 1
        target = "#messaggero-dioniso" if seen <= 2 else "#messaggero-finale"
        return f"{match.group(1)}{target}{match.group(2)}"

    migrated = pattern.sub(replacement, xml)
    if seen != 3:
        raise ValueError(f"Attesi 3 interventi ambigui del Messaggero, trovati {seen}")

    migrated, megarese_count = re.subn(
        r'(<sp who=")#Me(">\s*<speaker>Megarese</speaker>)',
        r"\1#megarese\2",
        migrated,
    )
    if megarese_count != 33:
        raise ValueError(
            f"Attesi 33 interventi del Megarese, trovati {megarese_count}"
        )
    return migrated


def add_speech_ids_and_resolve_who(xml: str) -> str:
    counter = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        old_who = match.group(1)
        who = WHO_MAP.get(old_who, old_who)
        if not who.startswith("#"):
            raise ValueError(f"Riferimento @who non risolto: {old_who!r}")
        return f'<sp xml:id="ach-sp-{counter:04d}" who="{who}">'

    migrated = re.sub(r'<sp\s+who="([^"]+)">', replacement, xml)
    if counter != EXPECTED_SPEECHES:
        raise ValueError(
            f"Attesi {EXPECTED_SPEECHES} interventi, migrati {counter}"
        )
    migrated = migrated.replace("<speaker>", '<speaker xml:lang="it">')
    migrated = migrated.replace(">SemicoroA</speaker>", ">Semicoro A</speaker>")
    migrated = migrated.replace(">SemicoroB</speaker>", ">Semicoro B</speaker>")
    return migrated


def normalise_divisions(xml: str) -> str:
    counter = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        old_type = match.group(1)
        old_n = match.group(2)
        division_type, subtype = DIVISION_MAP[old_type]
        if old_type == "Str1a":
            old_n = "1a"
        elif old_type == "Str1b":
            old_n = "1b"
        n_attribute = f' n="{old_n}"' if old_n else ""
        return (
            f'<div xml:id="ach-div-{counter:03d}" type="{division_type}" '
            f'subtype="{subtype}"{n_attribute}>'
        )

    migrated = re.sub(
        r'<div\s+type="([^"]+)"(?:\s+n="([^"]+)")?>',
        replacement,
        xml,
    )
    if counter != EXPECTED_DIVISIONS:
        raise ValueError(
            f"Attese {EXPECTED_DIVISIONS} divisioni, migrate {counter}"
        )
    return migrated


def validate_migration(xml: str) -> None:
    root = ET.fromstring(xml)
    speeches = root.findall(f".//{{{TEI_NAMESPACE}}}sp")
    lines = root.findall(f".//{{{TEI_NAMESPACE}}}l")
    divisions = root.findall(f".//{{{TEI_NAMESPACE}}}div")

    if len(speeches) != EXPECTED_SPEECHES:
        raise ValueError("La migrazione ha modificato il numero degli interventi")
    if len(lines) != EXPECTED_LINES:
        raise ValueError("La migrazione ha modificato il numero dei frammenti di verso")
    if len(divisions) != EXPECTED_DIVISIONS:
        raise ValueError("La migrazione ha modificato il numero delle divisioni")

    ids = [
        element.get(XML_ID)
        for element in root.iter()
        if element.get(XML_ID)
    ]
    if len(ids) != len(set(ids)):
        raise ValueError("La migrazione ha prodotto xml:id duplicati")

    target_ids = set(ids)
    for speech in speeches:
        speech_id = speech.get(XML_ID)
        who = speech.get("who", "")
        if not speech_id or not who.startswith("#") or who[1:] not in target_ids:
            raise ValueError(
                f"Intervento non risolto dopo la migrazione: {speech_id=} {who=}"
            )
        speaker = speech.find(f"{{{TEI_NAMESPACE}}}speaker")
        if speaker is None or not "".join(speaker.itertext()).strip():
            raise ValueError(f"Intervento senza speaker dopo la migrazione: {speech_id}")

    if any(marker in xml for marker in ("‹", "›", "<add ", "<del ")):
        raise ValueError("Sono rimasti marcatori editoriali legacy")


def main() -> None:
    source_bytes = TEI_PATH.read_bytes()
    line_ending = "\r\n" if b"\r\n" in source_bytes else "\n"
    source = source_bytes.decode("utf-8").replace("\r\n", "\n")
    if 'xml:id="acharnenses"' in source:
        raise SystemExit("ach.xml risulta già migrato")

    if count_elements(source, "sp") != EXPECTED_SPEECHES:
        raise ValueError("Numero iniziale degli interventi inatteso")
    if count_elements(source, "l") != EXPECTED_LINES:
        raise ValueError("Numero iniziale dei frammenti di verso inatteso")

    migrated = replace_header(source)
    migrated = add_front_and_languages(migrated)
    migrated = normalise_editorial_markup(migrated)
    migrated = repair_known_transcription_errors(migrated)
    migrated = add_missing_speaker(migrated)
    migrated = disambiguate_messengers(migrated)
    migrated = add_speech_ids_and_resolve_who(migrated)
    migrated = normalise_divisions(migrated)
    migrated = migrated.rstrip("\n") + "\n"
    validate_migration(migrated)

    TEI_PATH.write_bytes(migrated.replace("\n", line_ending).encode("utf-8"))
    print(
        f"Migrato {TEI_PATH}: {EXPECTED_DIVISIONS} divisioni, "
        f"{EXPECTED_SPEECHES} interventi, {EXPECTED_LINES} frammenti di verso."
    )


if __name__ == "__main__":
    main()
