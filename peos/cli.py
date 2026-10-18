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

from peos.plan import MAX_MAX_CYCLES, MIN_MAX_CYCLES
from peos.report import build_report
from peos.resume import abandon_run, inspect_run, resume_run
from peos.workflow import RunResult, run_workflow

EXIT_CODES = {
    "APPROVED": 0, "HUMAN_GATE": 2, "FAILED": 1, "MAX_CYCLES_REACHED": 1, "ABANDONED": 0,
    "PAUSED_RETRYABLE": 1,
}

# SPEC-007 "CLI / UX": the minimal V1 resume surface -- `resume`,
# `inspect`, `abandon` -- reserved as literal first-token subcommands,
# distinct from an ordinary `peos "<task>"` invocation. `./bin/peos runs`
# is explicitly not built in V1 (Decision 1).
_RESUME_SUBCOMMANDS = ("resume", "inspect", "abandon")


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


def _run_resume_subcommand(subcommand: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"peos {subcommand}")
    parser.add_argument("run_id", help="The run_id of a previously interrupted PEOS run.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root (default: current directory).")
    args = parser.parse_args(argv)

    try:
        repo_root = args.repo.resolve()
    except (OSError, ValueError) as exc:
        print(f"error: --repo path could not be resolved: {args.repo} ({exc})", file=sys.stderr)
        return 1
    if not (repo_root / ".git").exists():
        print(f"error: {repo_root} is not a Git repository root", file=sys.stderr)
        return 1

    if subcommand == "inspect":
        result = inspect_run(repo_root, args.run_id)
        if not result.found:
            print(f"No such run: {args.run_id}" + (f" ({result.error})" if result.error else ""), file=sys.stderr)
            return 1
        cp = result.checkpoint
        print(f"run_id: {cp.run_id}")
        print(f"task: {cp.task}")
        print(f"active_phase: {cp.active_phase} ({cp.active_phase_state})")
        print(f"last_safely_completed_phase: {cp.last_safely_completed_phase}")
        print(f"current_cycle: {cp.current_cycle} / {cp.effective_max_cycles}")
        if cp.terminal_outcome is not None:
            print(f"terminal_outcome: {cp.terminal_outcome}")
            if cp.terminal_gate_id is not None:
                print(f"gate_id: {cp.terminal_gate_id}")
            if cp.terminal_gate_reason is not None:
                print(f"gate_reason: {cp.terminal_gate_reason}")
        else:
            print("status: PAUSED_RETRYABLE (non-terminal -- resumable via `peos resume`, or `peos abandon`)")
        return 0

    if subcommand == "abandon":
        result = abandon_run(repo_root, args.run_id)
        if not result.ok:
            print(f"error: could not abandon run {args.run_id}: {result.reason}", file=sys.stderr)
            return 1
        print(f"Run {args.run_id} abandoned.")
        return 0

    # subcommand == "resume"
    result = resume_run(repo_root, args.run_id)
    try:
        report = build_report(result, repo_root)
    except Exception as exc:  # noqa: BLE001
        print(f"error: PEOS resume outcome was {result.outcome!r} but the final "
              f"report itself could not be built: {exc}", file=sys.stderr)
        return 1
    print(report)
    return EXIT_CODES.get(result.outcome, 1)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in _RESUME_SUBCOMMANDS:
        return _run_resume_subcommand(argv[0], argv[1:])

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
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help=(
            f"Maximum number of bounded remediation cycles ({MIN_MAX_CYCLES}-{MAX_MAX_CYCLES}, "
            "SPEC-004 Requirement 6). Counts remediation cycles only, never the fixed cycle-0 "
            "initial implementation/review. Omitting this uses the V2 default of 3 -- a "
            "deliberate behavior change from V1's effective 1; pass --max-cycles 1 to "
            "reproduce SPEC-001/SPEC-003's exact one-remediation-cycle behavior."
        ),
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

    # SPEC-004 Requirement 6/AC-4: an out-of-range --max-cycles is a hard
    # input-validation failure, reported the same shape as an invalid
    # --repo/--spec -- never a traceback, never a silently clamped value.
    if args.max_cycles is not None and not (MIN_MAX_CYCLES <= args.max_cycles <= MAX_MAX_CYCLES):
        return _report_input_failure(
            f"--max-cycles must be between {MIN_MAX_CYCLES} and {MAX_MAX_CYCLES} "
            f"(inclusive), got {args.max_cycles}.",
            repo_root,
        )

    explicit_spec: Path | None = None
    if args.spec is not None:
        explicit_spec, spec_error = _canonicalize_spec(args.spec, repo_root)
        if spec_error is not None:
            return _report_input_failure(spec_error, repo_root)

    try:
        result = run_workflow(args.task, repo_root, explicit_spec=explicit_spec, max_cycles=args.max_cycles)
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
