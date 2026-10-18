"""Runtime Browser: the Playwright-driven execution of the fixed V1
check catalog, the orchestrator-enforced watchdog, and the deterministic
Execution-Integrity-vs-Product-Observation classification procedure
(SPEC-006 Section 6 hardening item B, Section 8 step 6, Section 10
hardening item E, Section 11 hardening item G).

**Watchdog is signal-based, not thread-based (Codex implementation
review, round 1, Finding 2 -- corrected).** The original draft of this
module ran the liveness probe in a *separate thread* under a join-with-
timeout watchdog. That is incompatible with Playwright's **sync** API,
which is documented to require every call to stay on the single
thread/greenlet that created the `sync_playwright()` session -- calling
`page.evaluate()` from a second thread is not a slow call, it is a
*broken* one. `run_with_watchdog` is now built on POSIX `SIGALRM`
(`signal.setitimer`), which interrupts the *same* thread's blocking call
via a signal handler -- no second thread ever touches a Playwright
object. This only works from the interpreter's main thread (a POSIX
`signal.alarm`/`SIGALRM` constraint, not a Playwright one); `main()`
below -- the worker-subprocess entry point -- is exactly where this
module's only caller runs it, so that constraint is satisfied by
construction, not by caller discipline.

**Two-layer timeout defense.** The in-process `SIGALRM` watchdog gives
clean, attributable classification (which specific call hung). It is
not assumed sufficient alone: `peos/runtime_verification.py` invokes
this module's `main()` as a **subprocess**, confined by the Runtime
Verification Seatbelt profile, with its own outer wall-clock bound
(`subprocess.run(..., timeout=...)`); if the in-process watchdog itself
somehow fails to unblock a wedged call, the parent's outer timeout
forcibly kills the whole worker process group -- including Chromium, a
descendant of it -- regardless. Neither layer depends on the other
succeeding.

**Three-way liveness-probe classification.** `classify_timeout` never
collapses "the harness is fine, the page just never reached the awaited
state" and "the harness itself is dead" into one branch, and gives
exactly one bounded internal re-probe to a transient, non-fatal probe
error (e.g. "execution context was destroyed" during an in-flight
navigation) before treating it as a connection-level failure -- this
re-probe is a narrower, different thing from Resolved Decision 6's
"never retry a *completed* check": it is a single immediate re-attempt
of the *probe itself*, mid-classification of one still-in-progress
check.

**Catalog checks are written to never raise for an ordinary, anticipated
page-state outcome** (SPEC-006 Section 8 step 6) -- every expected
failure mode (missing landmark, no observed change, real overflow) is
surfaced as an ordinary `RuntimeCheck` with `status="FAIL"`, never an
uncaught exception; only a genuinely unanticipated exception (a
Playwright/transport-level error this module did not already know how to
interpret) escalates to `ExecutionIntegrityFailure`.

**Worker-subprocess protocol.** `main()` reads one JSON input file
(`{"declarations": [...], "base_url": ..., "cycle_label": ...}`,
declarations shaped as `{"declaration_index", "kind", "parameters",
"related_ac_ids"}`) and writes one JSON output file plus a sibling
`screenshots/` directory of PNG files (never base64-inlined -- keeps the
IPC payload small and avoids a second encoding step duplicating
`peos.runtime_evidence`'s own bounds). `peos/runtime_verification.py` is
the only caller and owns both temp files' lifecycle.
"""

from __future__ import annotations

import datetime
import json
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from peos.runtime_catalog import (
    DEFAULT_EXPERIMENT_CONTROL_SELECTOR,
    DEFAULT_EXPERIMENT_SUBMIT_SELECTOR,
    FROZEN_DEVICE_SCALE_FACTOR,
    FROZEN_LOCALE,
    FROZEN_REDUCED_MOTION,
    FROZEN_TIMEZONE_ID,
    RUNTIME_CHECK_CATALOG_VERSION,
    VIEWPORT_OVERFLOW_EPSILON_PX,
    ExperimentRunParams,
    PageLoadParams,
    ViewportOverflowParams,
)
from peos.runtime_evidence import RuntimeCheck, build_runtime_check

