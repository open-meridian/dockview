"""The plugin's reads: its `reporting` role class, and what each panel asks.

Every read goes through the plugin's sidecar, at the plugin's own scope
(W4.9), and records nothing. The book answers the plugin for every account
its scope reaches, so the rows of orders, placements, fills and positions
are cut here to the accounts the person whose page it is may read on this
plugin (decisions/014, W4.10): `Caller.read_for("reporting")`. That cut is
the plugin's, and nothing at runtime makes it for it.

A read the lake declines is said as a refusal, with its reason, never shown
as an empty table.

The reads are the reporting role's that exist in SDK 0.37.1:

- the blotter: `list_orders`, orders with their placements and executions
  in one reply, changed since a watermark the page hands back;
- positions: `list_positions`;
- an instrument by an identifier: `resolve_identifier`, and
  `resolve_instrument` for its record;
- the latest price: `list_prices`; bars: `list_bars`.

An FX pair is priced as its data plugins record it: the base currency's
cash instrument as the row's subject, its price a `Money` in the quote
currency's cash instrument.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import meridian
from google.protobuf.message import DecodeError
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import reporting

NS = 1_000_000_000

#: The role whose accounts a person's rows are cut to.
ROLE = "reporting"

#: The bar lengths the chart offers, shortest first, by the label it shows:
#: a length is offered only where the lake holds bars of it in the chart's
#: window, its last 500 bars (`Book.bars`).
INTERVALS = {"1m": 60 * NS, "1h": 3600 * NS, "1d": 86_400 * NS}

#: How many pages of one read are followed at the most: a page is the book's
#: or the lake's own size.
PAGES = 50

REASONS = {
    ops.UNANSWERED_REASON_NOT_ENTITLED: "not entitled",
    ops.UNANSWERED_REASON_NOT_COVERED: "not covered by any dataset",
    ops.UNANSWERED_REASON_ASKED_SOURCE: "asked of its source, not answered yet",
    ops.UNANSWERED_REASON_SOURCE_SILENT: "its source states nothing for it",
    ops.UNANSWERED_REASON_UNRESOLVED: "its instrument is not resolved",
    ops.UNANSWERED_REASON_BEYOND_HISTORY: "beyond the dataset's history",
    ops.UNANSWERED_REASON_NOT_KEPT: "not kept",
    ops.UNANSWERED_REASON_QUARANTINED: "quarantined",
}


class Refused(Exception):
    """A read the deployment declined, said as it was declined."""


class BadToken(ValueError):
    """A changed-since token that is not one this plugin handed out."""


def moment(ns: int) -> str:
    """A time in nanoseconds as ISO 8601, in UTC; empty for none."""
    if not ns:
        return ""
    return datetime.fromtimestamp(ns / NS, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value: Any) -> str:
    """A wire decimal as text; empty when unset."""
    if value is None or not value.ByteSize():
        return ""
    return str(meridian.as_decimal(value))


def money(value: Any) -> str:
    """A price as text, with its currency's code when the record names one."""
    if value is None or not value.ByteSize():
        return ""
    amount = number(value.amount)
    return f"{amount} {value.currency_code}".strip()


def _name(enum: Any, value: int, prefix: str) -> str:
    if not value:
        return ""
    return enum.Name(value).removeprefix(prefix).replace("_", " ").lower()


def token_of(watermark: ops.Watermark) -> str:
    """A watermark as the opaque token the page hands back."""
    return base64.urlsafe_b64encode(watermark.SerializeToString()).decode()


def watermark_of(token: str) -> ops.Watermark | None:
    """The watermark a token names; None for none."""
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        held = ops.Watermark.FromString(raw)
    except (binascii.Error, ValueError, DecodeError) as failed:
        raise BadToken("not a changed-since token this desk handed out") from failed
    return held


def readable(caller: meridian.Caller) -> frozenset[str]:
    """The accounts the person may read on this plugin: their reporting
    role's, or, where the claims carry no entry per role, the session's."""
    found = caller.read_for(ROLE)
    return frozenset(found if found else caller.read)


@dataclass(frozen=True)
class Row:
    """One line of the blotter: an order, a placement or a fill."""

    kind: str
    id: str
    order_id: str
    account: str
    instrument: str
    side: str
    quantity: str
    price: str
    state: str
    at: str
    at_ns: int
    last_change: str
    sequence: int


@dataclass(frozen=True)
class Holding:
    """One position."""

    account: str
    instrument: str
    side: str
    quantity: str
    settled: str
    last_change: str


@dataclass(frozen=True)
class Pair:
    """An instrument the desk points at: an FX pair, or one instrument."""

    label: str
    base: str
    quote: str = ""
    description: str = ""
    identifiers: list[str] = field(default_factory=list)


def _change(ref: Any) -> tuple[str, int]:
    if ref is None or not ref.ByteSize():
        return "", 0
    return f"{ref.partition} #{ref.sequence}", int(ref.sequence)


