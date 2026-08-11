"""Unit tests for pursuit.infra.email — recipient parsing (no network, no real accounts)."""

from pursuit.infra.email import _recipient_list


def test_single_recipient() -> None:
    assert _recipient_list("solo@example.com") == ["solo@example.com"]


def test_comma_separated_recipients_split_and_trim() -> None:
    # a league friendly reports to BOTH teams' inboxes in one send
    assert _recipient_list("a@example.com, b@example.com , c@example.com") == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
    ]


def test_empty_and_whitespace_entries_dropped() -> None:
    assert _recipient_list("a@example.com,,  , b@example.com") == [
        "a@example.com",
        "b@example.com",
    ]
