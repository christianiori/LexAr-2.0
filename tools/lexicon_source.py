"""Estrazione strutturata delle voci lessicali dal repertorio HTML di LexAr."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path


WORK_LABELS = {
    "acarnesi": "Acarnesi",
}

GRAMMAR_LABELS = {
    "sost": "Sostantivo",
    "verbi": "Verbo",
    "verbo": "Verbo",
    "agg": "Aggettivo",
    "avv": "Avverbio",
}

DEFINITION_PREFIX = re.compile(r"^(?:s(?:/agg)?|v(?:\s+part)?|agg|avv)\s*:\s*", re.I)


class _VocabularyParser(HTMLParser):
    """Legge i blocchi ``.term`` senza introdurre dipendenze esterne."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict[str, object]] = []
        self._entry: dict[str, object] | None = None
        self._depth = 0
        self._in_headword = False
        self._headword_read = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if self._entry is None and tag == "div" and "term" in classes:
            self._entry = {
                "categories": attributes.get("data-category") or "",
                "headword_parts": [],
                "text_parts": [],
            }
            self._depth = 1
            self._in_headword = False
            self._headword_read = False
            return

        if self._entry is None:
            return
        if tag == "div":
            self._depth += 1
        elif tag == "b" and not self._headword_read:
            self._in_headword = True

    def handle_endtag(self, tag: str) -> None:
        if self._entry is None:
            return
        if tag == "b" and self._in_headword:
            self._in_headword = False
            self._headword_read = True
        if tag != "div":
            return

        self._depth -= 1
        if self._depth == 0:
            self.entries.append(self._entry)
            self._entry = None

    def handle_data(self, data: str) -> None:
        if self._entry is None:
            return
        self._entry["text_parts"].append(data)
        if self._in_headword:
            self._entry["headword_parts"].append(data)


def normalise_lexicon_key(value: str) -> str:
    """Crea una chiave senza accenti, conservando eventuali elisioni."""

    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.category(character).startswith("M")
    )
    return without_marks.replace("ς", "σ").strip()


def _clean_entry(raw: dict[str, object]) -> dict[str, object]:
    lemma = " ".join("".join(raw["headword_parts"]).split())
    full_text = " ".join("".join(raw["text_parts"]).split())
    remainder = full_text[len(lemma) :].strip()
    reference_text, definition = remainder.split("=", 1)
    references = reference_text.strip().removeprefix("(").removesuffix(")").strip()
    meaning = DEFINITION_PREFIX.sub("", definition.strip(), count=1)
    category_tokens = str(raw["categories"]).split()
    grammar = list(
        dict.fromkeys(
            GRAMMAR_LABELS[token]
            for token in category_tokens
            if token in GRAMMAR_LABELS
        )
    )
    return {
        "key": normalise_lexicon_key(lemma),
        "lemma": unicodedata.normalize("NFC", lemma),
        "grammar": grammar or ["Categoria non indicata"],
        "references": references,
        "meaning": meaning,
    }


@lru_cache(maxsize=None)
def lexicon_entries(project_root: Path, work_slug: str) -> list[dict[str, object]]:
    """Restituisce le voci curate associate a un'opera."""

    try:
        work_label = WORK_LABELS[work_slug]
    except KeyError as error:
        raise KeyError(work_slug) from error

    parser = _VocabularyParser()
    parser.feed((project_root / "lessico" / "vocaboli.html").read_text(encoding="utf-8"))
    entries = [
        _clean_entry(entry)
        for entry in parser.entries
        if work_label in str(entry["categories"]).split()
    ]
    entries.sort(key=lambda entry: (str(entry["key"]), str(entry["lemma"])))
    return entries
