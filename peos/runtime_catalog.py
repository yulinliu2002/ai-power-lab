"""The fixed, typed, versioned Runtime Verification check catalog
(SPEC-006 Section 10, Resolved Decision 4; hardening item A).

This module is **trusted PEOS control-plane code** (SPEC-006 Section 10
hardening item A / ADR-0003 Decision 6): it is imported by the running
orchestrator process from the authoritative checkout's own `peos/`
directory before any isolated candidate workspace exists, and the
orchestrator never re-imports or re-executes any copy of this module
from inside that workspace. The application under test (backend/frontend
source) is untrusted candidate code; the catalog that decides what a
check's parameters mean and what "PASS" requires is not, and cannot be,
by construction.

Exactly three named check kinds in V1 -- two generic
(`page_load`, `viewport_overflow`) and one AI-Power-Lab-specific
(`experiment_run`) -- each a typed parameter dataclass, never a loose
dict parsed ad hoc. There is no general scripting escape hatch: a
governing specification may only select a `kind` from `CHECK_KINDS`
below and supply that kind's own typed parameters (SPEC-006 Section 10,
"Fixed, typed V1 check catalog"). Extending the catalog is a reviewed
`peos/` code change, never a spec-authoring feature.

This module defines parameter *shapes* and the viewport-preset table
only -- the actual Playwright-driven execution of a check lives in
`peos/runtime_browser.py`, which imports the dataclasses here.
"""

from __future__ import annotations

from dataclasses import dataclass

RUNTIME_CHECK_CATALOG_VERSION = "1.0.0"

# SPEC-006 Section 9/Section 12 bounds, Codex Round 1 Finding 6: a
# Runtime Plan declaring more checks than this is rejected at Planning
# (Human Gate #12) -- never a runtime overflow the evidence bounds have
# to improvise a response to.
MAX_CHECKS_PER_ROUND = 20

CHECK_KIND_PAGE_LOAD = "page_load"
CHECK_KIND_EXPERIMENT_RUN = "experiment_run"
CHECK_KIND_VIEWPORT_OVERFLOW = "viewport_overflow"
CHECK_KINDS = (CHECK_KIND_PAGE_LOAD, CHECK_KIND_EXPERIMENT_RUN, CHECK_KIND_VIEWPORT_OVERFLOW)

# SPEC-006 Section 10 hardening item E: frozen viewport presets. An
# explicit width/height pair is also accepted (peos/runtime_plan.py);
# these two names are the only presets V1 defines.
VIEWPORT_PRESETS = {
    "desktop": (1280, 800),
    "mobile": (390, 844),
}

# SPEC-006 Section 10 hardening item E: the frozen browser-environment
# defaults applied to every launched browser context, regardless of
# which check kind runs in it.
FROZEN_DEVICE_SCALE_FACTOR = 1.0
FROZEN_LOCALE = "en-US"
FROZEN_TIMEZONE_ID = "UTC"
FROZEN_REDUCED_MOTION = "reduce"

# SPEC-006 Section 10 hardening item E: the pixel epsilon
# `viewport_overflow` allows between `scrollWidth` and `clientWidth`
# before treating it as a real overflow, to absorb ordinary
# scrollbar-width jitter across platforms -- not a loosening of the
# check's own assertion.
VIEWPORT_OVERFLOW_EPSILON_PX = 1


@dataclass(frozen=True)
class PageLoadParams:
    """`page_load` (generic). SPEC-006 Section 10 item 1."""

    path: str = "/"
    # Ordered list of CSS selectors; the check asserts each one is
    # present AND appears in this top-to-bottom reading order
    # (bounding-rect Y-position comparison).
    landmarks: tuple[str, ...] = ()


