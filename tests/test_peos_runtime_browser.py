"""Tests for peos/runtime_browser.py (SPEC-006 Section 6/10/11).

AC-036 (timeout classification is not uniform), AC-046/AC-047 (watchdog
force-termination; bounded single re-probe for a transient error),
AC-009-012 (one fixture per catalog check kind; console/page-error
forces FAIL), using lightweight fakes for Playwright's `Browser`/`Page`
surface -- no real browser is launched (none is installed in this
environment; see SPEC-006 Section 10's human-run Chromium bootstrap
step).
"""

import time

import pytest

from peos import runtime_browser
from peos.runtime_browser import (
    ExecutionIntegrityFailure,
    WatchdogTimeout,
    classify_timeout,
    run_experiment_run_check,
    run_page_load_check,
    run_viewport_overflow_check,
    run_with_watchdog,
)
from peos.runtime_catalog import ExperimentRunParams, PageLoadParams, ViewportOverflowParams


class FakeBrowser:
    def __init__(self, connected=True):
        self._connected = connected
        self.closed = False
        self.version = "131.0.0.0-fake"

    def is_connected(self):
        return self._connected and not self.closed

    def close(self):
        self.closed = True


class FakeLocator:
    def __init__(self, exists=True, y=0.0, text="before"):
        self._exists = exists
        self._y = y
        self.text = text

    def count(self):
        return 1 if self._exists else 0

    def bounding_box(self):
        return {"y": self._y} if self._exists else None

    def text_content(self):
        if not self._exists:
            raise RuntimeError("no element")
        return self.text

    def fill(self, value):
        pass

    def click(self):
        pass

    def wait_for(self, state="visible", timeout=0):
        if not self._exists:
            raise RuntimeError("element never appeared")

    @property
    def first(self):
        return self


class FakeResponse:
    def __init__(self, ok=True, status=200):
        self.ok = ok
        self.status = status


class FakePage:
    def __init__(self, closed=False, evaluate_fn=None, locators=None, nav_response=None):
        self._closed = closed
        self._evaluate_fn = evaluate_fn or (lambda expr: True)
        self._locators = locators or {}
        self._nav_response = nav_response if nav_response is not None else FakeResponse()
        self._handlers = {}

    def is_closed(self):
        return self._closed

    def evaluate(self, expr):
        return self._evaluate_fn(expr)

    def goto(self, url, wait_until="load", timeout=0):
        return self._nav_response

    def locator(self, selector):
        return self._locators.get(selector, FakeLocator(exists=False))

    def on(self, event, handler):
        self._handlers[event] = handler

    def set_viewport_size(self, size):
        pass

    def wait_for_timeout(self, ms):
        pass

    def screenshot(self):
        return b"fake-png-bytes"


# --- run_with_watchdog -----------------------------------------------

def test_watchdog_returns_value_when_fn_completes_in_time():
    assert run_with_watchdog(lambda: 42, on_timeout=lambda: None, timeout_s=1) == 42


def test_watchdog_reraises_fn_exception():
    def boom():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        run_with_watchdog(boom, on_timeout=lambda: None, timeout_s=1)


def test_ac046_watchdog_force_terminates_on_hang():
    on_timeout_called = []

    def hang():
        time.sleep(5)
        return "too late"

    with pytest.raises(WatchdogTimeout):
        run_with_watchdog(hang, on_timeout=lambda: on_timeout_called.append(True), timeout_s=0.2)
    assert on_timeout_called == [True]


# --- classify_timeout --------------------------------------------------

def test_ac036_disconnected_browser_is_execution_integrity_failure():
    browser = FakeBrowser(connected=False)
    page = FakePage()
    classification, _ = classify_timeout(browser, page, timeout_s=1)
    assert classification == "execution_integrity_failure"


def test_ac036_closed_page_is_execution_integrity_failure():
    browser = FakeBrowser(connected=True)
    page = FakePage(closed=True)
    classification, _ = classify_timeout(browser, page, timeout_s=1)
    assert classification == "execution_integrity_failure"


def test_ac036_responsive_page_is_product_observation():
    browser = FakeBrowser(connected=True)
    page = FakePage(evaluate_fn=lambda expr: True)
    classification, detail = classify_timeout(browser, page, timeout_s=1)
    assert classification == "product_observation"
    assert "responsive" in detail


