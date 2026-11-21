"""The desk on a real deployment, in a headless browser.

As the deployment admin (`pat`, first_run.py), at the dashboard's own pages:
two accounts, each in an account group of its own; View on the desk for pat
on the first and for sam on the second (user groups, an access group,
permissions). plugin-ecb's dataset of reference rates is licensed and the
desk entitled to it. Then:

1. as pat, the desk's default layout renders in its area: every panel's tab;
2. the picker points the watchlist and the chart at EUR/USD, looked up in
   the deployment's master, and then at EUR/GBP. The desk's lookups read the
   master and never add to it, so a currency is found once the data plugin
   has resolved it, which it does as its first rates arrive (`pick`);
3. the watchlist shows a price with its time. The ECB publishes prices, not
   bars, so the chart says it has none, never an empty panel; the chart's
   bars are checked on the browser job's demo data;
4. the blotter names pat's account alone and shows its empty state: CI
   places no order (the populated blotter is the browser job's, on its demo
   data, and the dev deployment's);
5. a panel floats inside the area's frame; a pop-out is tried, and what the
   frame let it do is said;
6. every request the desk's frames make is to the plugin's own origin;
7. the desk, framed at 375, 582 and 1280 wide, does not scroll sideways
   (screenshots kept);
8. sam sees his own account alone, never pat's;
9. kim, who holds no level on the plugin, is refused its page;
10. the entitlement withdrawn: the refusal, not empty panels.

A dashboard copy reads the access records every 30 seconds, so a grant made
at one copy is refused at another until then. The run has two copies, and
opens the desk once each person's grant has held at the plugin's host for
that long (`in_force`).

When a check fails, it says what the browser had: a screenshot, each frame's
address and words, and the documents last answered (`tell`).

Never prints a password. Usage: python3 e2e.py RUN_DIR
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlsplit

from playwright.sync_api import Frame, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

DASHBOARD = "http://meridian.localhost"
INSTANCE = "desk"
PLUGIN = f"http://{INSTANCE}.plugins.meridian.localhost"
DATASETS = ("ecb:ecb_fx",)
RUN = Path(sys.argv[1])
SHOTS = RUN / "shots"
NOTE = "The desk's CI run"
PANELS = {"picker": "Instrument", "watchlist": "Watchlist", "chart": "Chart", "blotter": "Blotter", "positions": "Positions"}

#: How often a dashboard copy reads the access records, in seconds.
RECORDS_READ_EVERY = 30

#: How long the data plugin's first rates are waited for, in seconds: they
#: bring its currencies into the master, and the price into the lake.
FIRST_RATES = 900

#: Each document a watched page's frames were answered, oldest first.
DOCUMENTS: list[str] = []


def say(text: str) -> None:
    print(f"e2e: {text}", flush=True)


def until(what: str, seconds: float, check, every: float = 3.0):
    start = time.time()
    while time.time() - start < seconds:
        found = check()
        if found:
            say(f"{what} after {round(time.time() - start)}s")
            return found
        time.sleep(every)
    raise SystemExit(f"e2e: {what} never happened in {seconds}s")


def brief(url: str) -> str:
    """An address without its query's values: a one-time code is one."""
    parts = urlsplit(url)
    keys = ",".join(sorted({key for key, _ in parse_qsl(parts.query, keep_blank_values=True)}))
    host = f"{parts.scheme}://{parts.netloc}" if parts.netloc else ""
    return f"{host}{parts.path}" + (f"?{keys}" if keys else "")


def words(text: str, most: int = 400) -> str:
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())[:most]


def watch(page: Page) -> None:
    def answered(response) -> None:
        if response.request.resource_type == "document":
            DOCUMENTS.append(f"{response.status} {brief(response.url)}")

    page.on("response", answered)


def tell(page: Page, name: str) -> None:
    """What the browser had when a check failed."""
    try:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"failed-{name}.png"), full_page=True)
        say(f"failed: a screenshot kept as shots/failed-{name}.png")
    except Exception as failed:  # the page may be gone
        say(f"failed: no screenshot of {name}: {failed}")
    for at, frame in enumerate(page.frames):
        try:
            text = " ".join(frame.inner_text("body", timeout=2000).split())[:600]
        except Exception as failed:
            text = f"(its words could not be read: {type(failed).__name__})"
        say(f"failed: {name} frame {at} at {brief(frame.url)}: {text}")
    for line in DOCUMENTS[-16:]:
        say(f"failed: a document answered {line}")


