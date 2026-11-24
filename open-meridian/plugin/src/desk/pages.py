"""The plugin's page: the desk, and the read routes its panels call.

Two tabs are declared, as every page is:

- **Desk** (`/`), under Open and View: the docking layout of panels, built
  into `/plugin/web` (open-meridian/ci/frontend.sh). Its files and its read
  routes (`/api/...`) are served under the same levels by `dispatch` below,
  since the SDK's pages declare exact paths.
- **Datasets** (`/datasets`), under Manage: the reporting role's common page,
  each dataset the plugin reads and whether it is entitled to it.

Each read the desk shows is also a read tool on the deployment's MCP surface,
under the same levels (Open and View), at `/tools/...`: `read_blotter`,
`read_positions`, `read_instrument` (the picker), `read_latest_price` (the
watchlist), `read_bar_lengths` and `read_bars` (the chart). Each reads what
its panel reads, through the same role class, cut to the same accounts, and
is refused as its panel is.

Who is asking is the `Meridian-Caller` header the sidecar forwarded, every
time; nothing here sets a cookie or keeps a session. Every route reads:
nothing here takes a change, and a method but GET and HEAD is refused. The
plugin holds `reporting` alone, so its sidecar would refuse an order act
whatever was sent.

Every answer carries the Content-Security-Policy: the page reaches only its
own origin (`connect-src 'self'`), and loads images and fonts only from it
or inline.
"""

from __future__ import annotations

import json
import logging
import mimetypes
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import meridian
from meridian.roles import reporting
from meridian.v1 import sidecar_pb2

from .book import (
    INTERVALS,
    BadToken,
    Bar,
    Book,
    Holding,
    Pair,
    Refused,
    Row,
    blotter_rows,
    holdings,
    readable,
    token_of,
    watermark_of,
)

log = logging.getLogger("desk")

TITLE = "Desk"

#: Where the desk's built files are: the image's `/plugin/web`.
WEB = Path("/plugin/web")

#: The levels the desk is served under: Open and View.
SERVED = frozenset({sidecar_pb2.ACCESS_LEVEL_WRITE, sidecar_pb2.ACCESS_LEVEL_READ})

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "frame-src 'none'",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ]
)

mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("font/woff2", ".woff2")


def _headers(cache: str) -> tuple[tuple[str, str], ...]:
    return (
        ("content-security-policy", CSP),
        ("x-content-type-options", "nosniff"),
        ("referrer-policy", "no-referrer"),
        ("cache-control", cache),
    )


def _bytes(body: bytes, content_type: str, status: int = 200, cache: str = "no-store") -> meridian.Response:
    return meridian.Response(body, status, content_type, _headers(cache))


def _json(value: Any, status: int = 200) -> meridian.Response:
    return _bytes(json.dumps(value).encode(), "application/json", status)


def _said(status: int, text: str) -> meridian.Response:
    return _bytes(text.encode(), "text/plain; charset=utf-8", status)


