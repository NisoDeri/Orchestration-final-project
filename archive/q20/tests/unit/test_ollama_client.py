"""Unit tests for the stdlib Ollama client — parsing and error paths, no network.

We monkeypatch ``urllib.request.urlopen`` so no real Ollama server is needed: a
fake response proves token telemetry is read from Ollama's own counters, and the
error injections prove transport/JSON failures surface as a single ``Q20Error``.
"""

import io
import json
import urllib.error

import pytest

from q20.shared.exceptions import Q20Error
from q20.shared.ollama_client import OllamaClient


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def _patch_urlopen(monkeypatch, body=None, exc=None):
    def fake(req, timeout=None):
        if exc is not None:
            raise exc
        return _FakeResp(json.dumps(body).encode("utf-8"))
    monkeypatch.setattr("urllib.request.urlopen", fake)


def test_chat_parses_text_and_token_usage(monkeypatch):
    body = {"message": {"content": "hello"}, "prompt_eval_count": 11, "eval_count": 5}
    _patch_urlopen(monkeypatch, body=body)
    res = OllamaClient().chat("qwen2.5:7b", [{"role": "user", "content": "hi"}])
    assert res.text == "hello"
    assert res.usage.input_tokens == 11
    assert res.usage.output_tokens == 5
    assert res.usage.model == "qwen2.5:7b"


def test_chat_passes_num_ctx_option(monkeypatch):
    captured = {}

    def fake(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(json.dumps({"message": {"content": "x"}}).encode("utf-8"))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    OllamaClient().chat("m", [], temperature=0.7, num_ctx=2048)
    assert captured["payload"]["options"]["num_ctx"] == 2048
    assert captured["payload"]["options"]["temperature"] == 0.7
    assert captured["payload"]["stream"] is False


def test_chat_missing_message_yields_empty_text(monkeypatch):
    _patch_urlopen(monkeypatch, body={"prompt_eval_count": 0})
    assert OllamaClient().chat("m", []).text == ""


def test_transport_error_becomes_q20error(monkeypatch):
    _patch_urlopen(monkeypatch, exc=urllib.error.URLError("down"))
    with pytest.raises(Q20Error):
        OllamaClient().chat("m", [])


def test_non_json_response_becomes_q20error(monkeypatch):
    def fake(req, timeout=None):
        return _FakeResp(b"not json at all")
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(Q20Error):
        OllamaClient().chat("m", [])


def test_base_url_trailing_slash_is_trimmed():
    assert OllamaClient("http://h:11434/")._base == "http://h:11434"
