"""The desk in a browser, on the wrapper with the stand-in sidecar
(tests/dev.py, its demo data marked so in standin.py): the default layout
at 375, 582 and 1280 wide with no sideways scroll; the watchlist's price and
the chart's bars with their times; the picker pointing both at what it
picks; the blotter cut to the person's account; a panel floated and popped
out; every request to the page's own origin; with the entitlement
withdrawn, the refusal in the watchlist and the chart; and every other page
the plugin draws, the popped-out window and the Datasets tab under Manage,
at the same three widths with no sideways scroll.

Needs the front end built into web/ (open-meridian/ci/frontend.sh) and
Playwright's Chromium; skipped without them. Screenshots go to
$BROWSER_SHOTS when it is set.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).parent
WEB = HERE.parent / "web"
WIDTHS = (375, 582, 1280)
#: The width the desk is stated to work at, at the least (docs/pages.md).
MINIMUM = 375
PANELS = ("picker", "watchlist", "chart", "blotter", "positions")

playwright = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not (WEB / "index.html").is_file(), reason="the front end is not built")


def free_port() -> int:
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        return held.getsockname()[1]


def serve(entitled: bool = True, level: str = "read"):
    port = free_port()
    env = dict(
        os.environ,
        DESK_WEB=str(WEB),
        DESK_ENTITLED="1" if entitled else "0",
        DESK_ACCOUNTS="ACC-A",
        DESK_LEVEL=level,
    )
    process = subprocess.Popen([sys.executable, str(HERE / "dev.py"), str(port)], env=env)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return process, f"http://127.0.0.1:{port}"
        except OSError:
            time.sleep(0.1)
    process.kill()
    raise RuntimeError("the wrapper did not start")


def shot(page, name: str) -> None:
    shots = os.environ.get("BROWSER_SHOTS")
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=f"{shots}/{name}.png")


def sideways(page) -> tuple[int, int]:
    """The document's width and the room the window gives it, once the page
    has drawn at the window's size."""
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    wide, room = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    return wide, room


def outside(asked: list[str], base: str) -> list[str]:
    return sorted({u for u in asked if not u.startswith((base, "data:", "blob:", "about:"))})


def show(page, panel: str) -> None:
    """Brings a panel's tab to the front, where the layout tabs it."""
    tab = page.locator(".dv-tab", has_text={"picker": "Instrument"}.get(panel, panel.capitalize())).first
    tab.click()


def test_the_default_layout_at_each_width_with_no_sideways_scroll_and_no_route_out() -> None:
    process, base = serve()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 860})
                asked: list[str] = []
                page.on("request", lambda r: asked.append(r.url))
                page.goto(base + "/")
                page.wait_for_selector("[data-chart='EUR/USD'] [data-last-bar]:not([data-last-bar=''])", timeout=30_000)
                for panel in PANELS:
                    assert page.locator(".dv-tab").filter(
                        has_text={"picker": "Instrument"}.get(panel, panel.capitalize())
                    ).count() == 1, f"no {panel} tab at {width}"
                scroll, room = page.evaluate(
                    "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
                )
                assert scroll <= room, f"{scroll}px wide in {room}px at {width}"
                shot(page, f"desk-{width}")
                assert outside(asked, base) == [], outside(asked, base)
                page.close()
            browser.close()
    finally:
        process.kill()


def test_watchlist_chart_picker_and_blotter() -> None:
    process, base = serve()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            page.goto(base + "/")
            # The watchlist: the latest price with its time.
            row = page.locator("[data-panel=watchlist] tr[data-pair='EUR/USD']")
            row.locator(".price").wait_for(timeout=30_000)
            assert row.locator(".price").inner_text() == "1.1534"
            assert row.locator(".time").inner_text() == "2025-11-20T16:00:00Z"
            # The chart: bars, the last one's time and close.
            last = page.locator("[data-chart='EUR/USD'] [data-last-bar]")
            assert last.get_attribute("data-last-bar") == "2025-11-19T00:00:00Z"
            assert page.locator("[data-chart='EUR/USD'] canvas").count() > 0
            # The blotter: Pat's account's rows only, newest first.
            accounts = page.locator("[data-panel=blotter] [data-accounts]").get_attribute("data-accounts")
            assert accounts == "ACC-A"
            cells = page.locator("[data-panel=blotter] tbody tr td:nth-child(4)").all_inner_texts()
            assert cells and set(cells) == {"ACC-A"}
            assert page.locator("[data-panel=blotter] tbody tr td:nth-child(3)").first.inner_text() == "PLC-A2"
            # The picker points the watchlist and the chart at what it picks.
            page.fill("#pick", "EUR/GBP")
            page.click(".picker button[type=submit]")
            page.locator("[data-panel=picker] [data-picked='EUR/GBP']").wait_for(timeout=10_000)
            page.locator("[data-chart='EUR/GBP']").wait_for(timeout=10_000)
            assert page.locator("[data-panel=watchlist] tr[data-pair='EUR/GBP'].active").count() == 1
            # No control anywhere names an order act.
            words = " ".join(page.locator("button").all_inner_texts()).lower()
            for act in ("buy", "sell", "place", "amend", "cancel", "release", "submit order"):
                assert act not in words, act
            shot(page, "desk-picked")
            browser.close()
    finally:
        process.kill()


