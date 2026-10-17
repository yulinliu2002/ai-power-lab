"""Tests for peos/runtime_catalog.py (SPEC-006 Section 10)."""

from peos.runtime_catalog import CHECK_KINDS, VIEWPORT_PRESETS, ViewportOverflowParams


def test_exactly_three_catalog_kinds():
    assert set(CHECK_KINDS) == {"page_load", "experiment_run", "viewport_overflow"}


def test_viewport_presets_resolve():
    params = ViewportOverflowParams(viewport="desktop")
    assert params.resolve_dimensions() == VIEWPORT_PRESETS["desktop"]


def test_explicit_dimensions_resolve():
    params = ViewportOverflowParams(width=500, height=600)
    assert params.resolve_dimensions() == (500, 600)


def test_no_dimensions_resolves_to_none():
    assert ViewportOverflowParams().resolve_dimensions() is None
