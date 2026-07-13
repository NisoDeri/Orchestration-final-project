"""Unit tests for the NL protocol builders + tolerant parsers.

Covers the prompt builders' shape and the parsers' resilience: JSON embedded in
prose, non-string input, malformed regex matches, and non-dict array items must all
decode to safe defaults instead of raising — a flaky local model can't crash a round.
"""

from q20.agents import protocol


def test_ask_prompt_has_system_and_user_with_counts():
    msgs = protocol.ask_prompt({"hint": "h", "chain": ["a", "b"]}, 20, 4)
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert "20" in msgs[0]["content"]
    assert "4" in msgs[0]["content"]


def test_answer_prompt_keeps_secret_in_system_role():
    msgs = protocol.answer_prompt("secret paragraph", [{"text": "q", "options": ["a"]}])
    assert any("Never reveal" in m["content"] for m in msgs)


def test_guess_prompt_requests_json_object():
    msgs = protocol.guess_prompt({"hint": "h", "chain": []}, [])
    assert "opening_sentence" in msgs[0]["content"]


def test_parse_questions_extracts_json_from_prose():
    text = 'Sure! Here: [{"text":"q","options":["a","b","c","d"]}] done.'
    qs = protocol.parse_questions(text, 4)
    assert qs == [{"text": "q", "options": ["a", "b", "c", "d"]}]


def test_parse_questions_truncates_options_to_n():
    text = '[{"text":"q","options":["a","b","c","d","e"]}]'
    assert protocol.parse_questions(text, 2)[0]["options"] == ["a", "b"]


def test_parse_questions_drops_non_dict_and_optionless_items():
    text = '["junk", {"text":"ok","options":["a"]}, {"text":"bad"}]'
    qs = protocol.parse_questions(text, 4)
    assert len(qs) == 1 and qs[0]["text"] == "ok"


def test_parse_questions_non_list_returns_empty():
    assert protocol.parse_questions('{"text":"q","options":["a"]}', 4) == []


def test_parse_answers_coerces_floats_and_pads():
    assert protocol.parse_answers("[1, 2.0]", 4) == [1, 2, 0, 0]


def test_parse_answers_non_numeric_defaults_to_zero():
    assert protocol.parse_answers('["x", null, 3]', 3) == [0, 0, 3]


def test_parse_guess_from_embedded_object():
    text = 'My guess: {"opening_sentence":"S","associative_word":"W"} ok'
    assert protocol.parse_guess(text) == {"opening_sentence": "S", "associative_word": "W"}


def test_extract_json_handles_non_string_and_blank():
    assert protocol.parse_questions("", 4) == []
    assert protocol.parse_answers(None, 2) == [0, 0]


def test_extract_json_handles_unparseable_braces():
    # A regex match that still is not valid JSON must fall through to the default.
    assert protocol.parse_guess("text {not: valid json} more") == {
        "opening_sentence": "", "associative_word": ""
    }
