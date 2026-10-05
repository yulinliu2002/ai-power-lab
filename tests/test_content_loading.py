"""Validates content/learn/*.yaml against the Learn-topic schema."""

from __future__ import annotations

from dashboard.adapters.content_loader import LEVELS, load_topics
from dashboard.adapters.simulation_adapter import SCENARIO_KEYS


def test_topics_load_without_error():
    topics = load_topics()
    assert len(topics) > 0


def test_every_topic_has_a_known_level():
    for topic in load_topics():
        assert topic.level in LEVELS


def test_topic_ids_are_unique():
    ids = [t.id for t in load_topics()]
    assert len(ids) == len(set(ids))


def test_try_it_scenario_references_are_valid():
    for topic in load_topics():
        if topic.try_it_scenario:
            assert topic.try_it_scenario in SCENARIO_KEYS, (
                f"{topic.id}: try_it_scenario {topic.try_it_scenario!r} is not a real demo"
            )


def test_every_level_has_at_least_one_topic():
    grouped: dict[str, int] = {level: 0 for level in LEVELS}
    for topic in load_topics():
        grouped[topic.level] += 1
    for level, count in grouped.items():
        assert count > 0, f"level {level!r} has no topics"