class Desk(meridian.Pages):
    """The declared tabs, and the desk's files and read routes under them."""

    def __init__(self, book: Book | None = None, web: Path = WEB) -> None:
        super().__init__(TITLE, templates=Path(__file__).parent / "templates")
        self.book = book or Book()
        self.web = web

    async def dispatch(self, request: meridian.Request) -> meridian.Response:
        method = request.method.upper()
        declared = (request.path, "GET" if method == "HEAD" else method)
        if declared in self._declared_paths() and request.path != "/":
            return await super().dispatch(request)
        if request.caller.level not in SERVED:
            return _said(403, "The desk is served under Open and View.")
        if method not in ("GET", "HEAD"):
            return _said(405, "The desk reads; it takes no change.")
        answer = await self._serve(request)
        if method == "HEAD":
            return meridian.Response(b"", answer.status, answer.content_type, answer.headers)
        return answer

    def _declared_paths(self) -> set[tuple[str, str]]:
        """The SDK's own: the tabs, and the read tools' routes."""
        tabs = {(page.path, "GET") for page in self.declared}
        return tabs | {(tool.path, tool.method) for tool in self.tools}

    async def intervals(self, base: str, quote: str) -> list[str]:
        """The bar lengths the chart offers for a pair.

        Each length over the chart's own window, so a length is offered
        wherever the chart would draw bars of it, however old the newest is.
        A length the lake declines (one no dataset covers, or whose source is
        silent) is not offered, and does not hide another that holds bars;
        with none held, what was declined is said."""
        held: list[str] = []
        declined: list[str] = []
        for label, ns in INTERVALS.items():
            try:
                if await self.book.bar_rows(base, quote, ns):
                    held.append(label)
            except Refused as why:
                declined.append(str(why))
        if not held and declined:
            raise Refused(" ".join(dict.fromkeys(declined)))
        return held

    async def _serve(self, request: meridian.Request) -> meridian.Response:
        path = request.path
        if path.startswith("/api/"):
            try:
                return await self._api(path[len("/api/") :], request)
            except Refused as why:
                return _json({"refused": str(why)})
            except BadToken as why:
                return _json({"error": str(why)}, 400)
        if path in ("", "/", "/index.html"):
            return self.index()
        found = self._file(path)
        if found is not None:
            kind = mimetypes.guess_type(found.name)[0] or "application/octet-stream"
            hashed = found.parent.name == "assets"
            cache = "public, max-age=31536000, immutable" if hashed else "no-cache"
            return _bytes(found.read_bytes(), kind, cache=cache)
        return _said(404, "No such file.")

    async def _api(self, route: str, request: meridian.Request) -> meridian.Response:
        q = request.query
        caller = request.caller
        if route == "me":
            return _json({"name": caller.display_name, "accounts": sorted(readable(caller))})
        if route == "blotter":
            since = watermark_of(q.get("since", ""))
            result = await self.book.orders(since)
            rows = blotter_rows(result, readable(caller))
            return _json(
                {
                    "rows": [asdict(r) for r in rows],
                    "since": token_of(result.as_of),
                    "changed_only": since is not None,
                }
            )
        if route == "positions":
            held = holdings(await self.book.positions(), readable(caller))
            return _json({"rows": [asdict(h) for h in held]})
        if route == "lookup":
            found = await self.book.lookup(q.get("q", ""))
            return _json({"found": asdict(found) if found else None})
        base, quote = q.get("base", ""), q.get("quote", "")
        if not base:
            return _json({"error": "name an instrument: base, and quote for a pair"}, 400)
        if route == "price":
            return _json({"latest": await self.book.latest(base, quote)})
        if route == "intervals":
            return _json({"intervals": await self.intervals(base, quote)})
        if route == "bars":
            label = q.get("interval", "1d")
            if label not in INTERVALS:
                return _json({"error": f"no bar length {label!r}"}, 400)
            return _json({"interval": label, "bars": await self.book.bars(base, quote, INTERVALS[label])})
        return _json({"error": "no such route"}, 404)

    def _file(self, path: str) -> Path | None:
        target = (self.web / path.lstrip("/")).resolve()
        if self.web.resolve() not in target.parents or not target.is_file():
            return None
        return target

    def index(self) -> meridian.Response:
        return _bytes((self.web / "index.html").read_bytes(), "text/html; charset=utf-8")


pages = Desk()


def use(book: Book) -> None:
    """The role class the pages read through: the one the plugin runs."""
    pages.book = book


@pages.page("/", TITLE, levels=["write", "read"])
async def desk(request: meridian.Request) -> meridian.Response:
    """The desk: a blotter, positions, a watchlist, a chart and a picker, in
    panels a person docks, tabs and floats for the session. Read-only."""
    return pages.index()


@pages.page(
    "/datasets",
    "Datasets",
    levels="admin",
    answers=reporting.DatasetsRead,
    name="read_datasets",
)
async def datasets(request: meridian.Request) -> meridian.Response:
    """Each dataset this plugin reads, whether it is entitled to it and to
    which fields."""
    read = await pages.book.list_datasets()
    mine = {each.dataset: each for each in read.entitlements}
    said = reporting.DatasetsRead(
        datasets=[
            reporting.DatasetRead(
                dataset=ref.dataset,
                entitled=ref.dataset in mine and mine[ref.dataset].allowed,
                fields=list(mine[ref.dataset].fields) if ref.dataset in mine else [],
                misses=ref.miss_count,
            )
            for ref in read.datasets
        ]
    )
    return pages.answer("datasets.html", said)


