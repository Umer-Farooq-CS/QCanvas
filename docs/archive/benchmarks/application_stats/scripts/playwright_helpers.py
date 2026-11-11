"""
playwright_helpers.py
=====================
Browser automation and Web Vitals collection helpers for QCanvas.
Used by nb05_web_vitals.ipynb and nb06_editor_ux_latency.ipynb.

Requirements:
    pip install playwright
    playwright install chromium
"""

import time
import json
from typing import Any

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("playwright not installed – run: pip install playwright && playwright install chromium")

FRONTEND_URL = "http://localhost:3000"
DEFAULT_TIMEOUT_MS = 30_000  # 30s


# ── Web Vitals JS injection ────────────────────────────────────────────────────

# This JS snippet injects the web-vitals library and collects LCP, FCP, CLS, TBT.
# It stores results in window.__qcanvas_vitals for later polling.
_VITALS_JS = """
(function() {
  window.__qcanvas_vitals = {};

  // Performance Timing API
  function getNavTiming() {
    const t = performance.getEntriesByType('navigation')[0];
    if (!t) return {};
    return {
      dns_ms: t.domainLookupEnd - t.domainLookupStart,
      tcp_ms: t.connectEnd - t.connectStart,
      ttfb_ms: t.responseStart - t.requestStart,
      dom_content_loaded_ms: t.domContentLoadedEventEnd - t.startTime,
      load_ms: t.loadEventEnd - t.startTime,
      fcp_ms: null,
      lcp_ms: null,
      cls: 0,
    };
  }

  // FCP via PerformancePaintTiming
  function getFCP() {
    const entries = performance.getEntriesByType('paint');
    const fcp = entries.find(e => e.name === 'first-contentful-paint');
    return fcp ? fcp.startTime : null;
  }

  // LCP via PerformanceObserver
  const lcpObserver = new PerformanceObserver((list) => {
    const entries = list.getEntries();
    const last = entries[entries.length - 1];
    window.__qcanvas_vitals.lcp_ms = last.startTime;
  });
  try { lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true }); } catch(e) {}

  // CLS via PerformanceObserver
  let clsValue = 0;
  const clsObserver = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) clsValue += entry.value;
    }
    window.__qcanvas_vitals.cls = clsValue;
  });
  try { clsObserver.observe({ type: 'layout-shift', buffered: true }); } catch(e) {}

  // Collect after a short delay
  setTimeout(() => {
    const nav = getNavTiming();
    nav.fcp_ms = getFCP();
    nav.lcp_ms = window.__qcanvas_vitals.lcp_ms || getFCP();
    nav.cls = window.__qcanvas_vitals.cls || 0;
    window.__qcanvas_vitals = { ...window.__qcanvas_vitals, ...nav, ready: true };
  }, 3000);
})();
"""

_COLLECT_VITALS_JS = "return window.__qcanvas_vitals || {}"


# ── Browser lifecycle ─────────────────────────────────────────────────────────

def create_browser(headless: bool = True) -> "Browser":
    """Create and return a Playwright Chromium browser instance."""
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("playwright not installed")
    pw = sync_playwright().start()
    return pw.chromium.launch(headless=headless)


def new_context(browser: "Browser", viewport: dict | None = None) -> "BrowserContext":
    return browser.new_context(
        viewport=viewport or {"width": 1440, "height": 900},
        user_agent="QCanvas-Benchmark/1.0",
    )


# ── Web Vitals collection ─────────────────────────────────────────────────────

def collect_page_vitals(
    page: "Page",
    url: str,
    *,
    wait_ms: int = 4000,
) -> dict:
    """
    Navigate to `url`, inject the vitals collector, wait, then return metrics.
    """
    page.evaluate(_VITALS_JS) if url == "about:blank" else None

    t0 = time.perf_counter()
    page.goto(url, timeout=DEFAULT_TIMEOUT_MS, wait_until="networkidle")
    nav_latency_ms = (time.perf_counter() - t0) * 1000

    page.evaluate(_VITALS_JS)
    page.wait_for_timeout(wait_ms)

    vitals = page.evaluate(_COLLECT_VITALS_JS) or {}
    vitals["nav_latency_ms"] = nav_latency_ms
    vitals["url"] = url
    return vitals


