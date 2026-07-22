"""Server locale per LexAr.

Avvio: python server.py
Poi aprire http://localhost:8000/
"""

from __future__ import annotations

import json
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
WORKS = {
    "acarnesi": {
        "title": "Gli Acarnesi",
        "tei": ROOT / "xml" / "ach.xml",
        "metadata": ROOT / "xml" / "metach.xml",
    }
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
                scene TEXT,
                speaker TEXT,
                text TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lines_work_position
                ON lines(work_slug, position);
            """
        )
        for slug, work in WORKS.items():
            import_work(connection, slug, work)


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
    for scene in root.findall(".//tei:div[@type='scena']", TEI_NAMESPACE):
        scene_number = scene.get("n")
        for speech in scene.findall("tei:sp", TEI_NAMESPACE):
            speaker = normalise(speech.findtext("tei:speaker", default="", namespaces=TEI_NAMESPACE)) or None
            for line in speech.findall(".//tei:l", TEI_NAMESPACE):
                text = normalise("".join(line.itertext()))
                if text:
                    position += 1
                    rows.append((slug, position, scene_number, speaker, text))
    connection.executemany(
        "INSERT INTO lines (work_slug, position, scene, speaker, text) VALUES (?, ?, ?, ?, ?)", rows
    )


class LexArHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
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
            return self.send_json({"status": "ok"})
        if parsed.path == "/api/works":
            with database_connection() as connection:
                works = [dict(row) for row in connection.execute("SELECT slug, title, imported_at FROM works ORDER BY title")]
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
        result = dict(work)
        result["line_count"] = connection.execute("SELECT COUNT(*) FROM lines WHERE work_slug = ?", (slug,)).fetchone()[0]
    return result


def speeches_for(slug: str) -> list[dict]:
    with database_connection() as connection:
        if not connection.execute("SELECT 1 FROM works WHERE slug = ?", (slug,)).fetchone():
            raise KeyError
        rows = connection.execute(
            "SELECT scene, speaker, text FROM lines WHERE work_slug = ? ORDER BY position", (slug,)
        ).fetchall()
    speeches = []
    current = None
    for row in rows:
        identity = (row["scene"], row["speaker"])
        if current is None or identity != (current["scene"], current["speaker"]):
            current = {"scene": row["scene"], "speaker": row["speaker"], "lines": []}
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
    server = ThreadingHTTPServer(("127.0.0.1", 8000), LexArHandler)
    print("LexAr disponibile su http://localhost:8000/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer arrestato.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
