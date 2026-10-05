"""Validates data/industry/*.yaml against the industry-record schema.

Every "verified" record must carry a real public source; every "sample"
record must NOT carry one, so sample/placeholder data can never be
mistaken for verified industry data (see CLAUDE.md's integrity rules).
"""

from __future__ import annotations

from dashboard.adapters.industry_data import VALID_MATURITY, VALID_STATUS, load_records


def test_records_load_without_error():
    records = load_records()
    assert len(records) > 0


def test_every_record_has_restricted_status_and_maturity():
    for record in load_records():
        assert record.status in VALID_STATUS
        assert record.maturity in VALID_MATURITY


def test_verified_records_carry_a_real_source():
    for record in load_records():
        if record.status == "verified":
            assert record.source_name
            assert record.source_url.startswith("http"), (
                f"{record.title}: verified record's source_url doesn't look like a real URL"
            )


def test_sample_records_carry_no_source():
    for record in load_records():
        if record.status == "sample":
            assert not record.source_name
            assert not record.source_url


def test_at_least_one_commercial_and_one_standard_record_exist():
    records = load_records()
    maturities = {r.maturity for r in records}
    assert "commercial_product" in maturities
    assert "architecture_standard" in maturities
