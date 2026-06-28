"""Minimal local-Ollama chat client (stdlib only) with real token telemetry.

We talk to Ollama's HTTP API directly: every ``/api/chat`` response carries
``prompt_eval_count`` (input tokens) and ``eval_count`` (output tokens), so cost /
effort accounting rests on Ollama's own counters — exact, reproducible, no API key,
no cloud. ``httpx`` is a declared dependency but we use the stdlib here to keep the
client dependency-free; swap-in is trivial behind the same ``chat`` signature.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from q20.shared.cost import Usage
from q20.shared.exceptions import Q20Error


@dataclass
class ChatResult:
    """One model turn: the text plus the token usage Ollama reported."""

    text: str
    usage: Usage
    raw: dict = field(default_factory=dict)


class OllamaClient:
    """Thin synchronous client for a local Ollama server."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 600.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
        num_ctx: int | None = None,
    ) -> ChatResult:
        """Send a chat completion; return text + exact token usage.

        ``messages`` is the standard ``[{"role": ..., "content": ...}]`` list. Raises
        ``Q20Error`` on transport/HTTP failure so the gatekeeper's retry/backoff can
        act on a single project-level exception type.
        """
        options: dict = {"temperature": temperature}
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        payload = json.dumps(
            {"model": model, "messages": messages, "stream": False, "options": options}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Q20Error(f"Ollama request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise Q20Error(f"Ollama returned non-JSON: {exc}") from exc

        text = body.get("message", {}).get("content", "")
        usage = Usage(
            input_tokens=int(body.get("prompt_eval_count", 0)),
            output_tokens=int(body.get("eval_count", 0)),
            model=model,
        )
        return ChatResult(text=text, usage=usage, raw=body)