# ── The read tools: each read the desk shows, on the deployment's MCP ──────

#: The read tools' paths: under none of the desk's own (`/api/...`, files).
TOOLS = "/tools"

#: The levels the desk is served under, which its reads' tools serve.
READ_LEVELS = ["write", "read"]

_BASE = {"description": "The instrument's ID, or a pair's base currency's cash instrument", "max_length": 64}
_QUOTE = {"description": "A pair's quote currency's cash instrument; empty for one instrument", "max_length": 64}


@dataclass(frozen=True)
class BlotterAsked:
    """What the blotter is asked: every row, or those changed since."""

    since: str = field(
        default="",
        metadata={
            "description": "A changed-since token a previous read_blotter answered (its `since`); "
            "empty for every row",
            "max_length": 512,
        },
    )


@dataclass(frozen=True)
class BlotterRead:
    """The blotter's rows: orders, placements and fills on the accounts the
    person may read, newest first."""

    rows: list[Row] = field(default_factory=list)
    since: str = ""
    changed_only: bool = False


@dataclass(frozen=True)
class PositionsRead:
    """The positions on the accounts the person may read."""

    rows: list[Holding] = field(default_factory=list)


@dataclass(frozen=True)
class LookupAsked:
    """What the instrument picker is asked."""

    query: str = field(
        metadata={
            "description": "A pair of ISO 4217 codes (EUR/USD), a code, an instrument's ID, "
            "a FIGI, an ISIN or a ticker",
            "max_length": 64,
        }
    )


@dataclass(frozen=True)
class LookupRead:
    """The instrument the picker points at for what was asked: none or one."""

    found: list[Pair] = field(default_factory=list)


@dataclass(frozen=True)
class PairAsked:
    """An instrument, or a pair of cash instruments, the desk points at."""

    base: str = field(metadata=_BASE)
    quote: str = field(default="", metadata=_QUOTE)


@dataclass(frozen=True)
class LatestRead:
    """The latest price of the instrument or pair, as the watchlist shows it;
    every field empty where the lake holds none."""

    price: str = ""
    kind: str = ""
    at: str = ""
    recorded_at: str = ""
    dataset: str = ""


@dataclass(frozen=True)
class LengthsRead:
    """The bar lengths the chart offers for the instrument or pair."""

    intervals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BarsAsked:
    """The chart's bars of one length."""

    base: str = field(metadata=_BASE)
    quote: str = field(default="", metadata=_QUOTE)
    interval: str = field(
        default="1d", metadata={"description": "The bar length", "choices": list(INTERVALS)}
    )


@dataclass(frozen=True)
class BarsRead:
    """The bars the chart draws, oldest first, each price as the lake records it."""

    interval: str = ""
    bars: list[Bar] = field(default_factory=list)


def _rows(records: list[Any]) -> list[dict[str, Any]]:
    return [asdict(each) for each in records]


def _read(heading: str, data: Any, columns: list[tuple[str, str]], rows: list[dict[str, Any]], empty: str) -> meridian.Response:
    return pages.answer("read.html", data, heading=heading, columns=columns, rows=rows, empty=empty)


async def _or_refused(read: Any) -> Any:
    """A read, or its refusal said as the panel says it."""
    try:
        return await read
    except Refused as why:
        pages.refuse(str(why), reason="declined")


