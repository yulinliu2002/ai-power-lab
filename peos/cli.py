"""`peos "<task>"` -- the single local PEOS entry point (SPEC-001 AC-001).

Exit codes: 0 = APPROVED, 2 = HUMAN_GATE (stopped for a human decision),
1 = FAILED (command failure / uninterpretable output) or usage error.

SPEC-001 remediation Finding 11: a directory, a missing file, an
unreadable file, or any unexpected exception while resolving `--spec` or
running the workflow must produce a normal PEOS final report describing
the failure -- never an unhandled Python traceback.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from peos.report import build_report
from peos.workflow import RunResult, run_workflow

EXIT_CODES = {"APPROVED": 0, "HUMAN_GATE": 2, "FAILED": 1}


def _canonicalize_spec(spec_arg: Path, repo_root: Path) -> tuple[Path | None, str | None]:
    """Resolve `--spec` relative to `repo_root` when it is not already
    absolute, and validate it is a readable regular file. Returns
    `(path, None)` on success or `(None, error_message)` on failure --
    never raises.
    """
    candidate = spec_arg if spec_arg.is_absolute() else (repo_root / spec_arg)
    try:
        candidate = candidate.resolve()
    except (OSError, ValueError) as exc:
        # A NUL byte (or similar) in --spec makes Path.resolve() raise
        # ValueError, not OSError -- the same class of gap already fixed
        # for --repo in main() below.
        return None, f"--spec path could not be resolved: {spec_arg} ({exc})"

    if not candidate.exists():
        return None, f"--spec path does not exist: {candidate}"
    if candidate.is_dir():
        return None, f"--spec path is a directory, not a file: {candidate}"
    if not candidate.is_file():
        return None, f"--spec path is not a regular file: {candidate}"
    try:
        candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Finding 10 (second pass): an invalid-encoding spec file raised
        # UnicodeDecodeError uncaught here (not an OSError subclass),
        # escaping as a traceback instead of a clean PEOS report.
        return None, f"--spec path is not readable as UTF-8 text: {candidate} ({exc})"
    return candidate, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="peos",
        description=(
            "PEOS Automation V1: orchestrate Claude implementation, local "
            "verification, and Codex independent review for one engineering "
            "task. Stops before merge/release (see SPEC-001)."
        ),
    )
    parser.add_argument("task", help="The engineering task to implement.")
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help=(
            "Path to the governing (Approved) specification, absolute or "
            "relative to --repo. If omitted, PEOS attempts to auto-detect a "
            "single matching approved specification under "
            "docs/specifications/ and stops for human input if it cannot do "
            "so unambiguously."
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Repository root to operate in (default: current directory).",
    )
    args = parser.parse_args(argv)

    def _report_input_failure(reason: str, report_repo_root: Path) -> int:
        """Latest Codex review, Finding 5: an invalid --repo/--spec input
        must still produce the required PEOS final report (SPEC-001
        AC-012), not a bare stderr line that bypasses reporting entirely --
        exactly the same report shape every other FAILED outcome gets.
        `report_repo_root` is a best-effort path for the report's Git
        working-tree section; peos/gitutil.py's `_run_git` degrades
        gracefully (a formatted error string, not a raised exception) if
        it does not exist or is not a Git repository.
        """
        result = RunResult(task=args.task, outcome="FAILED", gate_reason=reason)
        try:
            report = build_report(result, report_repo_root)
        except Exception as exc:  # noqa: BLE001
            print(f"error: {reason}", file=sys.stderr)
            print(f"error: the final report itself could not be built: {exc}", file=sys.stderr)
            return 1
        print(report)
        return 1

    try:
        repo_root = args.repo.resolve()
    except (OSError, ValueError) as exc:
        # Latest Codex review, Finding 5: a path containing a NUL byte
        # (or similar) makes Path.resolve() raise ValueError, not OSError
        # -- previously uncaught here entirely, escaping as a traceback
        # (the same class of gap Finding 10, first pass, already fixed for
        # _canonicalize_spec's UnicodeDecodeError).
        return _report_input_failure(f"--repo path could not be resolved: {args.repo} ({exc})", args.repo)

    if not (repo_root / ".git").exists():
        return _report_input_failure(f"{repo_root} is not a Git repository root", repo_root)

    explicit_spec: Path | None = None
    if args.spec is not None:
        explicit_spec, spec_error = _canonicalize_spec(args.spec, repo_root)
        if spec_error is not None:
            return _report_input_failure(spec_error, repo_root)

    try:
        result = run_workflow(args.task, repo_root, explicit_spec=explicit_spec)
    except Exception as exc:  # noqa: BLE001 -- Finding 11: never let an unexpected
        # exception escape as a traceback; still produce a PEOS final report.
        result = RunResult(
            task=args.task, outcome="FAILED",
            gate_reason=f"Unhandled exception while running the workflow: {exc}",
        )

    try:
        report = build_report(result, repo_root)
    except Exception as exc:  # noqa: BLE001
        print(f"error: PEOS workflow outcome was {result.outcome!r} but the final "
              f"report itself could not be built: {exc}", file=sys.stderr)
        return 1

    print(report)
    return EXIT_CODES[result.outcome]


if __name__ == "__main__":
    sys.exit(main())
