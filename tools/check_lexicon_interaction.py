#!/usr/bin/env python3
"""Controlla dati, tokenizzazione e contratto UI del lessico nel lettore."""

from __future__ import annotations

import json
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from tools.lexicon_source import lexicon_entries, normalise_lexicon_key  # noqa: E402


EXPECTED_ENTRIES = 571
GREEK_WORD_PATTERN = re.compile(
    r"[\u0370-\u03ff\u1f00-\u1fff\u0300-\u036f]+"
    r"(?:[’'᾽][\u0370-\u03ff\u1f00-\u1fff\u0300-\u036f]*)?"
)


class QuietLexArHandler(server.LexArHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass


def public_lexicon_payloads() -> tuple[list[dict], list[dict]]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietLexArHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_port}"
    try:
        with urlopen(
            f"{base_url}/api/works/acarnesi/lexicon", timeout=10
        ) as response:
            api_entries = json.load(response)["entries"]
        with urlopen(
            f"{base_url}/script/data/lexicon-data.js", timeout=10
        ) as response:
            fallback_source = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=10)

    assignment = "globalThis.LEXAR_LEXICON_DATA = "
    start = fallback_source.index(assignment) + len(assignment)
    fallback = json.loads(fallback_source[start:].strip().removesuffix(";"))
    return api_entries, fallback["acarnesi"]["entries"]


def reconstructed(value: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in GREEK_WORD_PATTERN.finditer(value):
        parts.extend((value[cursor : match.start()], match.group()))
        cursor = match.end()
    parts.append(value[cursor:])
    return "".join(parts)


def main() -> int:
    errors: list[str] = []
    server.initialise_database()

    try:
        api_entries, fallback_entries = public_lexicon_payloads()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(f"API o fallback lessicale non caricabile: {error}")
        api_entries = []
        fallback_entries = []

    source_entries = lexicon_entries(ROOT, "acarnesi")
    if api_entries != fallback_entries or api_entries != source_entries:
        errors.append("fonte HTML, API e fallback lessicale espongono dati diversi")
    if len(source_entries) != EXPECTED_ENTRIES:
        errors.append(
            f"attese {EXPECTED_ENTRIES} voci degli Acarnesi, "
            f"trovate {len(source_entries)}"
        )

    keys = {str(entry.get("key") or "") for entry in source_entries}
    if len(keys) != len(source_entries):
        errors.append("le chiavi lessicali non sono univoche")
    for entry in source_entries:
        for field in ("key", "lemma", "grammar", "references", "meaning"):
            if not entry.get(field):
                errors.append(f"{entry.get('lemma', '?')}: campo {field} assente")
                break
    peace = next(
        (entry for entry in source_entries if entry["key"] == "ειρηνη"), None
    )
    if not peace or peace["lemma"] != "εἰρήνη" or "pace" not in peace["meaning"]:
        errors.append("voce campione εἰρήνη non estratta correttamente")

    matched_tokens = 0
    matched_keys: set[str] = set()
    for speech in server.speeches_for("acarnesi"):
        for line in speech["lines"]:
            value = line["text"]
            if reconstructed(value) != value:
                errors.append(f"tokenizzazione non conservativa in {line['id']}")
                break
            for match in GREEK_WORD_PATTERN.finditer(value):
                key = normalise_lexicon_key(match.group())
                if key in keys:
                    matched_tokens += 1
                    matched_keys.add(key)

    if matched_tokens < 200 or len(matched_keys) < 100:
        errors.append(
            "copertura lessicale inattesa: "
            f"{matched_tokens} forme, {len(matched_keys)} lemmi"
        )
    if normalise_lexicon_key("δ'") in keys:
        errors.append("un'elisione viene collegata in modo non conservativo")
    if reconstructed("ἀγορά, δ' εἰρήνη.") != "ἀγορά, δ' εἰρήνη.":
        errors.append("punteggiatura o apostrofo alterati dal tokenizzatore")

    html = (ROOT / "item" / "acarnesi.html").read_text(encoding="utf-8")
    script = (ROOT / "script" / "work.js").read_text(encoding="utf-8")
    stylesheet = (ROOT / "style" / "work.css").read_text(encoding="utf-8")
    for marker in (
        'script/data/lexicon-data.js?v=',
        'id="reader-lexicon-help"',
        'id="lexicon-card"',
        'role="dialog"',
        'id="lexicon-highlight-toggle"',
        'id="lexicon-card-link"',
    ):
        if marker not in html:
            errors.append(f"marcatore UI lessicale mancante: {marker}")
    for marker in (
        "appendInteractiveGreekText",
        'event.key === "Escape"',
        "MOBILE_LEXICON_QUERY",
        "setLexiconHighlights",
        "aria-expanded",
    ):
        if marker not in script:
            errors.append(f"comportamento lessicale mancante: {marker}")
    for marker in (
        ".tei-lexicon-token",
        ".reader-lexicon-card",
        ".reader-lexicon-backdrop",
        "env(safe-area-inset-bottom)",
    ):
        if marker not in stylesheet:
            errors.append(f"stile lessicale mancante: {marker}")

    if errors:
        print("CONTROLLO INTERAZIONE LESSICALE NON SUPERATO", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "CONTROLLO INTERAZIONE LESSICALE SUPERATO: "
        f"{EXPECTED_ENTRIES} voci; {matched_tokens} forme collegate a "
        f"{len(matched_keys)} lemmi; API, fallback e UI verificati."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