def test_a_panel_floats_and_pops_out_on_the_pages_own_origin() -> None:
    process, base = serve()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 860})
            page = context.new_page()
            asked: list[str] = []
            context.on("request", lambda r: asked.append(r.url))
            page.goto(base + "/")
            page.wait_for_selector("[data-panel=watchlist] .price", timeout=30_000)
            show(page, "watchlist")
            page.click("[data-action=float]")
            page.locator(".dv-resize-container [data-panel=watchlist]").wait_for(timeout=10_000)
            shot(page, "desk-floated")
            show(page, "positions")
            with context.expect_page(timeout=15_000) as opened:
                page.click("[data-action=popout]")
            popout = opened.value
            popout.wait_for_load_state()
            assert popout.url == base + "/popout.html"
            popout.locator("[data-panel=positions]").wait_for(timeout=10_000)
            csp = page.request.get(base + "/popout.html").headers["content-security-policy"]
            assert "connect-src 'self'" in csp
            page.click("[data-action=reset]")
            assert page.locator(".dv-resize-container").count() == 0
            assert outside(asked, base) == [], outside(asked, base)
            browser.close()
    finally:
        process.kill()


def test_with_the_entitlement_withdrawn_the_watchlist_and_chart_show_the_refusal() -> None:
    process, base = serve(entitled=False)
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            page.goto(base + "/")
            for panel in ("watchlist", "chart"):
                refused = page.locator(f"[data-panel={panel}] .refused").first
                refused.wait_for(timeout=30_000)
                assert "not entitled to any dataset" in refused.inner_text()
            shot(page, "desk-refused")
            browser.close()
    finally:
        process.kill()


def test_the_popped_out_window_at_each_width_with_no_sideways_scroll() -> None:
    process, base = serve()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 860})
            page = context.new_page()
            asked: list[str] = []
            context.on("request", lambda r: asked.append(r.url))
            page.goto(base + "/")
            page.wait_for_selector("[data-panel=watchlist] .price", timeout=30_000)
            show(page, "positions")
            with context.expect_page(timeout=15_000) as opened:
                page.click("[data-action=popout]")
            popout = opened.value
            popout.wait_for_load_state()
            popout.locator("[data-panel=positions]").wait_for(timeout=10_000)
            for width in WIDTHS:
                popout.set_viewport_size({"width": width, "height": 860})
                scroll, room = sideways(popout)
                assert scroll <= room, f"the popped-out window: {scroll}px wide in {room}px at {width}"
                shot(popout, f"popout-{width}")
            assert outside(asked, base) == [], outside(asked, base)
            browser.close()
    finally:
        process.kill()


def test_the_datasets_tab_under_manage_at_each_width_with_no_sideways_scroll() -> None:
    process, base = serve(level="admin")
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 860})
                asked: list[str] = []
                page.on("request", lambda r, asked=asked: asked.append(r.url))
                answer = page.goto(base + "/datasets")
                assert answer is not None and answer.status == 200
                page.get_by_role("heading", name="Datasets").wait_for(timeout=10_000)
                scroll, room = sideways(page)
                assert scroll <= room, f"Datasets: {scroll}px wide in {room}px at {width}"
                shot(page, f"datasets-{width}")
                assert outside(asked, base) == [], outside(asked, base)
                page.close()
            browser.close()
    finally:
        process.kill()