def _order_row(order: ops.Order) -> Row:
    change, sequence = _change(order.last_change)
    price = money(order.limit_price) or money(order.stop_price)
    return Row(
        kind="order",
        id=order.order_id,
        order_id=order.order_id,
        account=order.account_id,
        instrument=order.instrument_id,
        side=_name(ops.Side, order.side, "SIDE_"),
        quantity=number(order.quantity),
        price=price,
        state=_name(ops.OrderState, order.status.state, "ORDER_STATE_"),
        at=moment(order.received_at_ns),
        at_ns=order.received_at_ns,
        last_change=change,
        sequence=sequence,
    )


def _placement_row(placement: ops.Placement, instrument: str, side: str) -> Row:
    change, sequence = _change(placement.last_change)
    return Row(
        kind="placement",
        id=placement.placement_id,
        order_id=placement.order_id,
        account=placement.account_id,
        instrument=instrument,
        side=side,
        quantity=number(placement.quantity),
        price=money(placement.limit_price),
        state=_name(ops.PlacementState, placement.status.state, "PLACEMENT_STATE_"),
        at=moment(placement.routed_at_ns),
        at_ns=placement.routed_at_ns,
        last_change=change,
        sequence=sequence,
    )


def _fill_row(execution: ops.Execution) -> Row:
    change, sequence = _change(execution.last_change)
    return Row(
        kind="fill",
        id=execution.execution_id,
        order_id=execution.order_id,
        account=execution.account_id,
        instrument=execution.instrument_id,
        side=_name(ops.Side, execution.side, "SIDE_"),
        quantity=number(execution.quantity),
        price=money(execution.price),
        state=_name(ops.ExecutionState, execution.state, "EXECUTION_STATE_") or "recorded",
        at=moment(execution.trade_time_ns),
        at_ns=execution.trade_time_ns,
        last_change=change,
        sequence=sequence,
    )


def blotter_rows(result: ops.ListOrdersResult, accounts: Iterable[str]) -> list[Row]:
    """The reply's orders, placements and fills on the accounts given,
    newest first. Placements and executions come both at the top of the
    reply and inside their orders; each is shown once."""
    allowed = set(accounts)
    orders = {o.order_id: o for o in result.orders}
    placements = {p.placement_id: p for p in result.placements}
    executions = {e.execution_id: e for e in result.executions}
    for order in result.orders:
        for p in order.placements:
            placements.setdefault(p.placement_id, p)
        for e in order.executions:
            executions.setdefault(e.execution_id, e)
    rows = [_order_row(o) for o in orders.values() if o.account_id in allowed]
    for p in placements.values():
        if p.account_id not in allowed:
            continue
        parent = orders.get(p.order_id)
        rows.append(
            _placement_row(
                p,
                parent.instrument_id if parent else "",
                _name(ops.Side, parent.side, "SIDE_") if parent else "",
            )
        )
    rows += [_fill_row(e) for e in executions.values() if e.account_id in allowed]
    return sorted(rows, key=lambda r: (r.at_ns, r.sequence), reverse=True)


def holdings(positions: Iterable[ops.BookPosition], accounts: Iterable[str]) -> list[Holding]:
    """The positions on the accounts given, by account and instrument."""
    allowed = set(accounts)
    out = []
    for each in positions:
        if each.account_id not in allowed or each.removed:
            continue
        change, _ = _change(each.last_change)
        out.append(
            Holding(
                account=each.account_id,
                instrument=each.instrument_id,
                side=_name(ops.HoldingSide, each.side, "HOLDING_SIDE_"),
                quantity=number(each.trade_date_quantity),
                settled=number(each.settled_quantity),
                last_change=change,
            )
        )
    return sorted(out, key=lambda h: (h.account, h.instrument))


def _unanswered(page: Any) -> list[str]:
    return [
        f"{each.dataset or 'the lake'}: {REASONS.get(each.reason, 'not answered')}"
        for each in page.unanswered
    ]


