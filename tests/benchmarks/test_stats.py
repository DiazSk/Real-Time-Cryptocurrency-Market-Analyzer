from benchmarks.stats import (
    delivery_ratios,
    max_passing_step,
    parse_send_errors,
    percentiles,
    send_errors_delta,
    step_passed,
)


def test_percentiles_interpolate_between_samples():
    p = percentiles(list(range(1, 101)))
    assert p["p50"] == 50.5
    assert round(p["p95"], 2) == 95.05
    assert round(p["p99"], 2) == 99.01


def test_percentiles_of_empty_and_single():
    assert percentiles([]) == {"p50": None, "p95": None, "p99": None}
    assert percentiles([7]) == {"p50": 7.0, "p95": 7.0, "p99": 7.0}


def test_delivery_ratio_is_relative_to_the_best_client():
    assert delivery_ratios([100, 99, 50]) == [1.0, 0.99, 0.5]
    assert delivery_ratios([0, 0]) == [0.0, 0.0]


def test_step_passes_only_when_every_client_keeps_up_and_trades_flowed():
    assert step_passed([100, 99])
    assert not step_passed([100, 98])
    assert not step_passed([0, 0])  # no trades at all is not a pass
    assert not step_passed([])


def test_headline_stops_at_the_first_failed_step():
    steps = [
        {"clients": 25, "passed": True},
        {"clients": 50, "passed": False},
        {"clients": 100, "passed": True},
    ]
    assert max_passing_step(steps) == 25
    assert max_passing_step([{"clients": 25, "passed": False}]) is None


def test_parse_send_errors_takes_the_last_stats_line():
    log = (
        "2026-09-27 01:00:00,000 stats {'published': 5, 'invalid': 0, 'duplicates': 0, "
        "'send_errors': 1, 'reconnects': 0} missed_trades=0\n"
        "2026-09-27 01:01:00,000 stats {'published': 9, 'invalid': 0, 'duplicates': 0, "
        "'send_errors': 4, 'reconnects': 0} missed_trades=2\n"
    )
    assert parse_send_errors(log) == 4
    assert parse_send_errors("no stats yet") is None


def test_send_errors_delta_handles_a_restarted_producer():
    assert send_errors_delta(3, 7) == 4
    assert send_errors_delta(7, 2) == 2  # counter reset by a restart
    assert send_errors_delta(None, 2) is None
