"""A stand-in for the plugin's sidecar, answering the book's, the lake's and
the master's reads here. The SDK's recorder, which the role class is bound
to.

**Demo data, marked as such.** Its answers come from fixtures/, written for
these tests in the SDK 0.37.1 messages' JSON form: `list_orders.json` a
`ListOrdersResult` (three orders, their placements and two fills on two
accounts, ACC-A and ACC-B), `list_positions.json` a `ListPositionsResult`,
and `list_bars.json` a `ListBarsResult` of thirty made-up daily bars of
EUR/USD. None is a recording of a market or of anybody's book.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import meridian
from google.protobuf import json_format
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

FIXTURES = Path(__file__).parent / "fixtures"
DATASET = "truefx:daily"
CASH = {"EUR": "INS-EUR", "USD": "INS-USD", "GBP": "INS-GBP"}
#: The latest price of EUR in USD the stand-in answers, and its time.
LATEST = "1.1534"
LATEST_NS = 1_763_654_400_000_000_000  # 2025-11-20T16:00:00Z


def fixture(name: str, message: Any) -> Any:
    return json_format.ParseDict(json.loads((FIXTURES / name).read_text()), message)


def wire(text: str) -> ops.Decimal:
    from decimal import Decimal

    amount = Decimal(text)
    scale = max(0, -int(amount.as_tuple().exponent))
    return ops.Decimal(low=int(amount.scaleb(scale)), scale=scale)


class _Named:
    def __getattr__(self, name: str) -> str:
        return name


class Sidecar(Recorder):
    identity = meridian.Identity("desk", roles=("reporting",))
    grants = meridian.Grants()

    def __init__(self, entitled: bool = True, orders: bool = True) -> None:
        super().__init__("desk")
        #: With the entitlement withdrawn the sidecar lists no dataset, as a
        #: deployment's does, and the lake answers not entitled.
        self.entitled = entitled
        self.orders = orders
        self.read: list[str] = []
        self.asked: list[Any] = []

    def _operations(self) -> Any:
        return _Named()

    async def _operate(self, method: Any, params: Any) -> Any:
        self.read.append(cast(str, method))
        self.asked.append(params)
        if method == "ListOrders":
            if not self.orders:
                return ops.ListOrdersResult(as_of=ops.Watermark(partitions=[ops.PartitionSequence(partition="book-0", sequence=1)]))
            result = fixture("list_orders.json", ops.ListOrdersResult())
            if params.since.ByteSize():
                # Changed since: what the stand-in holds past the watermark.
                after = params.since.partitions[0].sequence
                kept = [o for o in result.orders if o.last_change.sequence > after]
                del result.orders[:]
                result.orders.extend(kept)
                for name in ("placements", "executions"):
                    rows = [r for r in getattr(result, name) if r.last_change.sequence > after]
                    del getattr(result, name)[:]
                    getattr(result, name).extend(rows)
            return result
        if method == "ListPositions":
            return fixture("list_positions.json", ops.ListPositionsResult())
        if method == "ListDatasets":
            if not self.entitled:
                return ops.ListDatasetsResult()
            return ops.ListDatasetsResult(
                datasets=[ops.DatasetRef(dataset=DATASET, vendor="TrueFX")],
                entitlements=[ops.DatasetEntitlement(dataset=DATASET, allowed=True)],
            )
        if method == "ResolveIdentifier":
            ident = params.identifiers[0]
            if ident.scheme == "iso4217" and ident.value in CASH:
                return ops.ResolveIdentifierResult(found=True, instrument_id=CASH[ident.value])
            return ops.ResolveIdentifierResult(found=False)
        if method == "ResolveInstrument":
            codes = {v: k for k, v in CASH.items()}
            code = codes.get(params.instrument_id)
            if code is None:
                return ops.ResolveInstrumentResult(found=False)
            return ops.ResolveInstrumentResult(
                found=True,
                instrument=ops.InstrumentRecord(
                    instrument_id=params.instrument_id,
                    identifiers=[ops.Identifier(scheme="iso4217", value=code)],
                    asset_class=ops.ASSET_CLASS_CASH,
                    currency=code,
                    description=f"{code} cash",
                ),
            )
        if method == "ListPrices":
            if not self.entitled:
                return ops.ListPricesResult(
                    unanswered=[ops.Unanswered(dataset=DATASET, reason=ops.UNANSWERED_REASON_NOT_ENTITLED)]
                )
            return ops.ListPricesResult(
                prices=[
                    ops.Price(
                        meta=ops.ObservationMeta(
                            subjects=[ops.SubjectRef(entity_id=CASH["EUR"])],
                            source=ops.Source(dataset=DATASET),
                            valid_from_ns=LATEST_NS,
                            recorded_at_ns=LATEST_NS + 1_000_000_000,
                        ),
                        kind=ops.PRICE_KIND_CLOSE,
                        price=ops.Money(amount=wire(LATEST), instrument_id=CASH["USD"]),
                    )
                ]
            )
        if method == "ListBars":
            if not self.entitled:
                return ops.ListBarsResult(
                    unanswered=[ops.Unanswered(dataset=DATASET, reason=ops.UNANSWERED_REASON_NOT_ENTITLED)]
                )
            if params.interval_ns != 86_400 * 1_000_000_000:
                # Daily bars alone, as a data plugin recording days answers:
                # any other length is declined, its source silent.
                return ops.ListBarsResult(
                    unanswered=[ops.Unanswered(dataset=DATASET, reason=ops.UNANSWERED_REASON_SOURCE_SILENT)]
                )
            return fixture("list_bars.json", ops.ListBarsResult())
        raise AssertionError(f"the desk read {method}, which no stand-in here answers")