def test_ac047_transient_navigation_error_gets_one_bounded_reprobe_then_succeeds():
    calls = {"count": 0}

    def flaky_evaluate(expr):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Execution context was destroyed, most likely because of a navigation")
        return True

    browser = FakeBrowser(connected=True)
    page = FakePage(evaluate_fn=flaky_evaluate)
    classification, _ = classify_timeout(browser, page, timeout_s=1)
    assert classification == "product_observation"
    assert calls["count"] == 2


def test_ac047_second_consecutive_transient_error_escalates_to_execution_integrity_failure():
    def always_transient(expr):
        raise RuntimeError("Execution context was destroyed")

    browser = FakeBrowser(connected=True)
    page = FakePage(evaluate_fn=always_transient)
    classification, _ = classify_timeout(browser, page, timeout_s=1)
    assert classification == "execution_integrity_failure"


def test_ac046_hung_probe_itself_is_execution_integrity_failure_via_watchdog():
    def hang(expr):
        time.sleep(5)
        return True

    browser = FakeBrowser(connected=True)
    page = FakePage(evaluate_fn=hang)
    classification, _ = classify_timeout(browser, page, timeout_s=0.2)
    assert classification == "execution_integrity_failure"
    assert browser.closed is True


# --- catalog checks, one fixture per kind ------------------------------

