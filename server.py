"""Server locale per LexAr.

Avvio: python server.py
Poi aprire http://localhost:8000/
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATABASE = DATA_DIR / "lexar.sqlite3"
TEI_NAMESPACE = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
WORKS = {
    "acarnesi": {
        "title": "Gli Acarnesi",
        "tei": ROOT / "xml" / "ach.xml",
        "metadata": ROOT / "xml" / "metach.xml",
        "page": "item/acarnesi.html",
        "year": -425,
    }
    , "cavalieri": {"title": "I Cavalieri", "tei": None, "page": "item/cavalieri.html", "year": -424}
    , "nuvole": {"title": "Le Nuvole", "tei": None, "page": "item/nuvole.html", "year": -423}
    , "vespe": {"title": "Le Vespe", "tei": None, "page": "item/vespe.html", "year": -422}
    , "pace": {"title": "La Pace", "tei": None, "page": "item/pace.html", "year": -421}
    , "uccelli": {"title": "Gli Uccelli", "tei": None, "page": "item/uccelli.html", "year": -414}
    , "tesmoforie": {
        "title": "Le Donne alle Tesmoforie", "tei": None,
        "metadata": ROOT / "xml" / "mettesm.xml", "page": "item/tesmoforie.html", "year": -411
    }
    , "lisistrata": {"title": "Lisistrata", "tei": None, "page": "item/lisistrata.html", "year": -411}
    , "rane": {"title": "Le Rane", "tei": None, "page": "item/rane.html", "year": -405}
    , "donne": {"title": "Le Donne al Parlamento", "tei": None, "page": "item/donne.html", "year": -392}
    , "pluto": {"title": "Il Pluto", "tei": None, "page": "item/pluto.html", "year": -388}
}


def database_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def normalise(text: str) -> str:
    return " ".join(text.split())


def initialise_database() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with database_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS works (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                tei_path TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS lines (
                id INTEGER PRIMARY KEY,
                work_slug TEXT NOT NULL REFERENCES works(slug),
                position INTEGER NOT NULL,
                speech_position INTEGER,
                speech_id TEXT,
                scene TEXT,
                section_id TEXT,
                speaker TEXT,
                speaker_ref TEXT,
                text TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lines_work_position
                ON lines(work_slug, position);
            """
        )
        ensure_column(connection, "lines", "speech_position", "INTEGER")
        ensure_column(connection, "lines", "speech_id", "TEXT")
        ensure_column(connection, "lines", "section_id", "TEXT")
        ensure_column(connection, "lines", "speaker_ref", "TEXT")
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_lines_work_speech
               ON lines(work_slug, speech_position)"""
        )
        for slug, work in WORKS.items():
            if work.get("tei"):
                import_work(connection, slug, work)
            else:
                connection.execute(
                    """INSERT INTO works (slug, title, tei_path, imported_at)
                       VALUES (?, ?, '', CURRENT_TIMESTAMP)
                       ON CONFLICT(slug) DO UPDATE SET title = excluded.title""",
                    (slug, work["title"]),
                )


def ensure_column(
    connection: sqlite3.Connection, table: str, column: str, declaration: str
) -> None:
    """Add a column to the generated cache when an older schema is present."""

    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})")
    }
    if column not in columns:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
        )


def import_work(connection: sqlite3.Connection, slug: str, work: dict[str, object]) -> None:
    """Importa il TEI a ogni avvio: la sorgente XML resta autorevole."""
    tei_path = Path(work["tei"])
    root = ET.parse(tei_path).getroot()
    title = normalise(root.findtext(".//tei:title", default=work["title"], namespaces=TEI_NAMESPACE))
    connection.execute("DELETE FROM lines WHERE work_slug = ?", (slug,))
    connection.execute(
        """INSERT INTO works (slug, title, tei_path, imported_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(slug) DO UPDATE SET
             title = excluded.title, tei_path = excluded.tei_path, imported_at = excluded.imported_at""",
        (slug, title, tei_path.relative_to(ROOT).as_posix()),
    )
    rows = []
    position = 0
    parent_map = {
        child: parent
        for parent in root.iter()
        for child in parent
    }
    speaker_by_who = {}
    speeches = root.findall(".//tei:sp", TEI_NAMESPACE)

    for speech in speeches:
        speaker = normalise(speech.findtext("tei:speaker", default="", namespaces=TEI_NAMESPACE))
        who = speech.get("who")
        if speaker and who:
            speaker_by_who[who] = speaker

    for speech_position, speech in enumerate(speeches, start=1):
        speaker = normalise(speech.findtext("tei:speaker", default="", namespaces=TEI_NAMESPACE))
        speaker = speaker or speaker_by_who.get(speech.get("who")) or None
        speech_id = speech.get(XML_ID) or f"{slug}-sp-{speech_position:04d}"
        speaker_ref = speech.get("who")
        section, section_id = tei_section_info(speech, parent_map)
        for line in speech.findall(".//tei:l", TEI_NAMESPACE):
            text = normalise(tei_display_text(line))
            if text:
                position += 1
                rows.append(
                    (
                        slug,
                        position,
                        speech_position,
                        speech_id,
                        section,
                        section_id,
                        speaker,
                        speaker_ref,
                        text,
                    )
                )
    connection.executemany(
        """INSERT INTO lines (
               work_slug, position, speech_position, speech_id, scene,
               section_id, speaker, speaker_ref, text
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def tei_display_text(element: ET.Element) -> str:
    """Render inline editorial semantics without flattening their meaning."""

    parts = [element.text or ""]
    wrappers = {
        "supplied": ("‹", "›"),
        "surplus": ("[", "]"),
    }
    for child in element:
        child_text = tei_display_text(child)
        opening, closing = wrappers.get(child.tag.rsplit("}", 1)[-1], ("", ""))
        parts.extend((opening, child_text, closing, child.tail or ""))
    return "".join(parts)


def tei_section_info(
    element: ET.Element, parent_map: dict[ET.Element, ET.Element]
) -> tuple[str | None, str | None]:
    """Return the nearest LexAr scene/choral label and stable division ID."""

    current = element
    while current in parent_map:
        current = parent_map[current]
        if current.tag != f"{{{TEI_NAMESPACE['tei']}}}div":
            continue
        division_type = (current.get("type") or "").casefold()
        division_subtype = (current.get("subtype") or "").casefold()
        section_number = current.get("n")
        section_id = current.get(XML_ID)

        if division_type == "section" and division_subtype == "scene":
            return section_number, section_id
        if division_type == "section" and division_subtype == "choral":
            label = f"Coro {section_number}" if section_number else "Coro"
            return label, section_id

        # Compatibilità temporanea con TEI non ancora migrati.
        if division_type == "scena":
            return section_number, section_id
        if division_type == "str":
            label = f"Coro {section_number}" if section_number else "Coro"
            return label, section_id
    return None, None


class LexArHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        # Il database locale non deve essere esposto dal server di file statici.
        if parsed.path == "/data" or parsed.path.startswith("/data/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not parsed.path.startswith("/api/"):
            return super().do_GET()
        try:
            self.handle_api(parsed)
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except KeyError:
            self.send_json({"error": "Risorsa non trovata."}, HTTPStatus.NOT_FOUND)

    def handle_api(self, parsed) -> None:
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            with database_connection() as connection:
                work_count = connection.execute("SELECT COUNT(*) FROM works").fetchone()[0]
            return self.send_json({"status": "ok", "work_count": work_count})
        if parsed.path == "/api/works":
            with database_connection() as connection:
                works = [public_work(dict(row)) for row in connection.execute("SELECT slug, title, imported_at FROM works ORDER BY title")]
            return self.send_json({"works": works})
        if parsed.path == "/api/terms":
            slug = query.get("work", ["acarnesi"])[0]
            limit = bounded_int(query.get("limit", ["30"])[0], 1, 100)
            return self.send_json({"work": slug, "terms": frequent_terms(slug, limit)})

        parts = parsed.path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "works"]:
            return self.send_json(work_summary(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "works"] and parts[3] == "speeches":
            return self.send_json({"work": parts[2], "speeches": speeches_for(parts[2])})
        raise KeyError

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def bounded_int(value: str, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(int(value), maximum))
    except ValueError as error:
        raise ValueError("Il parametro limit deve essere un numero intero.") from error


def work_summary(slug: str) -> dict:
    with database_connection() as connection:
        work = connection.execute("SELECT slug, title, imported_at FROM works WHERE slug = ?", (slug,)).fetchone()
        if not work:
            raise KeyError
        result = public_work(dict(work))
        result["line_count"] = connection.execute("SELECT COUNT(*) FROM lines WHERE work_slug = ?", (slug,)).fetchone()[0]
    return result


def public_work(work: dict) -> dict:
    source = WORKS[work["slug"]]
    return {
        **work,
        "page": source["page"],
        "year": source["year"],
        "has_tei": bool(source.get("tei")),
        "has_metadata": bool(source.get("metadata")),
    }


def speeches_for(slug: str) -> list[dict]:
    with database_connection() as connection:
        if not connection.execute("SELECT 1 FROM works WHERE slug = ?", (slug,)).fetchone():
            raise KeyError
        rows = connection.execute(
            """SELECT speech_id, scene, section_id, speaker, speaker_ref, text
               FROM lines
               WHERE work_slug = ?
               ORDER BY position""",
            (slug,),
        ).fetchall()
    speeches = []
    current = None
    for row in rows:
        if current is None or row["speech_id"] != current["id"]:
            current = {
                "id": row["speech_id"],
                "scene": row["scene"],
                "section_id": row["section_id"],
                "speaker": row["speaker"],
                "speaker_ref": row["speaker_ref"],
                "lines": [],
            }
            speeches.append(current)
        current["lines"].append(row["text"])
    return speeches


def frequent_terms(slug: str, limit: int) -> list[dict]:
    with database_connection() as connection:
        rows = connection.execute("SELECT text FROM lines WHERE work_slug = ?", (slug,)).fetchall()
    words = []
    for row in rows:
        for word in row["text"].split():
            clean = "".join(char for char in unicodedata.normalize("NFC", word.lower()) if char.isalpha())
            if len(clean) > 2:
                words.append(clean)
    return [{"term": term, "frequency": frequency} for term, frequency in Counter(words).most_common(limit)]


def main() -> None:
    initialise_database()
    # Render deve poter raggiungere il processo dall'esterno del container.
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), LexArHandler)
    print(f"LexAr disponibile su http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer arrestato.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
