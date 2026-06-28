"""Player MCP server (FastMCP, streamable-http) — the question/guess brain on the wire.

Thin ``@mcp.tool`` wrappers delegate to a single ``PlayerSession`` wrapping an
injected player agent (Fake or Ollama). ``ask`` turns a published view into the
MCQ batch; ``guess`` turns the answered questions into the final guess. No engine
or scoring logic lives here — the referee (judge_server + SDK) owns truth.
``fastmcp`` is imported lazily inside ``build``/``main``.
"""

from pathlib import Path

from q20.constants import Role
from q20.shared.config import ConfigLoader

_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _ROOT / "config"


class PlayerSession:
    """Adapts an injected player agent to JSON-friendly MCP payloads."""

    def __init__(self, player):
        self._player = player

    def ask(self, view: dict) -> list[dict]:
        """Emit the MCQ batch as a list of ``{text, options}`` dicts."""
        return [{"text": q.text, "options": list(q.options)} for q in self._player.ask(view)]

    def guess(self, view: dict, qa: list[dict]) -> dict:
        """Return the final guess as ``{opening_sentence, associative_word}``."""
        g = self._player.guess(view, qa)
        return {"opening_sentence": g.opening_sentence, "associative_word": g.associative_word}


def build(session: PlayerSession):
    """Construct a FastMCP app whose tools delegate to ``session``."""
    from fastmcp import FastMCP

    mcp = FastMCP("q20-player")

    @mcp.tool
    def ask(view: dict) -> dict:
        """Emit the batch of multiple-choice questions for a published view."""
        return {"questions": session.ask(dict(view))}

    @mcp.tool
    def guess(view: dict, qa: list) -> dict:
        """Guess the opening sentence + associative word from the answered questions."""
        return session.guess(dict(view), list(qa))

    return mcp


def main() -> None:
    cfg = ConfigLoader(_CONFIG_DIR).load()
    from q20.agents.factory import fake_agents, live_agents

    servers = cfg.setup["servers"]
    player = fake_agents(cfg)[Role.PLAYER.value]  # network-free default
    if servers.get("live"):
        player = live_agents(cfg, ConfigLoader.build_gatekeeper(cfg))[Role.PLAYER.value]
    build(PlayerSession(player)).run(
        transport="streamable-http", host=servers["host"], port=servers["player"]
    )


if __name__ == "__main__":
    main()
