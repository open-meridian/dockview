"""The wrapper on this machine, against the stand-in sidecar, for a browser:
every request is given the `Meridian-Caller` header a sidecar would forward,
for Pat in a session at View (DESK_LEVEL to say otherwise) reading account
ACC-A (DESK_ACCOUNTS, comma-separated). For the browser check; never a way
to run the plugin.

    DESK_WEB=<built front end> python tests/dev.py [port]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from meridian.pages import _serve
from meridian.testing import caller_header

sys.path.insert(0, os.path.dirname(__file__))

from standin import Sidecar  # noqa: E402

from desk.book import Book  # noqa: E402
from desk.pages import pages, use  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    sidecar = Sidecar(entitled=os.environ.get("DESK_ENTITLED", "1") == "1")
    use(sidecar.bind(Book()))
    pages.web = Path(os.environ["DESK_WEB"])
    accounts = [a for a in os.environ.get("DESK_ACCOUNTS", "ACC-A").split(",") if a]
    header = caller_header(
        os.environ.get("DESK_LEVEL", "read"), read=accounts, subject="local|pat", display_name="Pat Example"
    ).encode()
    app = pages.app(sidecar)

    async def with_caller(scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope, headers=[*scope["headers"], (b"meridian-caller", header)])
        await app(scope, receive, send)

    async def run() -> None:
        _serve(with_caller, port, asyncio.get_running_loop(), pages.max_body)
        print(f"dev: http://127.0.0.1:{port}/", flush=True)
        await asyncio.Event().wait()

    asyncio.run(run())


if __name__ == "__main__":
    main()
