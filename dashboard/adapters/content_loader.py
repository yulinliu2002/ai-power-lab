"""Loads structured Learn-section content from content/learn/*.yaml.

No physics modeling lives here -- this module only reads and validates
the shape of curated educational content so dashboard pages can render
it consistently. Content is organized into four priority levels (see
CLAUDE.md / V1.1 scope): system architecture + controls (highest
priority), SST power-electronics architecture, system behavior
(thermal/protection), and future deep-device-physics topics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONTENT_DIR = Path("content/learn")

#: Ordered level codes -> display labels. Order here is display order.
LEVELS: dict[str, str] = {
    "1-system": "Level 1 — System Architecture + Controls",
    "2-sst-architecture": "Level 2 — SST Power-Electronics Architecture",
    "3-system-behavior": "Level 3 — System Behavior (Thermal + Protection)",
    "4-future": "Level 4 — Future Deep Dives",
}

_REQUIRED_FIELDS = ("id", "title", "level", "what_is_it", "why_it_exists")


@dataclass(frozen=True)
class Topic:
    """One Learn-section topic, following the repeatable learning template."""

    id: str
    title: str
    level: str
    what_is_it: str
    why_it_exists: str
    inputs_outputs: str = ""
    key_physics: str = ""
    key_control_idea: str = ""
    equations: list[str] = field(default_factory=list)
    what_can_go_wrong: str = ""
    how_modeled: str = ""
    what_ignored: str = ""
    industry_relevance: str = ""
    try_it_scenario: str | None = None
    source_file: str = ""


def load_topics(content_dir: Path = CONTENT_DIR) -> list[Topic]:
    """Load and validate every topic across content/learn/*.yaml.

    Raises:
        ValueError: if a topic entry is missing a required field or
            declares a level not in `LEVELS`.
    """
    topics: list[Topic] = []
    for path in sorted(content_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text()) or []
        for entry in raw:
            missing = [f for f in _REQUIRED_FIELDS if not entry.get(f)]
            if missing:
                raise ValueError(f"{path}: topic missing required field(s) {missing}: {entry}")
            if entry["level"] not in LEVELS:
                raise ValueError(f"{path}: topic {entry['id']!r} has unknown level {entry['level']!r}")
            topics.append(
                Topic(
                    id=entry["id"],
                    title=entry["title"],
                    level=entry["level"],
                    what_is_it=entry["what_is_it"],
                    why_it_exists=entry["why_it_exists"],
                    inputs_outputs=entry.get("inputs_outputs", ""),
                    key_physics=entry.get("key_physics", ""),
                    key_control_idea=entry.get("key_control_idea", ""),
                    equations=list(entry.get("equations", [])),
                    what_can_go_wrong=entry.get("what_can_go_wrong", ""),
                    how_modeled=entry.get("how_modeled", ""),
                    what_ignored=entry.get("what_ignored", ""),
                    industry_relevance=entry.get("industry_relevance", ""),
                    try_it_scenario=entry.get("try_it_scenario"),
                    source_file=path.name,
                )
            )
    return topics


def topics_by_level(content_dir: Path = CONTENT_DIR) -> dict[str, list[Topic]]:
    """Convenience grouping of `load_topics()` by level code."""
    grouped: dict[str, list[Topic]] = {level: [] for level in LEVELS}
    for topic in load_topics(content_dir):
        grouped[topic.level].append(topic)
    return grouped