@pages.route(f"{TOOLS}/blotter", levels=READ_LEVELS, params=BlotterAsked, answers=BlotterRead, name="read_blotter")
async def read_blotter(request: meridian.Request) -> meridian.Response:
    """The blotter: the orders, placements and fills on the accounts the
    person may read, newest first, each with its state and last change; or,
    given a `since` a previous read answered, only those changed since."""
    asked = request.params.since if request.params is not None else ""
    try:
        since = watermark_of(asked)
    except BadToken as why:
        pages.refuse(str(why), ("since", str(why)), reason="invalid_arguments")
    result = await pages.book.orders(since)
    rows = blotter_rows(result, readable(request.caller))
    said = BlotterRead(rows=rows, since=token_of(result.as_of), changed_only=since is not None)
    columns = [
        ("kind", "Kind"), ("id", "ID"), ("account", "Account"), ("instrument", "Instrument"),
        ("side", "Side"), ("quantity", "Quantity"), ("price", "Price"), ("state", "State"), ("at", "At"),
    ]
    return _read("Blotter", said, columns, _rows(rows), "No order, placement or fill on your accounts.")


@pages.route(f"{TOOLS}/positions", levels=READ_LEVELS, answers=PositionsRead, name="read_positions")
async def read_positions(request: meridian.Request) -> meridian.Response:
    """The positions on the accounts the person may read, by account and
    instrument: side, trade-date and settled quantities, and last change."""
    held = holdings(await pages.book.positions(), readable(request.caller))
    columns = [
        ("account", "Account"), ("instrument", "Instrument"), ("side", "Side"),
        ("quantity", "Quantity"), ("settled", "Settled"), ("last_change", "Last change"),
    ]
    return _read("Positions", PositionsRead(rows=held), columns, _rows(held), "No position on your accounts.")


@pages.route(f"{TOOLS}/instrument", levels=READ_LEVELS, params=LookupAsked, answers=LookupRead, name="read_instrument")
async def read_instrument(request: meridian.Request) -> meridian.Response:
    """The instrument an identifier names, as the desk's picker finds it: a
    pair's two cash instruments, or one instrument's record."""
    asked = request.params.query if request.params is not None else ""
    found = await pages.book.lookup(asked)
    listed = [found] if found else []
    columns = [("label", "Asked"), ("base", "Instrument"), ("quote", "Quote"), ("description", "Description")]
    return _read("Instrument", LookupRead(found=listed), columns, _rows(listed), f"No instrument for {asked!r}.")


@pages.route(f"{TOOLS}/latest-price", levels=READ_LEVELS, params=PairAsked, answers=LatestRead, name="read_latest_price")
async def read_latest_price(request: meridian.Request) -> meridian.Response:
    """The latest price of an instrument or pair, with its kind, its time and
    the dataset it came from, as the desk's watchlist shows it."""
    asked = request.params
    latest = await _or_refused(pages.book.latest(asked.base, asked.quote))
    said = LatestRead(**latest)
    columns = [("price", "Price"), ("kind", "Kind"), ("at", "At"), ("dataset", "Dataset")]
    return _read("Latest price", said, columns, [asdict(said)] if latest else [], "The lake holds no price for it.")


@pages.route(f"{TOOLS}/bar-lengths", levels=READ_LEVELS, params=PairAsked, answers=LengthsRead, name="read_bar_lengths")
async def read_bar_lengths(request: meridian.Request) -> meridian.Response:
    """The bar lengths (1m, 1h, 1d) the lake holds bars of for an instrument
    or pair over the chart's window: what the desk's chart offers."""
    asked = request.params
    held = await _or_refused(pages.intervals(asked.base, asked.quote))
    rows = [{"interval": each} for each in held]
    return _read("Bar lengths", LengthsRead(intervals=held), [("interval", "Length")], rows, "No bars held.")


@pages.route(f"{TOOLS}/bars", levels=READ_LEVELS, params=BarsAsked, answers=BarsRead, name="read_bars")
async def read_bars(request: meridian.Request) -> meridian.Response:
    """The bars of one length the desk's chart draws for an instrument or
    pair, oldest first, up to 500, each price exactly as the lake records it."""
    asked = request.params
    bars = await _or_refused(pages.book.bar_rows(asked.base, asked.quote, INTERVALS[asked.interval]))
    columns = [("at", "At"), ("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("dataset", "Dataset")]
    said = BarsRead(interval=asked.interval, bars=bars)
    return _read("Bars", said, columns, _rows(bars), "The lake holds no bar of that length.")