DEFAULT_WATCHDOG_TIMEOUT_S = 15.0
DEFAULT_CHECK_TIMEOUT_MS = 15000

_TRANSIENT_NAVIGATION_PHRASES = (
    "execution context was destroyed",
    "navigation",
)


class ExecutionIntegrityFailure(RuntimeError):
    """Raised when the Runtime Verification harness itself -- not the
    application under test -- fails to produce an interpretable result.
    Callers (`peos/workflow.py`) must treat this as `FAILED`, never a
    `FAIL`-status check result (SPEC-006 Section 6)."""


class WatchdogTimeout(ExecutionIntegrityFailure):
    """A blocking call exceeded its externally-enforced wall-clock
    deadline. Distinct subclass so callers can log which specific
    mechanism fired, but still an `ExecutionIntegrityFailure`."""


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_with_watchdog(fn, on_timeout, timeout_s: float = DEFAULT_WATCHDOG_TIMEOUT_S):
    """Run `fn()` under a POSIX `SIGALRM`-based wall-clock deadline, on
    the calling (main) thread -- never a second thread (see module
    docstring: Playwright's sync API cannot tolerate that). If `fn` does
    not return within `timeout_s`, the alarm's signal handler raises
    `WatchdogTimeout` *inside* `fn`'s own call stack, `on_timeout()` is
    then called (expected to force-close the browser) with the alarm
    already cancelled, and `WatchdogTimeout` propagates to the caller.
    Any other exception `fn` itself raises (within the deadline) is
    re-raised unchanged, for the caller to classify.

    Must be called from the main thread -- raises `RuntimeError`
    otherwise, rather than silently installing a signal handler that
    could never fire (`signal.signal`/`setitimer` are main-thread-only
    in CPython).
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            "run_with_watchdog must be called from the main thread (POSIX SIGALRM constraint); "
            "see peos/runtime_browser.py's main() worker entry point."
        )

    def _handler(signum, frame):
        raise WatchdogTimeout(f"operation did not complete within the {timeout_s}s watchdog bound")

    previous_handler = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        return fn()
    except WatchdogTimeout:
        signal.setitimer(signal.ITIMER_REAL, 0)  # cancel before calling on_timeout
        try:
            on_timeout()
        except Exception:  # noqa: BLE001 -- best-effort; the timeout itself is what matters
            pass
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)  # idempotent re-cancel; safety net
        signal.signal(signal.SIGALRM, previous_handler)


def _is_transient_navigation_error(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in _TRANSIENT_NAVIGATION_PHRASES)


def classify_timeout(browser, page, timeout_s: float = DEFAULT_WATCHDOG_TIMEOUT_S) -> tuple[str, str]:
    """SPEC-006 Section 6's deterministic timeout-classification
    procedure. Returns `("execution_integrity_failure" | "product_observation", detail)`.

    `browser`/`page` are the real Playwright `Browser`/`Page` objects (or
    a test fake exposing the same `is_connected()`/`is_closed()`/
    `evaluate()` surface).
    """
    for attempt in range(2):  # one bounded internal re-probe for a transient error only
        try:
            if not browser.is_connected():
                return "execution_integrity_failure", "browser is disconnected"
            if page.is_closed():
                return "execution_integrity_failure", "page is closed"
            alive = run_with_watchdog(
                lambda: page.evaluate("() => true"), on_timeout=browser.close, timeout_s=timeout_s,
            )
            if alive:
                return (
                    "product_observation",
                    "harness confirmed responsive; the awaited page condition did not become "
                    "true before the check's own deadline",
                )
            return "execution_integrity_failure", "liveness probe returned a falsy result"
        except WatchdogTimeout:
            return "execution_integrity_failure", "liveness probe itself exceeded the watchdog bound"
        except Exception as exc:  # noqa: BLE001 -- classified below, never silently swallowed
            message = str(exc)
            if attempt == 0 and _is_transient_navigation_error(message):
                continue
            return "execution_integrity_failure", f"liveness probe failed: {message}"
    return "execution_integrity_failure", "liveness probe failed after one bounded re-probe"  # pragma: no cover


class BrowserEnvironment:
    """Thin wrapper managing one frozen Playwright browser context
    (SPEC-006 Section 10 hardening item E) and its application-layer
    network interception (Section 11 hardening item G). Confined by the
    Runtime Verification Seatbelt profile only because the *process*
    this code executes in (the worker subprocess `main()` below is the
    entry point for) is itself launched under that profile by
    `peos/runtime_verification.py` -- this class does not, and cannot,
    confine Chromium on its own.
    """

    def __init__(self, playwright_module, catalog_version: str, playwright_version: str):
        self._playwright = playwright_module
        self.catalog_version = catalog_version
        self.playwright_version = playwright_version
        self.browser = None
        self.context = None
        self.browser_version = ""
        self.blocked_network_requests: list[str] = []

    def launch(self, width: int, height: int) -> None:
        self.browser = self._playwright.chromium.launch()
        self.browser_version = self.browser.version
        self.context = self.browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=FROZEN_DEVICE_SCALE_FACTOR,
            locale=FROZEN_LOCALE,
            timezone_id=FROZEN_TIMEZONE_ID,
            reduced_motion=FROZEN_REDUCED_MOTION,
            service_workers="block",
        )
        self.context.route("**/*", self._route_handler)

    def _route_handler(self, route) -> None:
        hostname = urlparse(route.request.url).hostname
        if hostname in ("127.0.0.1", "localhost"):
            route.continue_()
            return
        self.blocked_network_requests.append(route.request.url)
        route.abort()

    def new_page(self):
        return self.context.new_page()

    def verified_environment_dict(self, page) -> dict:
        """SPEC-006 Section 10 hardening item E / AC-037 (Codex
        implementation review Finding 11 -- corrected): read back what
        the browser *actually* applied, via `page.evaluate`, rather than
        restating the constants that were merely requested at context
        creation. Viewport is recorded per-check instead (checks that
        change it, like `viewport_overflow`, put the applied width/height
        in their own `measurements`), since different checks in the same
        round may use different viewports -- a single round-level
        viewport value would misrepresent whichever check did not use
        the default.
        """
        try:
            applied = page.evaluate(
                "() => ({"
                "locale: new Intl.NumberFormat().resolvedOptions().locale, "
                "timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, "
                "reduced_motion: window.matchMedia('(prefers-reduced-motion: reduce)').matches, "
                "device_pixel_ratio: window.devicePixelRatio"
                "})"
            )
        except Exception:  # noqa: BLE001 -- best-effort provenance; never fatal to the round
            applied = {}
        return {
            "locale": applied.get("locale"),
            "timezone": applied.get("timezone"),
            "reduced_motion": bool(applied.get("reduced_motion")),
            "device_pixel_ratio": applied.get("device_pixel_ratio"),
        }

    def close(self) -> None:
        if self.browser is not None:
            try:
                self.browser.close()
            except Exception:  # noqa: BLE001 -- teardown must not raise a second exception
                pass


def _collect_console_and_page_errors(page) -> tuple[list[str], list[str]]:
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if getattr(msg, "type", "") == "error" else None)
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    return console_errors, page_errors


def run_page_load_check(
    page, params: PageLoadParams, *, check_id: str, related_ac_ids: tuple[str, ...], base_url: str,
    browser, blocked_network_requests: list[str],
) -> tuple[RuntimeCheck, bytes | None]:
    """SPEC-006 Section 10 item 1. Asserts navigation success and the
    declared landmarks' presence AND top-to-bottom reading order."""
    started_at = now_iso()
    console_errors, page_errors = _collect_console_and_page_errors(page)
    url = base_url.rstrip("/") + params.path

    try:
        response = page.goto(url, wait_until="load", timeout=DEFAULT_CHECK_TIMEOUT_MS)
    except Exception as exc:  # noqa: BLE001 -- classified via the shared procedure
        classification, detail = classify_timeout(browser, page)
        if classification == "execution_integrity_failure":
            raise ExecutionIntegrityFailure(detail) from exc
        return _finish_check(
            check_id, "page_load", related_ac_ids, params.__dict__, "FAIL",
            f"navigated to {url}", detail, {}, None, console_errors, page_errors,
            blocked_network_requests, started_at,
        )

    nav_ok = response is not None and response.ok
    missing: list[str] = []
    ys: list[float] = []
    if nav_ok:
        for selector in params.landmarks:
            locator = page.locator(selector).first
            # `wait_until="load"` only waits for the initial document
            # load event -- a client-rendered page's async data fetch
            # (and the landmarks that depend on it) can still be
            # in-flight at that instant. A bounded wait here (never an
            # instantaneous `.count() == 0`) avoids a false "missing"
            # declared landmark purely from navigation/render timing --
            # live-run finding against this repository's own frontend.
            try:
                locator.wait_for(state="visible", timeout=DEFAULT_CHECK_TIMEOUT_MS)
            except Exception as exc:  # noqa: BLE001 -- classified via the shared procedure, same as page.goto above
                classification, _detail = classify_timeout(browser, page)
                if classification == "execution_integrity_failure":
                    raise ExecutionIntegrityFailure(_detail) from exc
                missing.append(selector)
                continue
            box = locator.bounding_box()
            if box is not None:
                ys.append(box["y"])
    ordering_ok = ys == sorted(ys)

    measurements = {
        "http_status": response.status if response is not None else None,
        "landmark_count": len(params.landmarks),
        "missing_landmark_count": len(missing),
        "landmark_order_ok": ordering_ok,
    }
    disqualified = bool(console_errors) or bool(page_errors)
    status = "PASS" if (nav_ok and not missing and ordering_ok and not disqualified) else "FAIL"
    if not nav_ok:
        observation = f"navigation to {url} did not succeed (http_status={measurements['http_status']})"
    elif missing:
        observation = f"missing declared landmark(s): {missing}"
    elif not ordering_ok:
        observation = "declared landmarks are present but not in the declared top-to-bottom order"
    elif disqualified:
        observation = "navigation and landmarks succeeded, but a console/page error occurred during the check"
    else:
        observation = f"navigated to {url}; all {len(params.landmarks)} declared landmark(s) present and ordered"

    screenshot_bytes = _safe_screenshot(page)
    return _finish_check(
        check_id, "page_load", related_ac_ids, params.__dict__, status,
        f"navigated to {url} and inspected declared landmarks", observation, measurements,
        screenshot_bytes, console_errors, page_errors, blocked_network_requests, started_at,
    )