def benchmark_pages(
    pages_to_test: list[dict] | None = None,
    *,
    headless: bool = True,
    n_runs: int = 3,
    frontend_url: str = FRONTEND_URL,
) -> list[dict]:
    """
    Measure Web Vitals for each page (label, path) n_runs times.
    Returns a flat list of result dicts.
    """
    if pages_to_test is None:
        pages_to_test = [
            {"label": "Landing Page", "path": "/"},
            {"label": "Login Page", "path": "/login"},
            {"label": "IDE (app)", "path": "/app"},
            {"label": "Examples", "path": "/examples"},
            {"label": "About", "path": "/about"},
        ]

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        for page_info in pages_to_test:
            url = f"{frontend_url}{page_info['path']}"
            for run in range(1, n_runs + 1):
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                page = ctx.new_page()
                try:
                    vitals = collect_page_vitals(page, url)
                    vitals["label"] = page_info["label"]
                    vitals["run"] = run
                    results.append(vitals)
                    print(f"  [{run}/{n_runs}] {page_info['label']}: "
                          f"LCP={vitals.get('lcp_ms', '?'):.0f}ms "
                          f"FCP={vitals.get('fcp_ms', '?'):.0f}ms "
                          f"CLS={vitals.get('cls', '?'):.4f}")
                except Exception as exc:
                    results.append({"label": page_info["label"], "run": run, "error": str(exc)})
                    print(f"  [{run}/{n_runs}] {page_info['label']}: ERROR - {exc}")
                finally:
                    ctx.close()
        browser.close()
    return results


# ── Editor UX timing ──────────────────────────────────────────────────────────

def measure_editor_compile_turnaround(
    page: "Page",
    code: str,
    *,
    framework: str = "cirq",
    compile_button_selector: str = "[data-testid='convert-btn'], button:has-text('Convert'), button:has-text('Compile')",
    result_selector: str = "[data-testid='result-pane'], .result-pane, .output-panel",
    timeout_ms: int = 30_000,
) -> dict:
    """
    Inject code into the Monaco editor, click compile, and measure turnaround.
    Returns timing dict.
    """
    # Clear and type into Monaco editor
    editor_selector = ".monaco-editor textarea, .monaco-editor .inputarea"
    try:
        page.click(editor_selector, timeout=5000)
        page.keyboard.press("Control+A")
        page.keyboard.type(code, delay=10)

        t0 = time.perf_counter()
        page.click(compile_button_selector, timeout=5000)
        page.wait_for_selector(result_selector, timeout=timeout_ms, state="visible")
        turnaround_ms = (time.perf_counter() - t0) * 1000

        return {
            "turnaround_ms": turnaround_ms,
            "code_len_chars": len(code),
            "framework": framework,
            "error": None,
        }
    except Exception as exc:
        return {
            "turnaround_ms": None,
            "code_len_chars": len(code),
            "framework": framework,
            "error": str(exc),
        }


def measure_editor_keystroke_latency(
    page: "Page",
    *,
    n_chars: int = 50,
    test_string: str = "# test typing latency benchmark\n",
) -> dict:
    """
    Type `n_chars` characters a small batch at a time and measure average
    keystroke latency via JS performance marks.
    Returns mean_latency_ms and std_latency_ms.
    """
    editor_selector = ".monaco-editor textarea, .monaco-editor .inputarea"
    latencies_ms = []

    try:
        page.click(editor_selector, timeout=5000)
        page.keyboard.press("Control+End")

        char_sequence = test_string * (n_chars // len(test_string) + 1)
        char_sequence = char_sequence[:n_chars]

        for char in char_sequence:
            t0 = time.perf_counter()
            page.keyboard.type(char)
            latencies_ms.append((time.perf_counter() - t0) * 1000)

        import statistics
        return {
            "mean_keystroke_ms": statistics.mean(latencies_ms),
            "p95_keystroke_ms": sorted(latencies_ms)[int(0.95 * len(latencies_ms))],
            "max_keystroke_ms": max(latencies_ms),
            "n_chars": n_chars,
            "error": None,
        }
    except Exception as exc:
        return {
            "mean_keystroke_ms": None,
            "p95_keystroke_ms": None,
            "max_keystroke_ms": None,
            "n_chars": n_chars,
            "error": str(exc),
        }


# ── Bundle size helper ────────────────────────────────────────────────────────

def get_js_bundle_sizes(
    page: "Page",
    url: str = FRONTEND_URL,
) -> list[dict]:
    """
    Navigate to a page and collect all JS/CSS resource sizes from
    the browser's Resource Timing API.
    """
    page.goto(url, timeout=DEFAULT_TIMEOUT_MS, wait_until="networkidle")
    entries = page.evaluate("""
        () => performance.getEntriesByType('resource')
          .filter(e => e.initiatorType === 'script' || e.initiatorType === 'link')
          .map(e => ({
            name: e.name,
            type: e.initiatorType,
            transfer_size_kb: e.transferSize / 1024,
            decoded_body_size_kb: e.decodedBodySize / 1024,
            duration_ms: e.duration
          }))
    """)
    return entries or []
