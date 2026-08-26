#!/usr/bin/env python3
"""Controlla collegamenti e risorse locali delle pagine pubbliche di LexAr."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
HTML_ATTRIBUTES = frozenset({"href", "src", "action", "poster"})
CSS_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
SKIPPED_DIRECTORIES = frozenset({".git", "__pycache__"})
REQUIRED_NAVIGATION_TARGETS = {
    "Home": Path("index.html"),
    "Opere": Path("catalogo/catalogo1.html"),
    "Lessico": Path("lessico/lessicogen.html"),
}


@dataclass(frozen=True)
class Reference:
    source: Path
    line: int
    attribute: str
    value: str


class PageParser(HTMLParser):
    """Raccoglie identificatori e riferimenti senza dipendenze esterne."""

    def __init__(self, source: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.identifiers: dict[str, int] = {}
        self.duplicate_identifiers: list[tuple[str, int, int]] = []
        self.references: list[Reference] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._handle_attributes(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._handle_attributes(tag, attrs)

    def _handle_attributes(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        line, _ = self.getpos()
        for raw_name, raw_value in attrs:
            name = raw_name.casefold()
            value = (raw_value or "").strip()

            if (name == "id" or (name == "name" and tag == "a")) and value:
                previous_line = self.identifiers.get(value)
                if previous_line is not None:
                    self.duplicate_identifiers.append(
                        (value, previous_line, line)
                    )
                else:
                    self.identifiers[value] = line

            if name in HTML_ATTRIBUTES and value:
                self.references.append(
                    Reference(self.source, line, name, value)
                )
            elif name == "srcset" and value and not value.startswith("data:"):
                for candidate in value.split(","):
                    url = candidate.strip().split(maxsplit=1)[0]
                    if url:
                        self.references.append(
                            Reference(self.source, line, name, url)
                        )


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def public_files(root: Path, suffix: str) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(f"*{suffix}")
        if not any(part in SKIPPED_DIRECTORIES for part in path.parts)
    )


def load_pages(root: Path) -> tuple[dict[Path, PageParser], list[str]]:
    pages: dict[Path, PageParser] = {}
    errors: list[str] = []

    for path in public_files(root, ".html"):
        parser = PageParser(path)
        try:
            parser.feed(path.read_text(encoding="utf-8"))
            parser.close()
        except (OSError, UnicodeError) as error:
            errors.append(f"{relative(path, root)}: impossibile leggere: {error}")
            continue

        pages[path.resolve()] = parser
        for identifier, first_line, duplicate_line in parser.duplicate_identifiers:
            errors.append(
                f"{relative(path, root)}:{duplicate_line}: id duplicato "
                f"{identifier!r} (prima occorrenza alla riga {first_line})"
            )

    return pages, errors


def resolve_local_target(
    reference: Reference, root: Path
) -> tuple[Path | None, str, str | None]:
    value = reference.value.strip()
    if not value or value.startswith("//"):
        return None, "", None

    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None, "", None
    if parsed.path.startswith("/api/"):
        return None, parsed.fragment, None
    if "\\" in parsed.path:
        return None, parsed.fragment, "usa '/' al posto di '\\' nell'URL"

    decoded_path = unquote(parsed.path)
    if decoded_path.startswith("/"):
        target = root / decoded_path.lstrip("/")
    elif decoded_path:
        target = reference.source.parent / decoded_path
    else:
        target = reference.source

    resolved_root = root.resolve()
    resolved_target = target.resolve()
    if not resolved_target.is_relative_to(resolved_root):
        return None, parsed.fragment, "il percorso esce dalla repository"

    if decoded_path.endswith("/") or resolved_target.is_dir():
        resolved_target /= "index.html"
    return resolved_target, unquote(parsed.fragment), None


def check_html_references(
    root: Path, pages: dict[Path, PageParser]
) -> tuple[list[str], int]:
    errors: list[str] = []
    checked = 0

    for parser in pages.values():
        for reference in parser.references:
            target, fragment, resolution_error = resolve_local_target(
                reference, root
            )
            if resolution_error:
                errors.append(
                    f"{relative(reference.source, root)}:{reference.line}: "
                    f"{reference.attribute}={reference.value!r}: {resolution_error}"
                )
                continue
            if target is None:
                continue

            checked += 1
            if not target.exists():
                errors.append(
                    f"{relative(reference.source, root)}:{reference.line}: "
                    f"risorsa mancante {reference.value!r}"
                )
                continue

            if fragment and target.suffix.casefold() in {".html", ".htm"}:
                target_page = pages.get(target.resolve())
                if target_page is None:
                    errors.append(
                        f"{relative(reference.source, root)}:{reference.line}: "
                        f"pagina non analizzata {reference.value!r}"
                    )
                elif fragment not in target_page.identifiers:
                    errors.append(
                        f"{relative(reference.source, root)}:{reference.line}: "
                        f"ancora mancante #{fragment} in "
                        f"{relative(target, root)}"
                    )

    return errors, checked


def check_navigation(root: Path, pages: dict[Path, PageParser]) -> list[str]:
    """Verifica che ogni pagina conservi le tre vie di ritorno principali."""

    errors: list[str] = []
    required = {
        label: (root / path).resolve()
        for label, path in REQUIRED_NAVIGATION_TARGETS.items()
    }

    for page, parser in pages.items():
        destinations: set[Path] = set()
        for reference in parser.references:
            if reference.attribute != "href":
                continue
            target, _, resolution_error = resolve_local_target(reference, root)
            if target is not None and resolution_error is None:
                destinations.add(target.resolve())

        for label, target in required.items():
            if target not in destinations:
                errors.append(
                    f"{relative(page, root)}: manca un collegamento a {label} "
                    f"({relative(target, root)})"
                )

    return errors


def check_css_references(root: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    checked = 0

    for path in public_files(root, ".css"):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"{relative(path, root)}: impossibile leggere: {error}")
            continue

        for match in CSS_URL_PATTERN.finditer(content):
            value = match.group(2).strip()
            if not value or value.startswith(("data:", "#", "//")):
                continue

            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc:
                continue

            line = content.count("\n", 0, match.start()) + 1
            reference = Reference(path, line, "url", value)
            target, _, resolution_error = resolve_local_target(reference, root)
            if resolution_error:
                errors.append(
                    f"{relative(path, root)}:{line}: url={value!r}: "
                    f"{resolution_error}"
                )
                continue
            if target is None:
                continue

            checked += 1
            if not target.exists():
                errors.append(
                    f"{relative(path, root)}:{line}: risorsa mancante {value!r}"
                )

    return errors, checked


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="radice della repository (predefinita: repository corrente)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    pages, errors = load_pages(root)
    html_errors, html_count = check_html_references(root, pages)
    css_errors, css_count = check_css_references(root)
    errors.extend(html_errors)
    errors.extend(css_errors)
    errors.extend(check_navigation(root, pages))

    if errors:
        print("CONTROLLO LINK NON SUPERATO", file=sys.stderr)
        for error in sorted(errors):
            print(f"- {error}", file=sys.stderr)
        print(f"Errori: {len(errors)}", file=sys.stderr)
        return 1

    print(
        "CONTROLLO LINK SUPERATO: "
        f"{len(pages)} pagine HTML, {html_count} riferimenti HTML locali, "
        f"{css_count} risorse CSS locali."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
