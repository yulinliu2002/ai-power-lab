"""Tests for repository safety preflight and governance-artifact
integrity (peos/preflight.py, SPEC-001 remediation Finding 7, Finding 4
in the second remediation pass)."""

from pathlib import Path

from peos.preflight import check_repository_safety, detect_mutations, hash_governance_artifacts

from tests._peos_fixtures import make_minimal_repo

_SPEC_REL = "docs/specifications/SPEC-001-x.md"


def test_clean_repo_passes_preflight(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    result = check_repository_safety(repo_root)
    assert result.ok
    assert result.dirty is False
    assert result.head_commit


def test_dirty_repo_is_explicitly_flagged_not_prohibited(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "CLAUDE.md").write_text("modified\n", encoding="utf-8")
    result = check_repository_safety(repo_root)
    assert result.ok
    assert result.dirty is True


def test_non_git_directory_fails_closed(tmp_path):
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    result = check_repository_safety(not_a_repo)
    assert not result.ok
    assert "not a Git repository" in result.reason


def test_interrupted_merge_fails_closed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / ".git" / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    result = check_repository_safety(repo_root)
    assert not result.ok
    assert "MERGE_HEAD" in result.reason


def test_missing_governance_file_fails_closed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "ENGINEERING.md").unlink()
    result = check_repository_safety(repo_root)
    assert not result.ok
    assert "ENGINEERING.md" in result.reason
    assert "ENGINEERING.md" in result.missing_governance_files


def test_hash_governance_artifacts_includes_spec_and_governance_files(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    hashes = hash_governance_artifacts(repo_root, spec_path, _SPEC_REL)
    assert "CLAUDE.md" in hashes
    assert "AGENTS.md" in hashes
    assert "ENGINEERING.md" in hashes
    assert _SPEC_REL in hashes


def test_hash_governance_artifacts_uses_the_given_workspace_relative_key_even_outside_repo(tmp_path):
    """Finding 4 (second pass): an explicitly-supplied spec outside
    repo_root must still be covered by hashing/mutation detection, keyed
    by wherever peos.sandbox.ensure_spec_in_workspace copied it to --
    not silently dropped because it can't be expressed relative to
    repo_root.
    """
    repo_root = make_minimal_repo(tmp_path)
    external_spec = tmp_path / "elsewhere" / "external-spec.md"
    external_spec.parent.mkdir()
    external_spec.write_text("# External\n\n**Status:** Approved\n", encoding="utf-8")

    hashes = hash_governance_artifacts(repo_root, external_spec, ".peos/governing-spec/external-spec.md")
    assert ".peos/governing-spec/external-spec.md" in hashes


def test_detect_mutations_finds_changed_file(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    baseline = hash_governance_artifacts(repo_root, spec_path, _SPEC_REL)

    (repo_root / "CLAUDE.md").write_text("mutated\n", encoding="utf-8")

    mutated = detect_mutations(baseline, repo_root)
    assert mutated == ("CLAUDE.md",)


def test_detect_mutations_finds_deleted_file(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    baseline = hash_governance_artifacts(repo_root, spec_path, _SPEC_REL)

    (repo_root / "AGENTS.md").unlink()

    mutated = detect_mutations(baseline, repo_root)
    assert "AGENTS.md" in mutated


def test_detect_mutations_empty_when_nothing_changed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    baseline = hash_governance_artifacts(repo_root, spec_path, _SPEC_REL)

    mutated = detect_mutations(baseline, repo_root)
    assert mutated == ()
