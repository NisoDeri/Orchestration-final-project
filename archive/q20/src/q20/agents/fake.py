"""Deterministic, network-free Judge/Player used by tests, CI, and `--fake` demos.

They honor the exact same contract as the LLM brains:
  * Judge: ``select(corpus, rng) -> RoundSpec`` and ``answer(spec, questions) -> [int]``
  * Player: ``ask(view) -> [Question]`` and ``guess(view, qa) -> Guess``
The FakePlayer is a *perfect* player — it reconstructs the answer from the chain /
the hint so a full round runs reproducibly with no Ollama/MCP and lands a WIN, proving
the whole pipeline end-to-end. Difficulty is irrelevant here; correctness of wiring is.
"""

import random

from q20.game.corpus import Corpus
from q20.game.round import Guess, Question, RoundSpec


class FakeJudge:
    """Picks a paragraph deterministically and answers every question with index 0."""

    role = "judge"

    def select(self, corpus: Corpus, rng: random.Random) -> RoundSpec:
        return RoundSpec.from_paragraph(corpus.sample(rng))

    def answer(self, spec: RoundSpec, questions: list[Question]) -> list[int]:  # noqa: ARG002
        # Deterministic: always choose the first option. The engine logs these; the
        # provisional rule scores the final guess, not per-question correctness.
        return [0 for _ in questions]


class FakePlayer:
    """Emits N filler MCQs, then guesses the answer perfectly from the public view."""

    role = "player"

    def __init__(self, n_questions: int, n_options: int):
        self._n = n_questions
        self._opts = n_options

    def ask(self, view: dict) -> list[Question]:
        chain = view.get("chain") or ["?"]
        opts = [str(chain[i % len(chain)]) for i in range(self._opts)]
        return [Question(text=f"Is the theme related to '{chain[i % len(chain)]}'?",
                         options=list(opts)) for i in range(self._n)]

    def guess(self, view: dict, qa: list[dict]) -> Guess:  # noqa: ARG002
        # A perfect deterministic player: the FakeJudge exposes the answer on the view
        # so the pipeline reaches a scored WIN without any model. Live players infer it.
        return Guess(
            opening_sentence=view.get("_answer_sentence", ""),
            associative_word=view.get("_answer_word", ""),
        )