def sign_in(page: Page, person_file: str) -> None:
    person = json.loads((RUN / person_file).read_text())
    page.goto(f"{DASHBOARD}/sign-in")
    page.fill("#name", person["name"])
    page.fill("#password", person["password"])
    with page.expect_navigation():
        page.click("button[type=submit]")


def token(page: Page, path: str) -> str:
    page.goto(f"{DASHBOARD}{path}")
    return page.get_attribute("input[name=form_token]", "value", timeout=30_000) or ""


def post(page: Page, path: str, fields, what: str) -> None:
    """A form as a browser posts it; `fields` a mapping, or pairs where a
    name repeats."""
    pairs = list(fields.items()) if isinstance(fields, dict) else list(fields)
    body = "&".join(f"{k}={_quote(v)}" for k, v in pairs)
    answer = page.request.post(
        f"{DASHBOARD}{path}",
        data=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
        max_redirects=0,
    )
    if answer.status not in (200, 302, 303):
        raise SystemExit(f"e2e: {what} answered {answer.status}: {words(answer.text())}")
    if answer.status == 200:
        say(f"{what}: 200")
        return
    where = answer.headers.get("location", "")
    landed = page.request.get(urljoin(f"{DASHBOARD}{path}", where))
    notices = re.findall(r"<p class=\"notice[^\"]*\">(.*?)</p>", landed.text(), flags=re.S)
    told = " | ".join(words(each) for each in notices) or "no notice"
    say(f"{what}: {answer.status} to {brief(where)}, which answers {landed.status}: {told}")