def run_experiment_run_check(
    page, params: ExperimentRunParams, *, check_id: str, related_ac_ids: tuple[str, ...],
    browser, blocked_network_requests: list[str],
) -> tuple[RuntimeCheck, bytes | None]:
    """SPEC-006 Section 10 item 2. Never asserts *what* the selector's
    content changes to -- only *that* it changed (SPEC-005 Sec 7
    Constraint 4's "no fabricated engineering behavior" rule)."""
    started_at = now_iso()
    console_errors, page_errors = _collect_console_and_page_errors(page)

    before_text = _safe_text_content(page, params.selector)
    try:
        if params.expand_selector:
            page.locator(params.expand_selector).first.click()
        fraction_input = page.locator(params.control_selector).first
        fraction_input.fill(str(params.final_fraction))
        submit = page.locator(params.submit_selector).first
        submit.click()
        # Polls for the selector's text to actually *change*, not merely
        # to become visible -- the outcome element is frequently already
        # visible at the pre-run baseline (e.g. a results tile showing
        # the default scenario), so a bare `wait_for(state="visible")`
        # resolves immediately and never actually waits for the run to
        # complete. Bounded by the same check-wide deadline; a
        # `page.evaluate` liveness probe stays available to
        # `classify_timeout` below if this polling loop times out
        # without ever observing a change (live-run finding).
        deadline = time.monotonic() + (DEFAULT_CHECK_TIMEOUT_MS / 1000.0)
        content_changed = False
        while time.monotonic() < deadline:
            if _safe_text_content(page, params.selector) != before_text:
                content_changed = True
                break
            page.wait_for_timeout(200)
        if not content_changed:
            # The polling loop above already proved the harness stayed
            # responsive throughout (every iteration round-tripped a
            # real `text_content()` call) -- a fresh `classify_timeout`
            # liveness re-probe would be redundant, and the specific
            # "content did not change" reason is more attributable than
            # its generic product-observation phrasing.
            return _finish_check(
                check_id, "experiment_run", related_ac_ids, params.__dict__, "FAIL",
                f"attempted experiment run with final_fraction={params.final_fraction}",
                f"selector {params.selector!r} content did not change within {DEFAULT_CHECK_TIMEOUT_MS}ms",
                {}, None, console_errors, page_errors, blocked_network_requests, started_at,
            )
    except Exception as exc:  # noqa: BLE001
        classification, detail = classify_timeout(browser, page)
        if classification == "execution_integrity_failure":
            raise ExecutionIntegrityFailure(detail) from exc
        return _finish_check(
            check_id, "experiment_run", related_ac_ids, params.__dict__, "FAIL",
            f"attempted experiment run with final_fraction={params.final_fraction}", detail,
            {}, None, console_errors, page_errors, blocked_network_requests, started_at,
        )

    after_text = _safe_text_content(page, params.selector)
    changed = before_text is not None and after_text is not None and before_text != after_text
    disqualified = bool(console_errors) or bool(page_errors)
    status = "PASS" if (changed and not disqualified) else "FAIL"
    if not changed:
        observation = f"selector {params.selector!r} content did not change after the experiment run"
    elif disqualified:
        observation = "selector content changed, but a console/page error occurred during the check"
    else:
        observation = f"selector {params.selector!r} content changed after the experiment run"

    screenshot_bytes = _safe_screenshot(page)
    return _finish_check(
        check_id, "experiment_run", related_ac_ids, params.__dict__, status,
        f"set final_fraction={params.final_fraction} and submitted the experiment", observation,
        {"content_changed": changed}, screenshot_bytes, console_errors, page_errors,
        blocked_network_requests, started_at,
    )


