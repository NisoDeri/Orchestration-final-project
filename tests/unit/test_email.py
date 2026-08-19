"""Unit tests for pursuit.infra.email — recipient parsing (no network, no real accounts)."""

import json

from pursuit.infra.email import _mime, _recipient_list


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


def test_result_body_and_attachment_are_the_same_complete_pretty_json() -> None:
    data = {"z": 1, "game_id": "bestteam-vs-nis-yar1", "nested": {"b": 2, "a": "שלום"}}
    document = json.dumps(data, indent=2, ensure_ascii=False)
    msg = _mime(
        "Police-Thief series result: winner nis-yar1",
        document,
        data,
        "yardentziar@gmail.com",
        "result_bestteam-vs-nis-yar1.json",
    )

    attachment = msg.get_payload()[1]
    assert attachment.get_filename() == "result_bestteam-vs-nis-yar1.json"
    expected = document.encode("utf-8")
    assert msg.get_payload()[0].get_payload(decode=True) == expected
    assert attachment.get_payload(decode=True) == expected
