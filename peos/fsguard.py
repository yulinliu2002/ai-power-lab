"""Shared filesystem-containment primitives (SPEC-004 Requirements 19/21,
remediation Finding 3).

Both the Run Ledger (`peos/ledger.py`, `.peos/runs/<run_id>/...`) and the
Static External Context mechanism (`peos/static_context.py`, a spec-
declared artifact path) need the identical security property: a
repository-relative path must resolve beneath a fixed root directory with
no symlink at *any* path component, not merely in the final resolved
path. Rather than duplicate that logic (and risk the copies drifting
apart on exactly the property that makes both of them safe), it lives
here once.

Two different shapes of that property live in this module:

- `assert_no_symlink_components` -- a pure, read-only, point-in-time
  check (never creates, deletes, or follows a symlink) used where a
  single structural verdict right before a read is enough (the Static
  External Context mechanism only ever reads a staged artifact's bytes,
  immediately after this check, at a single path -- there is no
  multi-step directory creation/deletion sequence whose *later* steps
  could be redirected by a swap the check itself cannot see).

- `open_repo_root` / `traverse_dirs_anchored` / `create_dir_exclusive_
  anchored` -- an anchored, component-by-component walk, used by the Run
  Ledger (directory creation, every write, and retention cleanup/
  deletion). A point-in-time check followed by a *separate* later
  `open(absolute_path)` is a classic TOCTOU: the filesystem can change in
  between. These functions instead resolve `repo_root` to a trusted
  directory file descriptor exactly once, then open every component
  beneath it -- including ones they create -- `O_NOFOLLOW`, relative to
  the specific already-open parent fd the previous step returned, never
  by re-resolving any absolute or partial path string. A symlink swapped
  into any ancestor after the walk has already passed it cannot redirect
  any later step, because later steps never look that ancestor up by
  name again.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


def assert_no_symlink_components(root: Path, relative: str) -> str | None:
    """Check that `relative` (a repository-relative, slash-separated path)
    resolves to a location beneath `root` with no symlink at any
    component. Returns `None` if the path is safe, or a human-readable
    reason string if it is not -- never raises on an ordinary containment
    violation.

    A component that does not yet exist on disk is not a symlink (there is
    nothing to check), so a path that will be created later (e.g. a run
    directory not yet made) still passes this check for its not-yet-
    existing suffix -- callers that need existence are responsible for
    checking that separately.
    """
    relative_path = Path(relative)
    if relative_path.is_absolute():
        return f"path must be relative to the root, got an absolute path: {relative}"
    if ".." in relative_path.parts:
        return f"path escapes the root via '..': {relative}"

    root_resolved = root.resolve()
    candidate = root_resolved
    for part in relative_path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return f"path contains a symlink component: {candidate}"

    try:
        fully_resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return f"path could not be resolved: {candidate} ({exc})"

    try:
        fully_resolved.relative_to(root_resolved)
    except ValueError:
        return f"path resolves outside the root: {fully_resolved} (root: {root_resolved})"

    return None


_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_DIRECTORY", 0)


def _verify_is_dir_fd(fd: int) -> bool:
    try:
        return stat.S_ISDIR(os.fstat(fd).st_mode)
    except OSError:
        return False


def open_repo_root(path: Path) -> int | None:
    """Open `path` -- the repository root, supplied directly by the
    caller rather than looked up through any PEOS-managed path -- as a
    trusted anchor directory file descriptor (SPEC-004 remediation
    Finding 3). This is the *only* place any PEOS filesystem operation
    resolves an absolute path string; every path beneath the root is
    then walked component-by-component, relative to this (or a
    descendant) already-open fd, by `traverse_dirs_anchored` -- never by
    re-resolving another absolute path string later.

    Returns `None` -- never raises -- if `path` does not exist, cannot be
    opened, or is not a real directory.
    """
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return None
    if not _verify_is_dir_fd(fd):
        os.close(fd)
        return None
    return fd


def _open_or_create_dir_component(parent_fd: int, name: str, *, create: bool) -> int | None:
    """One anchored traversal step: open `name` relative to the already-
    open `parent_fd`, creating it first (relative to that same
    `parent_fd`) if `create` is True and it does not yet exist.

    The create-then-open is never split across a path-string re-lookup:
    `os.mkdir(name, dir_fd=parent_fd)` and the following
    `os.open(name, ..., dir_fd=parent_fd)` both name `parent_fd`
    directly, so a symlink swapped in at `name` between the two calls
    cannot be followed -- `O_NOFOLLOW` on the open simply refuses it.
    An already-existing `name` (the common case for `.peos`/`runs` on
    every write after the first) is tolerated when `create` is True
    (`FileExistsError` is swallowed); any other `mkdir` failure, or any
    failure of the subsequent open/verify, returns `None`.
    """
    if create:
        try:
            os.mkdir(name, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError:
            return None
    try:
        fd = os.open(name, _DIR_OPEN_FLAGS, dir_fd=parent_fd)
    except OSError:
        return None
    if not _verify_is_dir_fd(fd):
        os.close(fd)
        return None
    return fd


def traverse_dirs_anchored(anchor_fd: int, relative: str, *, create: bool) -> int | None:
    """Walk `relative` (a repository-relative, slash-separated path with
    no `..` component) component-by-component, starting from the
    already-open, trusted `anchor_fd` (SPEC-004 remediation Finding 3).

    Every component -- existing or (when `create` is True) newly
    created -- is opened with `O_NOFOLLOW` *relative to its own
    immediately preceding, already-open parent fd*, and verified via
    `fstat` to be a real directory, before the walk continues one level
    deeper using the fd that step just returned. No step ever re-resolves
    an absolute or partial path string from the filesystem root: each
    step only ever trusts the specific directory inode the previous step
    already opened. This is the property a point-in-time
    `assert_no_symlink_components` check followed by a later
    `open(absolute_path)` cannot provide -- here, there is no later
    absolute-path open for a symlink swapped in after the walk begins to
    redirect.

    Returns an open fd for the final component on success; the caller
    owns it and must close it. Returns `None` -- never raises on an
    ordinary containment/symlink violation -- if `relative` is absolute,
    escapes via `..`, or any component along the way is a symlink, is
    not a directory, or (when `create` is False) does not exist.
    """
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    current_fd = anchor_fd
    owns_current = False
    for part in relative_path.parts:
        next_fd = _open_or_create_dir_component(current_fd, part, create=create)
        if owns_current:
            os.close(current_fd)
        if next_fd is None:
            return None
        current_fd = next_fd
        owns_current = True
    return current_fd


def create_dir_exclusive_anchored(parent_fd: int, name: str) -> int:
    """Create `name` relative to the already-open, trusted `parent_fd`
    with *exclusive* creation semantics (SPEC-004 Requirement 19: a run
    directory is never reused), then open and verify it -- also relative
    to that same `parent_fd`, never a fresh path-string lookup.

    Raises `FileExistsError` if `name` already exists (the caller's
    signal to refuse reusing another run's state) or `OSError` on any
    other creation/verification failure. Never returns a file descriptor
    for anything other than a freshly-created, verified real directory.
    """
    os.mkdir(name, dir_fd=parent_fd)
    fd = os.open(name, _DIR_OPEN_FLAGS, dir_fd=parent_fd)
    if not _verify_is_dir_fd(fd):
        os.close(fd)
        raise OSError(f"newly created directory entry {name!r} is not a real directory")
    return fd


def write_all(fd: int, data: bytes) -> None:
    """`os.write(fd, data)` in a loop, accumulating its own returned byte
    count until every byte of `data` is confirmed written -- POSIX
    permits a single `os.write` call to write fewer bytes than
    requested, and a caller that ignores that (a bare, unchecked single
    call) can `fsync`+`rename` an incomplete payload over a previously
    valid file while reporting success (SPEC-007 Codex implementation
    review Finding 9, extended identically to every atomic-write caller
    in this codebase -- `peos/ledger.py` and `peos/checkpoint.py` alike).
    """
    written = 0
    while written < len(data):
        n = os.write(fd, data[written:])
        if n <= 0:
            raise OSError("write_all: os.write made no progress")
        written += n


def fsync_dir_fd(dir_fd: int) -> None:
    """`fsync` an already-open directory file descriptor (SPEC-007
    "Checkpoint Trust Boundary"/Decision 8 extension).

    `os.fsync` on a regular file's fd makes that file's own *content*
    durable; it says nothing about whether the directory *entry* (the
    name -> inode mapping a `mkdir`/`os.rename`/`os.link` into that
    directory just created or changed) itself survives a crash or power
    loss. This is the one extra call that closes that gap -- callers
    invoke it on the containing directory's fd immediately after any
    operation that changes one of its entries, whenever that entry's
    durability matters (a run directory's first creation, a checkpoint/
    ledger file's first-ever creation via `os.rename`). May raise
    `OSError` on an unexpected failure; callers decide how to treat that
    exactly like any other write failure in this module.
    """
    os.fsync(dir_fd)


def mkdir_tolerant_anchored(parent_fd: int, name: str) -> int | None:
    """Create `name` relative to the already-open, trusted `parent_fd`
    *tolerantly* (an already-existing `name` is not an error, unlike
    `create_dir_exclusive_anchored`), `fsync`ing `parent_fd` iff this call
    is the one that actually created the entry (SPEC-007: the directory-
    entry change itself must survive power loss, but only the creator
    needs to pay for that fsync -- a caller that merely finds `name`
    already present did not just change `parent_fd`'s own content).

    Returns an open, verified-directory fd for `name` on success, or
    `None` -- never raises on an ordinary creation/verification failure
    -- exactly like `traverse_dirs_anchored`'s own per-component step.
    """
    created = False
    try:
        os.mkdir(name, dir_fd=parent_fd)
        created = True
    except FileExistsError:
        pass
    except OSError:
        return None
    if created:
        try:
            fsync_dir_fd(parent_fd)
        except OSError:
            return None
    try:
        fd = os.open(name, _DIR_OPEN_FLAGS, dir_fd=parent_fd)
    except OSError:
        return None
    if not _verify_is_dir_fd(fd):
        os.close(fd)
        return None
    return fd


def stat_nofollow(parent_fd: int, name: str) -> os.stat_result | None:
    """`os.stat(name, dir_fd=parent_fd, follow_symlinks=False)`, returning
    `None` (never raising) on any `OSError` -- a uniform, fail-safe way
    for callers to inspect one entry of an already-opened, verified-safe
    directory without ever resolving `name` through a fresh, independent
    path-string lookup.
    """
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return None


def remove_tree_dir_fd(parent_fd: int, name: str) -> None:
    """Recursively remove the file or directory `name` found directly
    inside the already-opened, verified-safe directory `parent_fd`, using
    only `dir_fd`-relative syscalls from that point on (SPEC-004
    remediation Finding 3).

    Every descent opens its own child with `open_dir_nofollow`-equivalent
    semantics (`O_NOFOLLOW`, relative to the parent's own fd, never a
    fresh path-string lookup from the filesystem root), and every
    delete (`os.unlink`/`os.rmdir`) is issued with `dir_fd=` against the
    specific parent fd that was already opened -- so a symlink planted at
    any ancestor path *after* this call began cannot redirect any part of
    the walk or the deletion, unlike `shutil.rmtree`, which re-resolves
    path strings as it goes.

    Raises `OSError` on an unexpected filesystem failure (the caller
    is responsible for deciding how to report that) but never follows a
    symlink it encounters -- a symlink entry is unlinked as itself
    (never traversed into), matching ordinary `rm -rf` semantics.
    """
    entry_stat = stat_nofollow(parent_fd, name)
    if entry_stat is None:
        return
    if not stat.S_ISDIR(entry_stat.st_mode):
        os.unlink(name, dir_fd=parent_fd)
        return
    fd = os.open(name, _DIR_OPEN_FLAGS, dir_fd=parent_fd)
    try:
        for child in os.listdir(fd):
            remove_tree_dir_fd(fd, child)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent_fd)