@dataclass(eq=False)
class Book(reporting.Role):
    """The plugin's reporting role class: reads only, nothing heard."""

    async def orders(self, since: ops.Watermark | None) -> ops.ListOrdersResult:
        """Every order the plugin's scope reaches, or those changed since a
        watermark, its pages joined into one reply."""
        joined = ops.ListOrdersResult()
        cursor = ""
        for _ in range(PAGES):
            page = await self.list_orders(since=since, cursor=cursor)
            joined.orders.extend(page.orders)
            joined.placements.extend(page.placements)
            joined.executions.extend(page.executions)
            if page.as_of.ByteSize():
                joined.as_of.CopyFrom(page.as_of)
            cursor = page.next_cursor
            if not cursor:
                break
        return joined

    async def positions(self) -> list[ops.BookPosition]:
        out: list[ops.BookPosition] = []
        cursor = ""
        for _ in range(PAGES):
            page = await self.list_positions(cursor=cursor)
            out.extend(page.positions)
            cursor = page.next_cursor
            if not cursor:
                break
        return out

    async def entitlement_refusal(self) -> str:
        """Why the plugin reads no dataset, or "" when it is entitled to one."""
        read = await self.list_datasets()
        allowed = {each.dataset for each in read.entitlements if each.allowed}
        names = [each.dataset for each in read.datasets]
        if allowed & set(names):
            return ""
        if not names:
            # The sidecar lists only what the plugin is entitled to, so an
            # entitlement withdrawn and a dataset never licensed read the same.
            return (
                "This plugin is not entitled to any dataset: a deployment admin "
                "licenses one and entitles this plugin to it on Data sources."
            )
        return (
            "This plugin is not entitled to "
            + ", ".join(sorted(names))
            + ": a deployment admin entitles it on Data sources."
        )

    async def instrument_of(self, scheme: str, value: str) -> str:
        found = await self.resolve_identifier(
            identifiers=[meridian.Identifier(scheme=scheme, value=value)]
        )
        return str(found.instrument_id) if found.found else ""

    async def lookup(self, query: str) -> Pair | None:
        """The instrument an identifier names: a pair of ISO 4217 codes
        (EUR/USD), a code, an instrument's ID, a FIGI, an ISIN or a ticker.
        The role has no text search over the master."""
        asked = query.strip().upper()
        pair = re.fullmatch(r"([A-Z]{3})\s*[/ ]?\s*([A-Z]{3})", asked)
        if pair:
            base = await self.instrument_of("iso4217", pair.group(1))
            quote = await self.instrument_of("iso4217", pair.group(2))
            if not base or not quote:
                return None
            return Pair(label=f"{pair.group(1)}/{pair.group(2)}", base=base, quote=quote)
        if re.fullmatch(r"(INS|LCL)-[0-9A-Z]+", asked):
            instrument = asked
        elif re.fullmatch(r"BBG[0-9A-Z]{9}", asked):
            instrument = await self.instrument_of("figi", asked)
        elif re.fullmatch(r"[A-Z]{2}[0-9A-Z]{9}[0-9]", asked):
            instrument = await self.instrument_of("isin", asked)
        elif re.fullmatch(r"[A-Z]{3}", asked):
            instrument = await self.instrument_of("iso4217", asked)
        elif asked:
            instrument = await self.instrument_of("ticker", asked)
        else:
            return None
        if not instrument:
            return None
        record = await self.resolve_instrument(instrument_id=instrument)
        if not record.found:
            return None
        held = record.instrument
        return Pair(
            label=asked,
            base=held.instrument_id,
            description=held.description,
            identifiers=[f"{each.scheme}:{each.value}" for each in held.identifiers],
        )

    @staticmethod
    def _quoted(meta_subject_money: Any, quote: str) -> bool:
        return not quote or meta_subject_money.instrument_id == quote

    async def latest(self, base: str, quote: str) -> dict[str, str]:
        """The latest price of the pair, with its time and dataset."""
        why = await self.entitlement_refusal()
        if why:
            raise Refused(why)
        page = await self.list_prices(subjects=[meridian.SubjectRef(entity_id=base)])
        prices = [p for p in page.prices if self._quoted(p.price, quote)]
        if not prices:
            unanswered = _unanswered(page)
            if unanswered:
                raise Refused("The lake did not answer: " + "; ".join(sorted(set(unanswered))) + ".")
            return {}
        newest = max(prices, key=lambda p: (p.meta.valid_from_ns, p.meta.recorded_at_ns))
        return {
            "price": number(newest.price.amount),
            "kind": _name(ops.PriceKind, newest.kind, "PRICE_KIND_"),
            "at": moment(newest.meta.valid_from_ns),
            "recorded_at": moment(newest.meta.recorded_at_ns),
            "dataset": newest.meta.source.dataset,
        }

    async def bars(self, base: str, quote: str, interval_ns: int, most: int = 500) -> list[dict[str, Any]]:
        """The pair's bars of one length, oldest first, as the chart takes
        them: UTC seconds, and open, high, low and close as numbers."""
        why = await self.entitlement_refusal()
        if why:
            raise Refused(why)
        now = int(datetime.now(UTC).timestamp() * NS)
        seen: dict[int, dict[str, Any]] = {}
        unanswered: list[str] = []
        cursor = ""
        for _ in range(PAGES):
            page = await self.list_bars(
                subjects=[meridian.SubjectRef(entity_id=base)],
                interval_ns=interval_ns,
                valid_from_ns=now - interval_ns * most,
                valid_until_ns=now + interval_ns,
                cursor=cursor,
            )
            unanswered += _unanswered(page)
            for bar in page.bars:
                if not self._quoted(bar.close, quote):
                    continue
                seen[bar.meta.valid_from_ns] = {
                    "time": bar.meta.valid_from_ns // NS,
                    "open": float(number(bar.open.amount) or 0),
                    "high": float(number(bar.high.amount) or 0),
                    "low": float(number(bar.low.amount) or 0),
                    "close": float(number(bar.close.amount) or 0),
                    "dataset": bar.meta.source.dataset,
                }
            cursor = page.next_cursor
            if not cursor:
                break
        if not seen and unanswered:
            raise Refused("The lake did not answer: " + "; ".join(sorted(set(unanswered))) + ".")
        return [seen[at] for at in sorted(seen)][-most:]
