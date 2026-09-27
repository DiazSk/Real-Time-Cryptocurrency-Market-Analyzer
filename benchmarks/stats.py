"""Pure metric helpers for the benchmark scripts (tested in tests/benchmarks/test_stats.py)."""

import re
import statistics

_SEND_ERRORS = re.compile(r"'send_errors': (\d+)")


def percentiles(values):
    """p50/p95/p99 with linear interpolation; None for each when there are no samples."""
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    if len(values) == 1:
        v = float(values[0])
        return {"p50": v, "p95": v, "p99": v}
    q = statistics.quantiles(values, n=100, method="inclusive")
    return {"p50": q[49], "p95": q[94], "p99": q[98]}


def delivery_ratios(counts):
    """Each client's frame count relative to the best client in the same step."""
    top = max(counts, default=0)
    return [c / top if top else 0.0 for c in counts]


def step_passed(counts, threshold=0.99):
    """A step passes only if trades flowed and every client got at least `threshold` of them."""
    ratios = delivery_ratios(counts)
    return bool(ratios) and max(counts) > 0 and min(ratios) >= threshold


def max_passing_step(steps):
    """Largest client count before the first failed step (steps in ascending order)."""
    best = None
    for step in sorted(steps, key=lambda s: s["clients"]):
        if not step["passed"]:
            break
        best = step["clients"]
    return best


def parse_send_errors(log_text):
    """send_errors from the producer's most recent `stats {...}` log line."""
    found = _SEND_ERRORS.findall(log_text)
    return int(found[-1]) if found else None


def send_errors_delta(before, after):
    """Errors during a scenario; a smaller `after` means the producer restarted and the counter reset."""
    if before is None or after is None:
        return None
    return after - before if after >= before else after