#: Default locators matching a generic HTML form convention
#: (`name="final_fraction"` / `type="submit"`). Live-run finding: the
#: real AI Power Lab frontend (`ExperimentPanel.tsx`) uses neither --
#: the control is an unlabeled `<input type="range">` and the button is
#: `type="button"` with no `data-testid`, so a real specification must
#: declare its own `control_selector`/`submit_selector` rather than rely
#: on these generic fallbacks. Named here, not silently assumed, so a
#: check against a real frontend with no stable test hooks fails with an
#: attributable "locator not found" observation instead of a misleading
#: default.
DEFAULT_EXPERIMENT_CONTROL_SELECTOR = 'input[name="final_fraction"], input[data-testid="final-fraction"]'
DEFAULT_EXPERIMENT_SUBMIT_SELECTOR = 'button[type="submit"], [data-testid="run-experiment"]'


@dataclass(frozen=True)
class ExperimentRunParams:
    """`experiment_run` (AI-Power-Lab-specific). SPEC-006 Section 10 item
    2. Never a hardcoded assumption about *what* the selector's content
    changes to -- only *that* it changes (SPEC-005 Sec 7 Constraint 4's
    "no fabricated engineering behavior" rule, carried over).

    `control_selector`/`submit_selector` locate the input control and
    the run button respectively; both default to a generic HTML-form
    convention that a real frontend without stable test hooks (e.g. no
    `data-testid` attributes) will not match -- a specification for such
    a frontend must declare its own selectors (live-run finding against
    this repository's own `ExperimentPanel.tsx`, which uses an
    unlabeled range input and a plain button).

    `expand_selector` (optional, default none): clicked once, before
    `control_selector` is located, if the control lives behind a
    collapsed disclosure section -- live-run finding against this
    repository's own frontend, where `ExperimentPanel` is not even
    present in the DOM until the "Advanced Experiment" toggle is
    clicked. Never clicked when empty; a specification for a frontend
    whose control is always visible omits it."""

    final_fraction: float = 0.0
    selector: str = ""
    control_selector: str = DEFAULT_EXPERIMENT_CONTROL_SELECTOR
    submit_selector: str = DEFAULT_EXPERIMENT_SUBMIT_SELECTOR
    expand_selector: str = ""


@dataclass(frozen=True)
class ViewportOverflowParams:
    """`viewport_overflow` (generic). SPEC-006 Section 10 item 3. Exactly
    one of `viewport` (a `VIEWPORT_PRESETS` key) or an explicit
    `width`/`height` pair is set; `peos/runtime_plan.py` enforces this
    at declaration-parse time (an invalid combination is Human Gate
    #12, never a default substitution)."""

    viewport: str | None = None
    width: int | None = None
    height: int | None = None

    def resolve_dimensions(self) -> tuple[int, int] | None:
        if self.viewport is not None:
            return VIEWPORT_PRESETS.get(self.viewport)
        if self.width is not None and self.height is not None:
            return (self.width, self.height)
        return None


CheckParams = PageLoadParams | ExperimentRunParams | ViewportOverflowParams

# Every supported `kind` -> its typed parameter dataclass, the single
# source of truth `peos/runtime_plan.py` validates declared key=value
# pairs against and `peos/runtime_browser.py` executes against.
PARAM_CLASSES: dict[str, type] = {
    CHECK_KIND_PAGE_LOAD: PageLoadParams,
    CHECK_KIND_EXPERIMENT_RUN: ExperimentRunParams,
    CHECK_KIND_VIEWPORT_OVERFLOW: ViewportOverflowParams,
}

# The required parameter field names per kind (SPEC-006 Section 10's
# declaration convention, "omitting a required parameter ... is Human
# Gate #12, never a default-substituted value"). `landmarks` is not
# required for `page_load` (an empty landmark list is a legitimate,
# if weak, declaration -- the navigation/HTTP-success assertion still
# applies); `path` defaults to `/` and is therefore not required either.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    CHECK_KIND_PAGE_LOAD: (),
    CHECK_KIND_EXPERIMENT_RUN: ("final_fraction", "selector"),
    CHECK_KIND_VIEWPORT_OVERFLOW: (),  # viewport OR width+height; checked specially
}