def _quote(value: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(value)


def minted(page: Page, name: str, section: str = "") -> str:
    """The identifier the conductor minted for a record named so, from the
    admin page's rows (as core's harness reads them)."""
    body = page.request.get(f"{DASHBOARD}/admin").text()
    if section:
        body = body.split(f"<h2>{section}</h2>", 1)[-1].split("</table>", 1)[0]
    found = re.search(r'<tr data-id="([^"]+)" data-name="' + re.escape(html.escape(name)) + '"', body)
    return found.group(1) if found else ""


def defined(page: Page, path: str, field: str, name: str, extra, section: str = "") -> str:
    found = minted(page, name, section)
    form = token(page, "/admin")
    post(page, path, [("form_token", form), (field, found), ("name", name), *extra], f"{name} defined")
    return until(f"{name} listed", 90, lambda: minted(page, name, section), every=3)


def grant(page: Page) -> dict[str, str]:
    """Two accounts; View on the desk for pat on the first, for sam on the
    second. Returns each person's account."""
    accounts = {}
    access = defined(page, "/admin/access-groups", "access_group_id", "Desk view",
                     [("entries", f"{INSTANCE} reporting read")])
    for person, letter in (("pat", "A"), ("sam", "B")):
        account = defined(page, "/admin/accounts", "account_id", f"Desk account {letter}", [], section="Accounts")
        group = defined(page, "/admin/account-groups", "account_group_id", f"Desk accounts {letter}",
                        [("account_ids", account)])
        users = defined(page, "/admin/user-groups", "user_group_id", f"Desk readers {letter}",
                        [("login", f"local|{person}")])
        form = token(page, "/admin")
        post(page, "/admin/permissions", {"form_token": form, "user_group_id": users,
                                          "account_group_id": group, "access_group_id": access},
             f"View on the desk for {person} on {account}")
        accounts[person] = account
    return accounts


def license_and_entitle(page: Page) -> None:
    for dataset in DATASETS:
        def listed():
            page.goto(f"{DASHBOARD}/admin/data-sources")
            return dataset in page.content()

        until(f"{dataset} listed on Data sources", 600, listed, every=10)
        form = token(page, "/admin/data-sources")
        post(page, "/admin/data-sources/licence", {
            "form_token": form, "dataset": dataset, "kept": "1", "retention_days": "0",
            "display": "1", "derived_use": "1", "note": NOTE,
        }, f"the licence of {dataset}")
        entitle(page, dataset, allowed=True)


def entitle(page: Page, dataset: str, allowed: bool) -> None:
    form = token(page, "/admin/data-sources")
    fields = {"form_token": form, "dataset": dataset, "instance": INSTANCE, "note": NOTE}
    if allowed:
        fields["allowed"] = "1"
    post(page, "/admin/data-sources/entitlement", fields,
         f"{'the entitlement' if allowed else 'the entitlement withdrawn'}: {INSTANCE} to {dataset}")


def in_force(page: Page, who: str) -> None:
    """The person's View on the desk, in force at every dashboard copy: the
    desk answered at the plugin's host, through the way in the area's frame
    takes, on every asking for as long as a copy goes between two reads of
    the access records."""
    held_since: list[float] = []

    def held():
        answer = page.request.get(f"{DASHBOARD}/plugins/{INSTANCE}/enter?level=read")
        if answer.status != 200 or not answer.url.startswith(PLUGIN):
            say(f"{who}'s View is not in force everywhere yet: {answer.status} at {brief(answer.url)}: "
                f"{words(answer.text(), 200)}")
            held_since.clear()
            return False
        held_since.append(time.time())
        return time.time() - held_since[0] >= RECORDS_READ_EVERY

    until(f"{who}'s View in force at the desk's host", 150, held, every=2)


def open_desk(page: Page) -> Frame:
    """The desk's area at View, its page framed, every panel's tab drawn."""

    def shown():
        page.goto(f"{DASHBOARD}/plugins/{INSTANCE}?level=read")
        return page.query_selector("iframe[data-plugin-frame]")

    until("the desk's page shown in its area", 180, shown)

    def drawn():
        frame = next((f for f in page.frames if f.url.startswith(PLUGIN)), None)
        if frame is None:
            return None
        tabs = frame.locator(".dv-tab").all_inner_texts()
        return frame if all(any(title in t for t in tabs) for title in PANELS.values()) else None

    return until("the desk's default layout, every panel's tab", 120, drawn, every=2)


def show(frame: Frame, panel: str) -> None:
    frame.locator(".dv-tab", has_text=PANELS[panel]).first.click()


def pick(frame: Frame, asked: str) -> None:
    """Look `asked` up at the picker until the master holds it. This plugin
    holds `reporting`, whose lookups read the master and add nothing to it;
    a currency is there once the data plugin has resolved it, as its first
    rates arrive. Until then the picker says the master holds nothing."""
    picked = frame.locator(f"[data-panel=picker] [data-picked='{asked}']")

    def looked():
        show(frame, "picker")
        frame.fill("#pick", asked)
        frame.click(".picker button[type=submit]")
        try:
            picked.wait_for(timeout=10_000)
        except PlaywrightTimeout:
            said = " ".join(frame.locator("[data-panel=picker]").inner_text().split())[:160]
            say(f"the picker has not found {asked} yet: {said}")
            return False
        return True

    until(f"the picker finding {asked} in the master", FIRST_RATES, looked, every=10)


def accounts_shown(frame: Frame) -> str:
    show(frame, "blotter")
    held = frame.locator("[data-panel=blotter] [data-accounts]")
    held.wait_for(timeout=30_000)
    return until("the blotter's accounts", 60, lambda: held.get_attribute("data-accounts") or None, every=2)


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        admin = browser.new_context(viewport={"width": 1280, "height": 900})
        page = admin.new_page()
        watch(page)
        try:
            checks(browser, page)
        except BaseException:
            tell(page, "pat")
            raise
        browser.close()
    say("every check held")


def checks(browser, page: Page) -> None:
    sign_in(page, "person.json")
    accounts = grant(page)
    license_and_entitle(page)
    in_force(page, "pat")

    asked: list[tuple[str, str]] = []
    page.on("request", lambda r: asked.append((r.frame.url if r.frame else "", r.url)))
    frame = open_desk(page)

    # 2. The picker, then 3. the watchlist and the chart.
    pick(frame, "EUR/USD")
    frame.locator("[data-chart='EUR/USD']").wait_for(timeout=30_000)
    row = frame.locator("[data-panel=watchlist] tr[data-pair='EUR/USD']")

    def priced():
        show(frame, "watchlist")
        price = row.locator(".price")
        return price.count() and f"{price.inner_text()} at {row.locator('.time').inner_text()}"

    say(f"the watchlist: EUR/USD {until('a price with its time', FIRST_RATES, priced, every=15)}")

    def charted():
        show(frame, "chart")
        last = frame.locator("[data-chart='EUR/USD'] [data-last-bar]")
        at = last.get_attribute("data-last-bar") if last.count() else ""
        if at:
            return f"the last bar at {at}"
        told = frame.locator("[data-panel=chart] .refused, [data-panel=chart] .empty")
        return told.count() and f"no bars, and it says so: {' '.join(told.first.inner_text().split())[:200]}"

    say(f"the chart: {until('the chart, its bars or its saying it has none', 120, charted, every=5)}")
    pick(frame, "EUR/GBP")
    frame.locator("[data-chart='EUR/GBP']").wait_for(timeout=30_000)
    if frame.locator("[data-panel=watchlist] tr[data-pair='EUR/GBP'].active").count() != 1:
        raise SystemExit("e2e: the watchlist does not follow the picker to EUR/GBP")
    say("the picker points the watchlist and the chart at EUR/USD, then at EUR/GBP")

    # 4. The blotter: pat's account alone, and its empty state.
    shown = accounts_shown(frame)
    if shown != accounts["pat"]:
        raise SystemExit(f"e2e: pat's blotter names accounts {shown!r}, not {accounts['pat']!r} alone")
    empty = frame.locator("[data-panel=blotter] .empty")
    empty.wait_for(timeout=30_000)
    say(f"pat's blotter: account {shown} alone; {empty.inner_text()}")

    # 5. Float, and pop out.
    show(frame, "positions")
    frame.click("[data-action=float]")
    frame.locator(".dv-resize-container [data-panel=positions]").wait_for(timeout=15_000)
    page.screenshot(path=str(SHOTS / "desk-floated.png"))
    say("a panel floats inside the area's frame")
    frame.click("[data-action=reset]")
    show(frame, "watchlist")
    try:
        with page.context.expect_page(timeout=10_000) as opened:
            frame.click("[data-action=popout]")
        popout = opened.value
        popout.wait_for_load_state()
        say(f"a pop-out opened at {brief(popout.url)}")
        popout.close()
    except Exception as failed:  # what the frame allows is reported, not required
        say(f"a pop-out from inside the area's frame did not open a window: {type(failed).__name__}")
    frame.click("[data-action=reset]")

    # 6. No route out.
    out = sorted({url for at, url in asked
                  if at.startswith(PLUGIN) and not url.startswith((PLUGIN, "data:", "blob:", "about:"))})
    if out:
        raise SystemExit(f"e2e: the desk's frames asked other origins: {out}")
    mine = sum(1 for at, _ in asked if at.startswith(PLUGIN))
    say(f"the desk's frames made {mine} requests, every one to {PLUGIN}")

    # 7. Widths, framed.
    for width in (375, 582, 1280):
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(3000)
        frame = next(f for f in page.frames if f.url.startswith(PLUGIN))
        wide, room = frame.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        page.screenshot(path=str(SHOTS / f"desk-{width}.png"))
        if wide > room:
            raise SystemExit(f"e2e: the desk scrolls sideways at {width}: {wide}px in {room}px")
        say(f"at {width} wide: {wide}px in {room}px, no sideways scroll")
    page.set_viewport_size({"width": 1280, "height": 900})

    # 8. Sam: his own account alone.
    sam = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    watch(sam)
    try:
        sign_in(sam, "person2.json")
        in_force(sam, "sam")
        theirs = accounts_shown(open_desk(sam))
        if theirs != accounts["sam"] or accounts["pat"] in theirs:
            raise SystemExit(f"e2e: sam's blotter names accounts {theirs!r}, not {accounts['sam']!r} alone")
        say(f"sam's blotter: account {theirs} alone, never pat's {accounts['pat']}")
    except BaseException:
        tell(sam, "sam")
        raise

    # 9. Kim, holding no level, is refused.
    kim = browser.new_context().new_page()
    sign_in(kim, "person3.json")
    answer = kim.goto(f"{DASHBOARD}/plugins/{INSTANCE}?level=read")
    if kim.query_selector("iframe[data-plugin-frame]") or (answer and answer.status < 400):
        tell(kim, "kim")
        raise SystemExit(f"e2e: kim was not refused the desk ({answer.status if answer else 'no answer'})")
    say(f"kim, holding no level, refused: {answer.status} {' '.join(kim.inner_text('body').split())[:160]}")

    # 10. The entitlement withdrawn.
    for dataset in DATASETS:
        entitle(page, dataset, allowed=False)

    def refused():
        desk = open_desk(page)
        show(desk, "watchlist")
        page.wait_for_timeout(8000)
        found = desk.locator("[data-panel=watchlist] .refused")
        return found.count() and "not entitled" in found.first.inner_text() and found.first.inner_text()

    said = until("the watchlist's refusal", 180, refused, every=5)
    page.screenshot(path=str(SHOTS / "refused.png"))
    say(f"withdrawn: {' '.join(said.split())[:200]}")

if __name__ == "__main__":
    main()
