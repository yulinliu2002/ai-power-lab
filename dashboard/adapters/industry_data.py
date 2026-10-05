"""Loads and validates curated public industry-intelligence records.

Reads a local, curated YAML knowledge base under data/industry/ -- no
web scraping, no live fetching, no automatic browsing (see CLAUDE.md
and the V1.1 scope note on this). External research and verification
happen separately; this module only loads and validates what has
already been curated into the dataset.

Every record must carry a `maturity` label distinguishing a verified
commercial product from an industry architecture/standard from
research -- the Industry dashboard page uses this to visually
separate the three, per CLAUDE.md's engineering-honesty rules. Every
record also carries a `status`: "verified" records must cite a real
public source; "sample" records are explicitly illustrative
placeholders (e.g. demonstrating the weekly-update schema before real
weekly updates exist) and must NOT carry a source, so they can never
be mistaken for a verified record.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DATA_DIR = Path("data/industry")

#: How mature/real the thing being described is -- kept distinct from
#: `category` (product/architecture/deployment/standard/research/...)
#: so the UI can always tell a shipping product apart from a standards
#: workstream apart from academic research, per CLAUDE.md engineering
#: honesty rules.
VALID_MATURITY = frozenset({"commercial_product", "architecture_standard", "research"})

#: "verified" = a real, sourced public record. "sample" = an
#: illustrative placeholder with no real source (see module docstring).
VALID_STATUS = frozenset({"verified", "sample"})

_ALWAYS_REQUIRED = (
    "date",
    "organization",
    "category",
    "title",
    "summary",
    "technology_area",
    "status",
    "maturity",
)


@dataclass(frozen=True)
class IndustryRecord:
    date: str
    organization: str
    category: str
    title: str
    summary: str
    technology_area: str
    status: str
    maturity: str
    relevance_to_sst: str = ""
    relevance_to_ai_data_centers: str = ""
    source_name: str = ""
    source_url: str = ""
    verified_date: str = ""
    source_file: str = ""


def load_records(data_dir: Path = DATA_DIR) -> list[IndustryRecord]:
    """Load and validate every record across data/industry/*.yaml.

    Raises:
        ValueError: if a record is missing a required field, declares
            an unrecognized status/maturity, or is a "verified" record
            with no source attribution.
    """
    records: list[IndustryRecord] = []
    for path in sorted(data_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text()) or []
        for entry in raw:
            missing = [f for f in _ALWAYS_REQUIRED if not entry.get(f)]
            if missing:
                raise ValueError(f"{path}: record missing required field(s) {missing}: {entry}")

            status = entry["status"]
            maturity = entry["maturity"]
            if status not in VALID_STATUS:
                raise ValueError(f"{path}: record {entry['title']!r} has invalid status {status!r}")
            if maturity not in VALID_MATURITY:
                raise ValueError(f"{path}: record {entry['title']!r} has invalid maturity {maturity!r}")

            source_name = entry.get("source_name", "")
            source_url = entry.get("source_url", "")
            if status == "verified" and not (source_name and source_url):
                raise ValueError(
                    f"{path}: verified record {entry['title']!r} must carry source_name and source_url"
                )
            if status == "sample" and (source_name or source_url):
                raise ValueError(
                    f"{path}: sample record {entry['title']!r} must NOT carry a real source "
                    "(it would be mistakable for a verified record)"
                )

            records.append(
                IndustryRecord(
                    date=entry["date"],
                    organization=entry["organization"],
                    category=entry["category"],
                    title=entry["title"],
                    summary=entry["summary"],
                    technology_area=entry["technology_area"],
                    status=status,
                    maturity=maturity,
                    relevance_to_sst=entry.get("relevance_to_sst", ""),
                    relevance_to_ai_data_centers=entry.get("relevance_to_ai_data_centers", ""),
                    source_name=source_name,
                    source_url=source_url,
                    verified_date=entry.get("verified_date", ""),
                    source_file=path.name,
                )
            )
    return records


MATURITY_LABELS: dict[str, str] = {
    "commercial_product": "Commercial Product",
    "architecture_standard": "Industry Architecture / Standard",
    "research": "Research",
}
