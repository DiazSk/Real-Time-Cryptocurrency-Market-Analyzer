import re

import pytest

import benchmarks.chaos_test as chaos


@pytest.mark.parametrize("cmdline", [
    "venv/bin/python -m src.producers.coinbase_trades_producer",
    "/Users/me/repo/venv/bin/python3.12 -m src.producers.coinbase_trades_producer",
    # what `ps` really shows for a Homebrew venv python on macOS
    "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12"
    "/Resources/Python.app/Contents/MacOS/Python -m src.producers.coinbase_trades_producer",
])
def test_producer_pattern_matches_the_producer(cmdline):
    assert re.search(chaos.PRODUCER_PGREP, cmdline)


@pytest.mark.parametrize("cmdline", [
    "vim src/producers/coinbase_trades_producer.py",
    "less src/producers/coinbase_trades_producer.py",
    "pytest tests/producers/test_coinbase_trades_producer.py",
])
def test_producer_pattern_ignores_editors_and_tests(cmdline):
    assert not re.search(chaos.PRODUCER_PGREP, cmdline)


def test_container_is_tracked_before_stop_so_ctrl_c_mid_stop_restores_it(monkeypatch):
    def interrupted_docker(*args):
        raise KeyboardInterrupt  # Ctrl-C while `docker stop` is still running

    monkeypatch.setattr(chaos, "docker", interrupted_docker)
    monkeypatch.setattr(chaos, "stopped_containers", set())
    with pytest.raises(KeyboardInterrupt):
        chaos.stop_container("postgres")
    assert chaos.stopped_containers == {"postgres"}
