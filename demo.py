"""Replay price-capped IOC orders against timestamped fixture asks."""
from bisect import bisect_right
from collections import defaultdict

from mathutil import BPS, D, ZERO, fixed, level_fill, settings

SCHEMA = {
    "shares": ("Shares per signal", "10", "0.01", "10000"),
    "latency": ("Order delay", "500", "0", "10000"),
    "limit": ("Max buy price", "0.58", "0.01", "0.99"),
    "fee": ("Assumed fee", "20", "0", "1000"),
}
MAX_AGE_MS = 1600


def run(fixture, params):
    config = settings(params, SCHEMA)
    fee_rate = config["fee"] / BPS
    books = defaultdict(list)
    for frame in sorted(fixture["books"], key=lambda entry: entry["at"]):
        asks = sorted((D(price), D(size)) for price, size in frame["asks"])
        books[frame["outcome"]].append((frame["at"], asks))
    times = {outcome: [at for at, _ in frames] for outcome, frames in books.items()}
    consumed = defaultdict(lambda: ZERO)
    rows = []
    traded = partial = 0
    total_shares = total_cost = total_fee = ZERO
    requested = config["shares"]
    for signal in sorted(fixture["signals"], key=lambda entry: entry["at"]):
        outcome = signal["outcome"]
        due = D(signal["at"]) + config["latency"]
        index = bisect_right(times.get(outcome, []), due) - 1
        reason = "No earlier snapshot for this outcome"
        filled = cost = ZERO
        if due > fixture["end"]:
            reason = "Order arrives after the replay window"
        elif index >= 0:
            at, book = books[outcome][index]
            if due - at > MAX_AGE_MS:
                reason = "Snapshot is stale at order arrival"
            else:
                eligible = [
                    (price, size - consumed[(outcome, index, level)])
                    for level, (price, size) in enumerate(book)
                    if price <= config["limit"]
                ]
                filled, cost, allocations = level_fill(eligible, requested)
                for level, size in allocations:
                    consumed[(outcome, index, level)] += size
                reason = "No available asks at or below the cap"
        state = "No fill"
        if filled:
            traded += 1
            fee = cost * fee_rate
            total_shares += filled
            total_cost += cost
            total_fee += fee
            if filled == requested:
                state, reason = "Filled", "Completed within the price cap"
            else:
                partial += 1
                state, reason = "Partial", "Unfilled remainder canceled (IOC)"
        rows.append([
            str(signal["at"]), outcome, fixed(due, 0), state,
            f"{fixed(filled)} / {fixed(requested)}",
            fixed(cost / filled, 4) if filled else "—", reason,
        ])
    return {
        "metrics": [
            ["Orders with fills", str(traded)],
            ["Partial fills", str(partial)],
            ["Shares filled", fixed(total_shares)],
            ["Cash spent incl. fee ($)", fixed(total_cost + total_fee)],
            ["Assumed fee ($)", fixed(total_fee, 4)],
        ],
        "columns": ["Signal (ms)", "Outcome", "Arrival (ms)", "Result", "Shares", "Avg price ($)", "Reason"],
        "rows": rows,
        "note": "Synthetic BTC outcome books. No future snapshots or settlement P&L. Fees are a configurable assumption.",
    }
