"""Resolve the registered bibliography against primary metadata and emit BibTeX."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "reference_manifest.json"
DEFAULT_RAW = ROOT.parent / "sources" / "reference_metadata_raw.json"
DEFAULT_REPORT = ROOT / "artifacts" / "reference_verification_report.json"
DEFAULT_BIB = ROOT / "maintrack" / "references_verified.bib"
CROSSREF_URL = "https://api.crossref.org/works"


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def source_name(work: dict[str, Any]) -> str:
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    return str(source.get("display_name") or "")


def source_type(work: dict[str, Any]) -> str:
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    return str(source.get("type") or "")


class CitationMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        key = values.get("name") or values.get("property")
        content = values.get("content")
        if key and content:
            self.meta.setdefault(key.lower(), []).append(content)


def metadata_work(
    entry: dict[str, Any],
    *,
    identifier: str,
    title: str,
    year: int,
    authors: list[str],
    venue: str,
    doi: str = "",
    source: str,
    work_type: str = "article",
    venue_type: str = "",
    retraction_signal: bool = False,
) -> dict[str, Any] | None:
    if normalize_title(title) != normalize_title(str(entry["title"])):
        return None
    verification_year = int(entry.get("metadata_year", entry["year"]))
    if abs(year - verification_year) > 1:
        return None
    return {
        "id": identifier,
        "doi": f"https://doi.org/{doi}" if doi else None,
        "title": title,
        "publication_year": year,
        "publication_date": str(year),
        "type": work_type,
        "cited_by_count": None,
        "authorships": [
            {"author": {"display_name": author}} for author in authors
        ],
        "primary_location": {
            "source": {"display_name": venue, "type": venue_type}
        },
        "is_retracted": retraction_signal,
        "verification_source": source,
    }


def crossref_fallback(entry: dict[str, Any], session: requests.Session) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    parsed = urlparse(str(entry["url"]))
    if parsed.netloc.lower() not in {"doi.org", "dx.doi.org"}:
        return None, {}
    doi = parsed.path.lstrip("/")
    response = session.get(
        f"{CROSSREF_URL}/{quote(doi, safe='')}",
        params={"mailto": "vera-reference-audit@example.com"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    message = payload.get("message", {})
    date_parts = (
        message.get("published-print", {}).get("date-parts")
        or message.get("published-online", {}).get("date-parts")
        or message.get("issued", {}).get("date-parts")
        or [[-100]]
    )
    year = int(date_parts[0][0])
    authors = [
        " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part)
        for author in message.get("author", [])
    ]
    venue_values = message.get("container-title", [])
    venue = str(venue_values[0]) if venue_values else str(message.get("publisher") or "")
    title_values = message.get("title", [])
    subtitle_values = message.get("subtitle", [])
    title = str(title_values[0]) if title_values else ""
    if subtitle_values:
        title = f"{title}: {subtitle_values[0]}"
    crossref_type = str(message.get("type") or "")
    venue_type = "journal" if crossref_type == "journal-article" else "conference"
    retraction_signal = any(
        str(update.get("type") or "").lower() == "retraction"
        for update in message.get("update-to", [])
    )
    return (
        metadata_work(
            entry,
            identifier=f"crossref:{doi}",
            title=title,
            year=year,
            authors=authors,
            venue=venue,
            doi=doi,
            source="Crossref",
            work_type=crossref_type,
            venue_type=venue_type,
            retraction_signal=retraction_signal,
        ),
        payload,
    )


def primary_page_fallback(entry: dict[str, Any], session: requests.Session) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    response = session.get(str(entry["url"]), timeout=30)
    response.raise_for_status()
    parser = CitationMetaParser()
    parser.feed(response.text)
    meta = parser.meta
    title = (meta.get("citation_title") or [""])[0]
    date = (
        meta.get("citation_publication_date")
        or meta.get("citation_date")
        or meta.get("article:published_time")
        or [""]
    )[0]
    year_match = re.search(r"(?:19|20)\d{2}", date)
    authors = meta.get("citation_author", [])
    venue = (
        meta.get("citation_conference_title")
        or meta.get("citation_journal_title")
        or meta.get("citation_inbook_title")
        or meta.get("citation_publisher")
        or [""]
    )[0]
    doi = (meta.get("citation_doi") or [""])[0]
    page_text = response.text.lower()
    retraction_signal = any(
        marker in page_text
        for marker in (
            "citation_retraction",
            "this article has been retracted",
            "this paper has been withdrawn",
            "submission has been withdrawn",
        )
    )
    work = None
    if year_match:
        work = metadata_work(
            entry,
            identifier=f"primary:{entry['url']}",
            title=title,
            year=int(year_match.group()),
            authors=authors,
            venue=venue,
            doi=doi,
            source="primary citation metadata",
            work_type="article" if meta.get("citation_journal_title") else "proceedings-article",
            venue_type="journal" if meta.get("citation_journal_title") else "conference",
            retraction_signal=retraction_signal,
        )
    return work, {"url": str(response.url), "status_code": response.status_code, "citation_meta": meta}


def query_entry(entry: dict[str, Any]) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "VERA-reference-audit/1.0"})
    crossref_payload: dict[str, Any] = {}
    primary_payload: dict[str, Any] = {}
    selected = None
    errors: list[str] = []
    try:
        selected, crossref_payload = crossref_fallback(entry, session)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Crossref: {exc}")
    if selected is None:
        try:
            selected, primary_payload = primary_page_fallback(entry, session)
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            errors.append(f"primary page: {exc}")
    return {
        "entry": entry,
        "endpoint": str(entry["url"]),
        "meta": {},
        "results": [],
        "crossref": crossref_payload,
        "primary_page": primary_payload,
        "selected_id": selected.get("id") if selected else None,
        "selected": selected,
        "error": "" if selected else "; ".join(errors) or "no exact primary metadata match",
    }


def latex_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    replacements = {
        "\\": "\\textbackslash{}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
    }
    return "".join(replacements.get(character, character) for character in value)


def bibtex_entry(entry: dict[str, Any], work: dict[str, Any]) -> str:
    authors = [
        str(authorship.get("author", {}).get("display_name") or "")
        for authorship in work.get("authorships", [])
    ]
    authors = [latex_text(author) for author in authors if author]
    venue = latex_text(str(entry.get("venue") or source_name(work)))
    work_type = str(work.get("type") or "")
    venue_type = source_type(work)
    registered_type = str(entry.get("bibtex_type") or "")
    if registered_type:
        kind = registered_type
        venue_field = "journal" if kind == "article" else "booktitle"
    elif venue_type == "journal" or work_type == "article":
        kind = "article"
        venue_field = "journal"
    elif venue_type == "conference" or work_type in {"proceedings-article", "book-chapter"}:
        kind = "inproceedings"
        venue_field = "booktitle"
    else:
        kind = "misc"
        venue_field = "howpublished"
    fields = [
        ("title", "{" + latex_text(str(entry["title"])) + "}"),
        ("author", " and ".join(authors)),
        ("year", str(entry["year"])),
    ]
    if venue:
        fields.append((venue_field, venue))
    eprint = str(entry.get("eprint") or "")
    if eprint:
        fields.extend((("eprint", eprint), ("archivePrefix", "arXiv")))
    doi = str(work.get("doi") or "").removeprefix("https://doi.org/")
    if doi and "arxiv" not in doi.lower():
        fields.append(("doi", doi))
    fields.append(("url", str(entry["url"])))
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
    return f"@{kind}{{{entry['key']},\n{body}\n}}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = manifest.get("references", [])
    if not isinstance(entries, list) or not entries:
        raise ValueError("reference manifest is empty")
    keys = [str(entry.get("key", "")) for entry in entries]
    titles = [normalize_title(str(entry.get("title", ""))) for entry in entries]
    categories = [str(entry.get("category", "")) for entry in entries]

    records: list[dict[str, Any] | None] = [None] * len(entries)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(query_entry, entry): index for index, entry in enumerate(entries)}
        for future in as_completed(futures):
            records[futures[future]] = future.result()
    resolved = [record for record in records if record is not None]
    failures: list[str] = []
    if len(set(keys)) != len(keys):
        failures.append("citation keys are not unique")
    if len(set(titles)) != len(titles):
        failures.append("normalized titles are not unique")
    required_categories = set(manifest.get("required_categories", []))
    if set(categories) != required_categories:
        failures.append("reference categories differ from the required category set")

    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    scholarly_ids: list[str] = []
    for record in resolved:
        entry = record["entry"]
        work = record.get("selected")
        if not isinstance(work, dict):
            failures.append(f"{entry['key']}: {record.get('error') or 'not resolved'}")
            continue
        if work.get("is_retracted") is True:
            failures.append(f"{entry['key']}: selected work is retracted")
            continue
        selected.append((entry, work))
        scholarly_ids.append(str(work.get("id") or ""))
    if len(set(scholarly_ids)) != len(scholarly_ids):
        failures.append("multiple references resolved to the same scholarly work")

    minimum = int(manifest.get("minimum_verified_references", 40))
    category_counts = Counter(entry["category"] for entry, _ in selected)
    if len(selected) < minimum:
        failures.append(f"only {len(selected)} references verified; require at least {minimum}")
    for category in sorted(required_categories):
        if category_counts[category] < 3:
            failures.append(f"category {category} has fewer than three verified references")

    raw_payload = {
        "databases": ["Crossref", "primary publisher citation metadata"],
        "endpoints": [CROSSREF_URL, "registered canonical URLs"],
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "queries": resolved,
    }
    report = {
        "passed": not failures,
        "databases": ["Crossref", "primary publisher citation metadata"],
        "search_date": manifest.get("search_date"),
        "manifest_count": len(entries),
        "verified_reference_count": len(selected),
        "minimum_verified_references": minimum,
        "category_counts": dict(sorted(category_counts.items())),
        "unique_keys": len(set(keys)) == len(keys),
        "unique_scholarly_works": len(set(scholarly_ids)) == len(scholarly_ids),
        "retraction_signal_count": sum(bool(work.get("is_retracted")) for _, work in selected),
        "failures": failures,
        "raw_output": str(args.raw_output),
        "bib_output": str(args.bib),
        "records": [
            {
                "key": entry["key"],
                "category": entry["category"],
                "title": work.get("title"),
                "year": work.get("publication_year"),
                "registered_citation_year": entry["year"],
                "metadata_year_offset": int(work.get("publication_year") or -100)
                - int(entry.get("metadata_year", entry["year"])),
                "scholarly_id": work.get("id"),
                "verification_source": work.get("verification_source"),
                "doi": work.get("doi"),
                "source": source_name(work),
                "cited_by_count": work.get("cited_by_count"),
                "canonical_url": entry["url"],
            }
            for entry, work in selected
        ],
    }
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.bib.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(raw_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.bib.write_text(
        "\n\n".join(bibtex_entry(entry, work) for entry, work in selected) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "passed": report["passed"],
        "manifest_count": len(entries),
        "verified_reference_count": len(selected),
        "failure_count": len(failures),
        "report": str(args.report),
    }, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
