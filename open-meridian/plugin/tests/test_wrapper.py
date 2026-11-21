"""The wrapper, against the stand-in sidecar: the per-person cut of the
blotter and positions, changed-since reads, the lookup, the price and the
bars and their refusals, the levels, no route that takes a change, and the
Content-Security-Policy. `meridian plugin check --run-tests` and the fork's
CI run these; none needs a deployment."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from meridian.testing import PageClient

sys.path.insert(0, str(Path(__file__).parent))

from standin import Sidecar  # noqa: E402

from desk.book import Book, token_of  # noqa: E402
from desk.pages import CSP, pages, use  # noqa: E402

SRC = Path(__file__).parent.parent / "src" / "desk"


@pytest.fixture(autouse=True)
def web(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html><title>Desk</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("export {}")
    monkeypatch.setattr(pages, "web", tmp_path)


def client(sidecar: Sidecar | None = None, read=(), who="local|pat", name="Pat Example"):
    sidecar = sidecar or Sidecar()
    use(sidecar.bind(Book()))
    return PageClient(pages, sidecar, read=read, subject=who, display_name=name), sidecar


def body(answer):
    return json.loads(answer.body)


def test_two_people_each_see_only_their_own_accounts_rows() -> None:
    pat, _ = client(read={"ACC-A"})
    sam, _ = client(read={"ACC-B"}, who="local|sam", name="Sam Example")
    for person, mine, theirs in ((pat, "ACC-A", "ACC-B"), (sam, "ACC-B", "ACC-A")):
        rows = body(person.get("/api/blotter", "read"))["rows"]
        assert rows and {r["account"] for r in rows} == {mine}
        assert theirs not in json.dumps(rows)
        held = body(person.get("/api/positions", "read"))["rows"]
        assert [h["account"] for h in held] == [mine]
    assert body(pat.get("/api/me", "read"))["accounts"] == ["ACC-A"]
    assert body(sam.get("/api/me", "read"))["accounts"] == ["ACC-B"]


def test_a_person_with_no_account_sees_no_row() -> None:
    nobody, _ = client(read=())
    assert body(nobody.get("/api/blotter", "read"))["rows"] == []
    assert body(nobody.get("/api/positions", "read"))["rows"] == []


def test_the_blotter_is_newest_first_with_each_rows_state_and_last_change() -> None:
    pat, _ = client(read={"ACC-A"})
    rows = body(pat.get("/api/blotter", "read"))["rows"]
    assert [r["id"] for r in rows] == ["PLC-A2", "ORD-A2", "EXE-A1", "PLC-A1", "ORD-A1"]
    first = rows[0]
    assert first["kind"] == "placement" and first["state"] == "working"
    assert first["last_change"] == "book-0 #7" and first["at"] == "2025-11-20T15:31:00Z"
    fill = next(r for r in rows if r["kind"] == "fill")
    assert fill["price"] == "1.1518 USD" and fill["state"] == "matched"


def test_changed_since_reads_hand_the_watermark_back_and_cut_the_same_way() -> None:
    pat, sidecar = client(read={"ACC-A"})
    first = body(pat.get("/api/blotter", "read"))
    assert first["changed_only"] is False and first["since"]
    from meridian.plugin.v1 import operations_pb2 as ops

    halfway = token_of(ops.Watermark(partitions=[ops.PartitionSequence(partition="book-0", sequence=5)]))
    later = body(pat.get("/api/blotter", "read", since=halfway))
    assert later["changed_only"] is True
    assert [r["id"] for r in later["rows"]] == ["PLC-A2", "ORD-A2"]
    assert sidecar.asked[-1].since.partitions[0].sequence == 5
    assert pat.get("/api/blotter", "read", since="not-a-token!").status == 400


def test_the_lookup_points_at_a_pair_by_its_codes() -> None:
    pat, _ = client(read={"ACC-A"})
    found = body(pat.get("/api/lookup", "read", q="eur/usd"))["found"]
    assert found == {"label": "EUR/USD", "base": "INS-EUR", "quote": "INS-USD", "description": "", "identifiers": []}
    assert body(pat.get("/api/lookup", "read", q="XYZ/ABC"))["found"] is None


def test_the_latest_price_and_the_bars_with_their_times() -> None:
    pat, _ = client(read={"ACC-A"})
    latest = body(pat.get("/api/price", "read", base="INS-EUR", quote="INS-USD"))["latest"]
    assert latest["price"] == "1.1534" and latest["at"] == "2025-11-20T16:00:00Z"
    assert latest["dataset"] == "truefx:daily"
    bars = body(pat.get("/api/bars", "read", base="INS-EUR", quote="INS-USD", interval="1d"))["bars"]
    assert len(bars) == 30 and bars[0]["time"] < bars[-1]["time"]
    assert {"open", "high", "low", "close"} <= set(bars[0])
    held = body(pat.get("/api/intervals", "read", base="INS-EUR", quote="INS-USD"))["intervals"]
    assert held == ["1d"]


def test_a_length_is_offered_over_the_charts_window_and_another_lengths_refusal_does_not_hide_it() -> None:
    pat, sidecar = client(read={"ACC-A"})
    held = body(pat.get("/api/intervals", "read", base="INS-EUR", quote="INS-USD"))
    assert held == {"intervals": ["1d"]}
    asked = {p.interval_ns: p.valid_until_ns - p.valid_from_ns for p in sidecar.asked if hasattr(p, "interval_ns")}
    day = 86_400 * 1_000_000_000
    assert asked[day] >= 500 * day, "the probe reads the chart's window, not the last two bars"
    assert set(asked) == {60 * 1_000_000_000, 3600 * 1_000_000_000, day}


def test_with_the_entitlement_withdrawn_the_panels_get_the_refusal_not_empty_data() -> None:
    pat, _ = client(Sidecar(entitled=False), read={"ACC-A"})
    for route, query in (("price", {}), ("bars", {"interval": "1d"}), ("intervals", {})):
        said = body(pat.get(f"/api/{route}", "read", base="INS-EUR", quote="INS-USD", **query))
        assert "not entitled to any dataset" in said["refused"]


def test_the_desk_is_served_under_open_and_view_and_refused_under_manage_or_nothing() -> None:
    pat, _ = client(read={"ACC-A"})
    for level in ("read", "write"):
        assert pat.get("/", level).status == 200
        assert pat.get("/api/me", level).status == 200
    for level in ("admin", ""):
        assert pat.get("/", level).status == 403
        assert pat.get("/api/blotter", level).status == 403
    assert pat.get("/datasets", "admin").status == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_no_route_takes_a_change(method) -> None:
    pat, sidecar = client(read={"ACC-A"})
    for path in ("/", "/api/blotter", "/api/orders", "/api/place", "/api/cancel"):
        assert pat.request(method, path, "write").status == 405
    assert not [m for m in sidecar.read if not m.startswith(("List", "Resolve"))]


def test_every_answer_carries_the_csp_and_it_names_no_outside_host() -> None:
    pat, _ = client(read={"ACC-A"})
    for path in ("/", "/assets/index-abc123.js", "/api/me", "/api/blotter"):
        headers = dict(pat.get(path, "read").headers)
        assert headers["content-security-policy"] == CSP
    for directive in CSP.split("; "):
        if directive.split()[0] in ("connect-src", "img-src", "font-src"):
            assert "https:" not in directive and "wss:" not in directive and "http:" not in directive


def test_the_wrapper_holds_no_order_act_and_no_outside_route() -> None:
    """Backs the declaration: the code calls no order operation and no
    HTTP client (open-meridian/ci/checks.sh greps the front end too)."""
    code = "\n".join(p.read_text() for p in SRC.glob("*.py"))
    acts = re.findall(r"\b(create_order|amend_order|cancel_order|release_order|create_placement|"
                      r"amend_placement|cancel_placement|record_execution|place_order)\b", code)
    assert acts == []
    assert not re.search(r"^\s*(import|from) (urllib\.request|http\.client|socket|requests|httpx|aiohttp)\b", code, re.M)
