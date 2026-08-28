#!/usr/bin/env python3
"""Controlla il contratto dati e i casi limite del lettore degli Acarnesi."""

from __future__ import annotations

import json
import re
import sys
import threading
import unicodedata
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


CURATED_TERMS = (
    "πόλις",
    "χοῖρος",
    "σπονδή",
    "εἰρήνη",
    "ἀγορά",
    "ἀσπίς",
    "πόλεμος",
    "πρεσβευτής",
    "δραχμή",
)


class QuietLexArHandler(server.LexArHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass


def normalise(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value)
        if not unicodedata.category(character).startswith("M")
    ).casefold().strip()


def matching_speeches(speeches: list[dict], query: str) -> list[dict]:
    normalised_query = normalise(query)
    return [
        speech
        for speech in speeches
        if normalised_query
        in normalise(
            f"{speech.get('speaker') or ''} "
            + " ".join(line.get("text") or "" for line in speech["lines"])
        )
    ]


def load_public_payloads() -> tuple[list[dict], list[dict]]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietLexArHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_port}"

    try:
        with urlopen(
            f"{base_url}/api/works/acarnesi/speeches", timeout=10
        ) as response:
            api_speeches = json.load(response)["speeches"]
        with urlopen(
            f"{base_url}/script/data/work-texts.js", timeout=10
        ) as response:
            fallback_source = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=10)

    assignment = "globalThis.LEXAR_WORK_DATA = "
    start = fallback_source.index(assignment) + len(assignment)
    fallback_payload = json.loads(fallback_source[start:].strip().removesuffix(";"))
    return api_speeches, fallback_payload["acarnesi"]["speeches"]


def check_lexicon_links(errors: list[str]) -> None:
    vocabulary_html = (ROOT / "lessico/vocaboli.html").read_text()
    headwords = {
        normalise(re.sub(r"<[^>]+>", "", value))
        for value in re.findall(r'<div class="term"[^>]*>\s*<b>(.*?)</b>', vocabulary_html)
    }
    missing = [term for term in CURATED_TERMS if normalise(term) not in headwords]
    if missing:
        errors.append(f"voci lessicali curate mancanti: {', '.join(missing)}")
    if "../script/vocabulary-links.js" not in vocabulary_html:
        errors.append("script dei collegamenti lessicali non caricato")


def main() -> int:
    errors: list[str] = []
    server.initialise_database()

    try:
        api_speeches, fallback_speeches = load_public_payloads()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(f"API o fallback non caricabile: {error}")
        api_speeches = []
        fallback_speeches = []

    if api_speeches != fallback_speeches:
        errors.append("API e fallback statico espongono dati diversi")
    if len(api_speeches) != 481:
        errors.append(f"attesi 481 interventi, trovati {len(api_speeches)}")

    if api_speeches:
        accented = matching_speeches(api_speeches, "εἰρήνη")
        unaccented = matching_speeches(api_speeches, "ειρηνη")
        if not accented or len(accented) != len(unaccented):
            errors.append("ricerca accentata e non accentata incoerente")
        if not matching_speeches(api_speeches, "Diceopoli"):
            errors.append("ricerca per personaggio senza risultati")
        if matching_speeches(api_speeches, "nessunrisultato"):
            errors.append("la ricerca senza risultati produce corrispondenze")

        verse_index: dict[int, list[dict]] = {}
        for speech in api_speeches:
            for line in speech["lines"]:
                for verse in line["verses"]:
                    verse_index.setdefault(verse, []).append(line)

        if 425 not in verse_index:
            errors.append("verso esistente 425 non indicizzato")
        if 209 in verse_index:
            errors.append("verso di riscontro 209 indicizzato in modo inatteso")
        if len(verse_index.get(395, [])) < 2:
            errors.append("verso frammentato 395 non riconosciuto")
        if not any(line["gap"] for line in verse_index.get(1202, [])):
            errors.append("lacuna al verso 1202 non riconosciuta")
        if not any(
            line["verses"] == [1233, 1234]
            for line in verse_index.get(1234, [])
        ):
            errors.append("frammento condiviso dei vv. 1233–1234 non riconosciuto")

    reader_html = (ROOT / "item/acarnesi.html").read_text()
    reader_script = (ROOT / "script/work.js").read_text()
    shared_script = (ROOT / "script/script.js").read_text()
    for expected in (
        'id="verse-jump" novalidate',
        'aria-describedby="reader-jump-status"',
        'id="reader-data-source"',
        'class="reader-metric-legend"',
    ):
        if expected not in reader_html:
            errors.append(f"marcatore del lettore mancante: {expected}")
    if 'requestedSource === "fallback"' not in reader_script:
        errors.append("modalità diagnostica del fallback non disponibile")
    if 'menuLinks.classList.toggle("is-open", isOpen)' not in reader_script:
        errors.append("menu mobile della pagina opera non collegato")
    if 'event.key !== "Escape"' not in reader_script:
        errors.append("chiusura da tastiera del menu mobile non disponibile")
    if "articolato in ${fragmentCount} frammenti" not in reader_script:
        errors.append("messaggio per verso frammentato non disponibile")
    if "`${metricTitle(metric)} · ${status}`" not in reader_script:
        errors.append("stato delle scansioni metriche non visibile")
    if 'addEventListener("click", applySearch)' in shared_script:
        errors.append("gestore lessicale collegato a una funzione fuori ambito")
    if 'Elemento con data-bs-target="#testo-Acarnesi" non trovato' in shared_script:
        errors.append("avviso spurio del caricatore TEI sulle pagine lessicali")

    check_lexicon_links(errors)

    if errors:
        print("CONTROLLO LETTORE NON SUPERATO", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "CONTROLLO LETTORE SUPERATO: API e fallback equivalenti; "
        "ricerca, versi e collegamenti lessicali verificati."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
