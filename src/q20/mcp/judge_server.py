"""Judge MCP server (FastMCP, streamable-http) — the authoritative secret-keeper.

Thin ``@mcp.tool`` wrappers delegate to a single ``JudgeSession`` so all game
logic stays in the agents/engine (none here). The session selects the secret
``RoundSpec`` once and NEVER leaks it: ``publish`` returns only the public view
(hint + chain), ``answer`` returns option indices, and ``reveal`` exposes the
truth only after the player has committed a guess (referee scoring). ``fastmcp``
is imported lazily inside ``build``/``main``.
"""

import random
from pathlib import Path

from q20.constants import Role
from q20.game.corpus import load_corpus
from q20.game.round import Question, RoundSpec
from q20.shared.config import ConfigLoader

_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _ROOT / "config"


class JudgeSession:
    """Holds one judge's secret round state and gates the leak-guarded reveal."""

    def __init__(self, judge, corpus, rng: random.Random):
        self._judge = judge
        self._corpus = corpus
        self._rng = rng
        self.spec: RoundSpec = judge.select(corpus, rng)
        self._guess_committed = False

    def public_view(self) -> dict:
        """The judge's published view — paragraph/sentence/word stay hidden."""
        return self.spec.public_view()

    def answer(self, questions: list[dict]) -> list[int]:
        """Answer a batch of MCQ dicts with option indices (delegates to the agent)."""
        qs = [Question(text=str(q.get("text", "")), options=[str(o) for o in q.get("options", [])])
              for q in questions]
        return self._judge.answer(self.spec, qs)

    def commit_guess(self) -> None:
        """Mark that the player has submitted its guess (unlocks ``reveal``)."""
        self._guess_committed = True

    def reveal(self) -> dict:
        """Disclose the truth — only after a guess is committed (leak-guard)."""
        if not self._guess_committed:
            return {"revealed": False, "reason": "guess not yet committed"}
        return {"revealed": True, "opening_sentence": self.spec.opening_sentence,
                "associative_word": self.spec.associative_word}


def build(session: JudgeSession):
    """Construct a FastMCP app whose tools delegate to ``session``."""
    from fastmcp import FastMCP

    mcp = FastMCP("q20-judge")

    @mcp.tool
    def publish() -> dict:
        """Publish the public view (hint + associative-word chain) for this round."""
        return session.public_view()

    @mcp.tool
    def answer(questions: list) -> dict:
        """Answer the player's batch of MCQs; returns 0-based option indices."""
        return {"answers": session.answer(list(questions))}

    @mcp.tool
    def commit_guess() -> dict:
        """Signal that the player has committed its guess (unlocks reveal)."""
        session.commit_guess()
        return {"ok": True}

    @mcp.tool
    def reveal() -> dict:
        """Reveal the secret answer — refused until a guess is committed."""
        return session.reveal()

    return mcp


def main() -> None:
    cfg = ConfigLoader(_CONFIG_DIR).load()
    from q20.agents.factory import fake_agents, live_agents

    servers = cfg.setup["servers"]
    corpus = load_corpus(cfg, _ROOT)
    rng = random.Random(cfg.setup["game"].get("seed", 7))
    judge = fake_agents(cfg)[Role.JUDGE.value]  # network-free default; live below if desired
    if servers.get("live"):
        judge = live_agents(cfg, ConfigLoader.build_gatekeeper(cfg))[Role.JUDGE.value]
    build(JudgeSession(judge, corpus, rng)).run(
        transport="streamable-http", host=servers["host"], port=servers["judge"]
    )


if __name__ == "__main__":
    main()
