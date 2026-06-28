"""Thin ``fastmcp.Client`` wrappers — the OVER-THE-WIRE counterpart to the SDK.

``JudgeClient`` / ``PlayerClient`` each method is one genuine client->server
round-trip to a running FastMCP streamable-http server. ``run_round_over_mcp``
drives one league match purely through those tool calls — publish -> ask ->
answer -> guess -> commit -> reveal -> score — and assembles the SAME canonical
log as ``sdk.run_round``, so a wire game is verifiable as real traffic, not an
in-process shortcut. ``fastmcp`` is imported lazily inside ``_client``.
"""

import asyncio
import logging

from q20.game.round import Guess, RoundSpec
from q20.game.scoring import determine_outcome, score
from q20.sdk.sdk import assemble_log

_LOG = logging.getLogger("q20.mcp.client")


class _Base:
    """Shared lazy ``fastmcp.Client`` round-trip plumbing."""

    def __init__(self, url: str):
        self.url = url

    def _client(self):
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        return Client(StreamableHttpTransport(self.url))

    async def _call(self, tool: str, args: dict | None = None):
        async with self._client() as c:
            res = await c.call_tool(tool, args or {})
        _LOG.info("MCP %s %s -> %r", tool, args or {}, res.data)
        return res.data


class JudgeClient(_Base):
    """Calls a running q20 judge server."""

    async def publish(self) -> dict:
        return await self._call("publish")

    async def answer(self, questions: list[dict]) -> list[int]:
        data = await self._call("answer", {"questions": questions})
        return [int(i) for i in data.get("answers", [])]

    async def commit_guess(self) -> dict:
        return await self._call("commit_guess")

    async def reveal(self) -> dict:
        return await self._call("reveal")


class PlayerClient(_Base):
    """Calls a running q20 player server."""

    async def ask(self, view: dict) -> list[dict]:
        data = await self._call("ask", {"view": view})
        return list(data.get("questions", []))

    async def guess(self, view: dict, qa: list[dict]) -> dict:
        return await self._call("guess", {"view": view, "qa": qa})


async def run_round_over_mcp(cfg, judge_url: str, player_url: str) -> dict:
    """Play one Judge-vs-Player round across the wire; return the canonical log."""
    judge, player = JudgeClient(judge_url), PlayerClient(player_url)
    view = await judge.publish()
    questions = await player.ask(view)
    answers = await judge.answer(questions)
    qa = [{"text": q.get("text", ""), "options": list(q.get("options", [])),
           "chosen": answers[i] if i < len(answers) else 0}
          for i, q in enumerate(questions)]
    guess_d = await player.guess(view, qa)
    await judge.commit_guess()
    truth = await judge.reveal()

    spec = RoundSpec(paragraph="", opening_sentence=truth.get("opening_sentence", ""),
                     associative_word=truth.get("associative_word", ""),
                     hint=view.get("hint", ""), chain=list(view.get("chain", [])))
    guess = Guess(opening_sentence=guess_d.get("opening_sentence", ""),
                  associative_word=guess_d.get("associative_word", ""))
    outcome = determine_outcome(guess, spec)
    return assemble_log(cfg, spec, qa, guess, outcome, score(outcome, cfg))


def play_over_mcp(cfg, judge_url: str, player_url: str) -> dict:
    """Synchronous entry point for the CLI: drive one wire round."""
    return asyncio.run(run_round_over_mcp(cfg, judge_url, player_url))