def test_ac009_page_load_pass_when_landmarks_present_and_ordered():
    page = FakePage(locators={
        "#a": FakeLocator(exists=True, y=10),
        "#b": FakeLocator(exists=True, y=20),
    })
    check, screenshot = run_page_load_check(
        page, PageLoadParams(path="/", landmarks=("#a", "#b")),
        check_id="c1", related_ac_ids=("AC-001",), base_url="http://127.0.0.1:1234",
        browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "PASS"
    assert screenshot == b"fake-png-bytes"


def test_ac009_page_load_fail_when_landmark_missing():
    page = FakePage(locators={"#a": FakeLocator(exists=True, y=10)})
    check, _ = run_page_load_check(
        page, PageLoadParams(path="/", landmarks=("#a", "#missing")),
        check_id="c1", related_ac_ids=("AC-001",), base_url="http://127.0.0.1:1234",
        browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "FAIL"
    assert "missing" in check.observation.lower()


def test_ac009_page_load_fail_when_landmarks_out_of_order():
    page = FakePage(locators={
        "#a": FakeLocator(exists=True, y=50),
        "#b": FakeLocator(exists=True, y=10),
    })
    check, _ = run_page_load_check(
        page, PageLoadParams(path="/", landmarks=("#a", "#b")),
        check_id="c1", related_ac_ids=("AC-001",), base_url="http://127.0.0.1:1234",
        browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "FAIL"
    assert "order" in check.observation.lower()


def test_ac012_console_error_forces_fail_even_though_navigation_and_landmarks_pass():
    """A check is never marked PASS merely because its own narrow
    assertion happened to hold -- a console error during the check
    forces FAIL regardless (SPEC-006 Section 8 step 7)."""
    page = FakePage(locators={"#a": FakeLocator(exists=True, y=10)})

    class _ConsoleMsg:
        type = "error"
        text = "Uncaught TypeError"

    def goto_with_console_error(url, wait_until="load", timeout=0):
        # Fires the registered console handler mid-navigation, matching
        # real Playwright event ordering (the handler is registered
        # before goto() is called in run_page_load_check).
        page._handlers["console"](_ConsoleMsg())
        return FakeResponse()

    page.goto = goto_with_console_error
    check, _ = run_page_load_check(
        page, PageLoadParams(path="/", landmarks=("#a",)),
        check_id="c1", related_ac_ids=("AC-001",), base_url="http://127.0.0.1:1234",
        browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "FAIL"
    assert check.console_errors


def test_ac010_experiment_run_pass_when_content_changes():
    locator = FakeLocator(exists=True, text="before")

    page = FakePage(locators={
        "input[name=\"final_fraction\"], input[data-testid=\"final-fraction\"]": FakeLocator(exists=True),
        "button[type=\"submit\"], [data-testid=\"run-experiment\"]": FakeLocator(exists=True),
        "[data-testid=min-vdc]": locator,
    })

    call_count = {"n": 0}
    original_text_content = locator.text_content

    def text_content_side_effect():
        call_count["n"] += 1
        return "before" if call_count["n"] == 1 else "after"

    locator.text_content = text_content_side_effect

    check, _ = run_experiment_run_check(
        page, ExperimentRunParams(final_fraction=0.45, selector="[data-testid=min-vdc]"),
        check_id="c3", related_ac_ids=("AC-002",), browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "PASS"
    assert check.measurements["content_changed"] is True


def test_ac010_experiment_run_fail_when_content_does_not_change(monkeypatch):
    # The real check now polls (bounded by DEFAULT_CHECK_TIMEOUT_MS) for
    # the selector's content to change rather than checking once --
    # shrink the bound here so a genuinely-never-changes fixture doesn't
    # make this test take the real 15s timeout to fail.
    monkeypatch.setattr(runtime_browser, "DEFAULT_CHECK_TIMEOUT_MS", 50)
    locator = FakeLocator(exists=True, text="same")
    page = FakePage(locators={
        "input[name=\"final_fraction\"], input[data-testid=\"final-fraction\"]": FakeLocator(exists=True),
        "button[type=\"submit\"], [data-testid=\"run-experiment\"]": FakeLocator(exists=True),
        "[data-testid=min-vdc]": locator,
    })
    check, _ = run_experiment_run_check(
        page, ExperimentRunParams(final_fraction=0.45, selector="[data-testid=min-vdc]"),
        check_id="c4", related_ac_ids=("AC-002",), browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "FAIL"
    assert "did not change" in check.observation


def test_ac011_viewport_overflow_pass_when_no_overflow():
    page = FakePage(evaluate_fn=lambda expr: {"scrollWidth": 390, "clientWidth": 390})
    check, _ = run_viewport_overflow_check(
        page, ViewportOverflowParams(viewport="mobile"), check_id="c5", related_ac_ids=("AC-012",),
        browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "PASS"
    assert check.measurements["scroll_width_px"] == 390
    assert check.measurements["client_width_px"] == 390


def test_ac011_viewport_overflow_fail_when_overflow_detected():
    page = FakePage(evaluate_fn=lambda expr: {"scrollWidth": 430, "clientWidth": 390})
    check, _ = run_viewport_overflow_check(
        page, ViewportOverflowParams(viewport="mobile"), check_id="c6", related_ac_ids=("AC-012",),
        browser=FakeBrowser(), blocked_network_requests=[],
    )
    assert check.status == "FAIL"
    assert "overflow detected" in check.observation


def test_viewport_overflow_hung_evaluate_raises_execution_integrity_failure():
    def hang(expr):
        time.sleep(5)
        return {"scrollWidth": 1, "clientWidth": 1}

    page = FakePage(evaluate_fn=hang)
    with pytest.raises(ExecutionIntegrityFailure):
        run_viewport_overflow_check(
            page, ViewportOverflowParams(viewport="mobile"), check_id="c7", related_ac_ids=("AC-012",),
            browser=FakeBrowser(), blocked_network_requests=[], watchdog_timeout_s=0.2,
        )


def test_watchdog_rejects_non_main_thread_calls():
    """Codex implementation review Finding 2: the original thread-based
    watchdog was incompatible with Playwright's sync API, which requires
    every call to stay on the thread that created the session. The
    SIGALRM-based replacement only works on the main thread and must say
    so explicitly rather than silently installing a handler that could
    never fire."""
    import threading as _threading

    errors = []

    def worker():
        try:
            run_with_watchdog(lambda: 1, on_timeout=lambda: None, timeout_s=1)
        except RuntimeError as exc:
            errors.append(exc)

    t = _threading.Thread(target=worker)
    t.start()
    t.join()
    assert len(errors) == 1
    assert "main thread" in str(errors[0])


def test_watchdog_restores_previous_sigalrm_handler_after_success_and_timeout():
    """The signal handler/itimer must not leak across calls -- a prior
    handler is restored whether the call completed normally or timed
    out, so unrelated code using SIGALRM elsewhere is never disrupted."""
    import signal as _signal

    sentinel_calls = []

    def sentinel_handler(signum, frame):
        sentinel_calls.append(True)

    previous = _signal.signal(_signal.SIGALRM, sentinel_handler)
    try:
        run_with_watchdog(lambda: 1, on_timeout=lambda: None, timeout_s=1)
        assert _signal.getsignal(_signal.SIGALRM) is sentinel_handler

        with pytest.raises(WatchdogTimeout):
            run_with_watchdog(lambda: time.sleep(5), on_timeout=lambda: None, timeout_s=0.2)
        assert _signal.getsignal(_signal.SIGALRM) is sentinel_handler
    finally:
        _signal.signal(_signal.SIGALRM, previous)
