"""The plugin's page: the desk, and the read routes its panels call.

Two tabs are declared, as every page is:

- **Desk** (`/`), under Open and View: the docking layout of panels, built
  into `/plugin/web` (open-meridian/ci/frontend.sh). Its files and its read
  routes (`/api/...`) are served under the same levels by `dispatch` below,
  since the SDK's pages declare exact paths.
- **Datasets** (`/datasets`), under Manage: the reporting role's common page,
  each dataset the plugin reads and whether it is entitled to it.

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
from dataclasses import asdict
from pathlib import Path
from typing import Any

import meridian
from meridian.roles import reporting
from meridian.v1 import sidecar_pb2

from .book import INTERVALS, BadToken, Book, Refused, blotter_rows, holdings, readable, token_of, watermark_of

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
        if declared in {(page.path, "GET") for page in self.declared} and request.path != "/":
            return await super().dispatch(request)
        if request.caller.level not in SERVED:
            return _said(403, "The desk is served under Open and View.")
        if method not in ("GET", "HEAD"):
            return _said(405, "The desk reads; it takes no change.")
        answer = await self._serve(request)
        if method == "HEAD":
            return meridian.Response(b"", answer.status, answer.content_type, answer.headers)
        return answer

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
            held = [label for label, ns in INTERVALS.items() if await self.book.bars(base, quote, ns, most=2)]
            return _json({"intervals": held})
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
