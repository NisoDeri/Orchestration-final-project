"""Unit tests for the project logger: configured once, idempotent across calls."""

import logging

from q20.shared.logger import get_logger


def test_logger_is_configured_with_a_handler():
    log = get_logger("q20.test.logger")
    assert log.handlers
    assert log.level == logging.INFO


def test_logger_is_idempotent():
    name = "q20.test.idempotent"
    first = get_logger(name)
    n_handlers = len(first.handlers)
    second = get_logger(name)
    assert first is second
    assert len(second.handlers) == n_handlers  # no duplicate handlers on re-call


def test_logger_default_name():
    assert get_logger().name == "q20"