def run_viewport_overflow_check(
    page, params: ViewportOverflowParams, *, check_id: str, related_ac_ids: tuple[str, ...],
    browser, blocked_network_requests: list[str], watchdog_timeout_s: float = DEFAULT_WATCHDOG_TIMEOUT_S,
) -> tuple[RuntimeCheck, bytes | None]:
    """SPEC-006 Section 10 item 3. Scope: document-level horizontal
    overflow only (Codex Round 1 Finding 11) -- never a "clipped text"
    claim. The assertion is structured (`scrollWidth`/`clientWidth`),
    never a screenshot/pixel inspection (hardening item E)."""
    started_at = now_iso()
    console_errors, page_errors = _collect_console_and_page_errors(page)

    dimensions = params.resolve_dimensions()
    try:
        if dimensions is not None:
            page.set_viewport_size({"width": dimensions[0], "height": dimensions[1]})
        result = run_with_watchdog(
            lambda: page.evaluate(
                "() => ({scrollWidth: document.documentElement.scrollWidth, "
                "clientWidth: document.documentElement.clientWidth})"
            ),
            on_timeout=browser.close, timeout_s=watchdog_timeout_s,
        )
    except WatchdogTimeout as exc:
        raise ExecutionIntegrityFailure(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        classification, detail = classify_timeout(browser, page, timeout_s=watchdog_timeout_s)
        if classification == "execution_integrity_failure":
            raise ExecutionIntegrityFailure(detail) from exc
        return _finish_check(
            check_id, "viewport_overflow", related_ac_ids, params.__dict__, "FAIL",
            "measured document-level scrollWidth/clientWidth", detail, {}, None,
            console_errors, page_errors, blocked_network_requests, started_at,
        )

    scroll_width = result["scrollWidth"]
    client_width = result["clientWidth"]
    overflow = (scroll_width - client_width) > VIEWPORT_OVERFLOW_EPSILON_PX
    disqualified = bool(console_errors) or bool(page_errors)
    status = "PASS" if (not overflow and not disqualified) else "FAIL"
    if overflow:
        observation = f"horizontal overflow detected: scrollWidth={scroll_width} > clientWidth={client_width}"
    elif disqualified:
        observation = "no horizontal overflow, but a console/page error occurred during the check"
    else:
        observation = f"no horizontal overflow: scrollWidth={scroll_width} <= clientWidth={client_width}"

    measurements = {"scroll_width_px": scroll_width, "client_width_px": client_width}
    if dimensions is not None:
        # Codex implementation review Finding 11: record the viewport
        # actually applied to *this* check, since checks in the same
        # round may each request a different one.
        try:
            applied_size = page.viewport_size
        except Exception:  # noqa: BLE001
            applied_size = None
        measurements["applied_viewport_width_px"] = applied_size["width"] if applied_size else dimensions[0]
        measurements["applied_viewport_height_px"] = applied_size["height"] if applied_size else dimensions[1]

    screenshot_bytes = _safe_screenshot(page)
    return _finish_check(
        check_id, "viewport_overflow", related_ac_ids, params.__dict__, status,
        "measured document-level scrollWidth/clientWidth", observation,
        measurements, screenshot_bytes, console_errors, page_errors, blocked_network_requests, started_at,
    )


def _safe_text_content(page, selector: str) -> str | None:
    try:
        return page.locator(selector).first.text_content()
    except Exception:  # noqa: BLE001 -- a missing selector is evidence (None), not a crash
        return None


def _safe_screenshot(page) -> bytes | None:
    try:
        return page.screenshot()
    except Exception:  # noqa: BLE001 -- a screenshot is corroborating only; its absence must not crash the check
        return None


def _finish_check(
    check_id, kind, related_ac_ids, parameters, status, action_performed, observation,
    measurements, screenshot_bytes, console_errors, page_errors, blocked_network_requests, started_at,
) -> tuple[RuntimeCheck, bytes | None]:
    """Returns `(check, screenshot_bytes_to_persist_or_None)` -- the
    caller (the per-round driving loop) collects these into the
    `screenshots` dict `peos.runtime_evidence.persist_evidence` expects,
    keyed by `check.check_id`."""
    return build_runtime_check(
        check_id=check_id, kind=kind, related_ac_ids=related_ac_ids, parameters=parameters,
        status=status, action_performed=action_performed, observation=observation,
        measurements=measurements, screenshot_bytes=screenshot_bytes,
        console_errors=tuple(console_errors), page_errors=tuple(page_errors),
        blocked_network_requests=tuple(blocked_network_requests),
        started_at=started_at, finished_at=now_iso(),
    )


def _not_executed_check(check_id: str, kind: str, related_ac_ids: tuple[str, ...], parameters: dict) -> RuntimeCheck:
    check, _ = build_runtime_check(
        check_id=check_id, kind=kind, related_ac_ids=related_ac_ids, parameters=parameters,
        status="NOT_EXECUTED", action_performed="(not executed)",
        observation="an earlier check's execution-integrity failure aborted the round before this check ran",
        measurements={}, screenshot_bytes=None,
    )
    return check


_DEFAULT_LAUNCH_WIDTH = 1280
_DEFAULT_LAUNCH_HEIGHT = 800


@dataclass
class RuntimeExecutionResult:
    checks: tuple
    screenshots: dict
    execution_integrity_passed: bool
    failure_reason: str | None
    browser_version: str
    playwright_version: str
    browser_environment: dict


def _check_id(cycle_slug: str, declaration) -> str:
    return f"runtime.{cycle_slug}.{declaration.declaration_index}.{declaration.kind}"


def _playwright_package_version() -> str:
    """`playwright.sync_api` exports no `__version__` (Codex
    implementation review Finding 1) -- the installed-distribution
    version is the correct, documented way to read it."""
    import importlib.metadata

    try:
        return importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover -- preflight already checked this
        return "unknown"


def execute_runtime_plan(declarations: tuple, base_url: str, cycle_label: str) -> "RuntimeExecutionResult":
    """Run every declared check against `base_url`, in declared order,
    in one browser context (SPEC-006 Section 8 steps 6-7), **on the
    calling thread** (must be the main thread -- see `run_with_watchdog`).
    This is the function `main()` below calls from inside the worker
    subprocess; it is not itself safe to call in-process in the
    orchestrator, because the orchestrator's main thread is busy running
    the rest of `peos/workflow.py` -- see `peos/runtime_verification.py`.

    On the first `ExecutionIntegrityFailure` from any individual check,
    that check and every remaining declared check are recorded with
    `status="NOT_EXECUTED"` (never silently absent from the evidence,
    SPEC-006 Section 8 step 7) and
    `RuntimeExecutionResult.execution_integrity_passed` is `False`.
    """
    from playwright.sync_api import sync_playwright

    playwright_version = _playwright_package_version()
    cycle_slug = cycle_label.strip().lower().replace(" ", "-")
    checks: list = []
    screenshots: dict = {}

    with sync_playwright() as p:
        env = BrowserEnvironment(p, RUNTIME_CHECK_CATALOG_VERSION, playwright_version)
        try:
            env.launch(_DEFAULT_LAUNCH_WIDTH, _DEFAULT_LAUNCH_HEIGHT)
        except Exception as exc:  # noqa: BLE001 -- browser launch failure is execution-integrity
            return RuntimeExecutionResult(
                checks=tuple(
                    _not_executed_check(_check_id(cycle_slug, d), d.kind, d.related_ac_ids, d.params.__dict__)
                    for d in declarations
                ),
                screenshots={}, execution_integrity_passed=False,
                failure_reason=f"browser launch failed: {exc}", browser_version="",
                playwright_version=playwright_version, browser_environment={},
            )

        browser_environment: dict = {}
        try:
            for index, declaration in enumerate(declarations):
                check_id = _check_id(cycle_slug, declaration)
                try:
                    page = env.new_page()
                    try:
                        if not browser_environment:
                            browser_environment = env.verified_environment_dict(page)
                        if declaration.kind == "page_load":
                            check, screenshot = run_page_load_check(
                                page, declaration.params, check_id=check_id,
                                related_ac_ids=declaration.related_ac_ids, base_url=base_url,
                                browser=env.browser, blocked_network_requests=env.blocked_network_requests,
                            )
                        elif declaration.kind == "experiment_run":
                            page.goto(base_url, wait_until="load")
                            check, screenshot = run_experiment_run_check(
                                page, declaration.params, check_id=check_id,
                                related_ac_ids=declaration.related_ac_ids,
                                browser=env.browser, blocked_network_requests=env.blocked_network_requests,
                            )
                        elif declaration.kind == "viewport_overflow":
                            page.goto(base_url, wait_until="load")
                            check, screenshot = run_viewport_overflow_check(
                                page, declaration.params, check_id=check_id,
                                related_ac_ids=declaration.related_ac_ids,
                                browser=env.browser, blocked_network_requests=env.blocked_network_requests,
                            )
                        else:  # pragma: no cover -- peos/runtime_plan.py already rejects unknown kinds
                            raise ExecutionIntegrityFailure(f"unsupported kind reached the browser driver: {declaration.kind!r}")
                        checks.append(check)
                        if screenshot is not None:
                            screenshots[check_id] = screenshot
                    finally:
                        try:
                            page.close()
                        except Exception:  # noqa: BLE001
                            pass
                except ExecutionIntegrityFailure as exc:
                    for not_run in declarations[index:]:
                        checks.append(
                            _not_executed_check(
                                _check_id(cycle_slug, not_run), not_run.kind, not_run.related_ac_ids,
                                not_run.params.__dict__,
                            )
                        )
                    return RuntimeExecutionResult(
                        checks=tuple(checks), screenshots=screenshots, execution_integrity_passed=False,
                        failure_reason=str(exc), browser_version=env.browser_version,
                        playwright_version=playwright_version, browser_environment=browser_environment,
                    )
        finally:
            env.close()

    return RuntimeExecutionResult(
        checks=tuple(checks), screenshots=screenshots, execution_integrity_passed=True, failure_reason=None,
        browser_version=env.browser_version, playwright_version=playwright_version,
        browser_environment=browser_environment,
    )


# --- Worker-subprocess entry point -------------------------------------
#
# peos/runtime_verification.py invokes `python -m peos.runtime_browser
# <input.json> <output_dir>` as a Seatbelt-sandboxed subprocess (SPEC-006
# Section 11) with its own outer wall-clock bound -- see the module
# docstring's "two-layer timeout defense". This is the one place in the
# codebase `execute_runtime_plan` is actually called from the main
# thread of a fresh process, satisfying `run_with_watchdog`'s requirement
# by construction.

def _declaration_from_dict(d: dict):
    from peos.runtime_plan import RuntimeCheckDeclaration

    kind = d["kind"]
    raw_params = d.get("parameters", {})
    if kind == "page_load":
        params = PageLoadParams(path=raw_params.get("path", "/"), landmarks=tuple(raw_params.get("landmarks", ())))
    elif kind == "experiment_run":
        # Pass every field through (not just final_fraction/selector) --
        # the parent always serializes the dataclass's full `__dict__`
        # (see `peos/runtime_verification.py`'s `_run_browser_worker`),
        # so dropping control_selector/submit_selector/expand_selector
        # here silently discarded a real specification's declared
        # locators in favor of the (generic, frontend-mismatched)
        # dataclass defaults -- live-run finding.
        params = ExperimentRunParams(
            final_fraction=raw_params["final_fraction"], selector=raw_params["selector"],
            control_selector=raw_params.get("control_selector", DEFAULT_EXPERIMENT_CONTROL_SELECTOR),
            submit_selector=raw_params.get("submit_selector", DEFAULT_EXPERIMENT_SUBMIT_SELECTOR),
            expand_selector=raw_params.get("expand_selector", ""),
        )
    elif kind == "viewport_overflow":
        params = ViewportOverflowParams(
            viewport=raw_params.get("viewport"), width=raw_params.get("width"), height=raw_params.get("height"),
        )
    else:  # pragma: no cover -- the parent only ever serializes already-validated declarations
        raise ValueError(f"unsupported kind in worker input: {kind!r}")
    return RuntimeCheckDeclaration(
        declaration_index=d["declaration_index"], kind=kind, params=params,
        related_ac_ids=tuple(d.get("related_ac_ids", ())),
    )


def _serialize_check_for_worker_output(check: RuntimeCheck) -> dict:
    return {
        "check_id": check.check_id, "kind": check.kind, "catalog_version": check.catalog_version,
        "related_ac_ids": list(check.related_ac_ids), "parameters": check.parameters,
        "status": check.status, "action_performed": check.action_performed, "observation": check.observation,
        "measurements": check.measurements, "screenshot_filename": (
            f"{check.check_id}.png" if check.screenshot_path is not None else None
        ),
        "console_errors": list(check.console_errors), "page_errors": list(check.page_errors),
        "blocked_network_requests": list(check.blocked_network_requests),
        "truncated": check.truncated, "omitted_reason": check.omitted_reason,
        "started_at": check.started_at, "finished_at": check.finished_at,
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print("usage: python -m peos.runtime_browser <input.json> <output_dir>", file=sys.stderr)
        return 2
    input_path, output_dir = Path(argv[0]), Path(argv[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = output_dir / "screenshots"

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    declarations = tuple(_declaration_from_dict(d) for d in payload["declarations"])

    try:
        result = execute_runtime_plan(declarations, payload["base_url"], payload["cycle_label"])
    except Exception as exc:  # noqa: BLE001 -- never a bare traceback; the parent reads structured output only
        (output_dir / "result.json").write_text(
            json.dumps({
                "ok": False, "failure_reason": f"worker raised an unanticipated exception: {exc}",
            }),
            encoding="utf-8",
        )
        return 1

    screenshots_dir.mkdir(exist_ok=True)
    for check_id, raw_bytes in result.screenshots.items():
        (screenshots_dir / f"{check_id}.png").write_bytes(raw_bytes)

    output_payload = {
        "ok": True,
        "checks": [_serialize_check_for_worker_output(c) for c in result.checks],
        "execution_integrity_passed": result.execution_integrity_passed,
        "failure_reason": result.failure_reason,
        "browser_version": result.browser_version,
        "playwright_version": result.playwright_version,
        "browser_environment": result.browser_environment,
    }
    (output_dir / "result.json").write_text(json.dumps(output_payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
