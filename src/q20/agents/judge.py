"""The LLM-backed Judge brain — language at the edges, engine stays deterministic.

The Judge picks a paragraph (deterministic corpus draw, not the LLM) and answers the
player's MCQs via a gatekept Ollama call. Selection is engine-side on purpose: the
LLM never invents the secret, it only *answers*, so the referee's truth is stable.
The LLM client is injected, so tests drive it with a fake client and no network.
"""

import random

from q20.agents import protocol
from q20.game.corpus import Corpus
from q20.game.round import Question, RoundSpec


class JudgeAgent:
    """LLM Judge: deterministic selection + LLM answers, all calls gatekept."""

    role = "judge"

    def __init__(self, client, gatekeeper, model_cfg):
        self._client = client
        self._gate = gatekeeper
        self._model = model_cfg

    def _chat(self, messages: list[dict]) -> str:
        result = self._gate.execute(
            self._client.chat,
            self._model.model,
            messages,
            self._model.temperature,
            service="ollama",
            usage_of=lambda r: r.usage,
        )
        return getattr(result, "text", "") or ""

    def select(self, corpus: Corpus, rng: random.Random) -> RoundSpec:
        """Pick the secret paragraph deterministically (no LLM — keeps truth stable)."""
        return RoundSpec.from_paragraph(corpus.sample(rng))

    def answer(self, spec: RoundSpec, questions: list[Question]) -> list[int]:
        """Answer each MCQ with an option index; tolerant of flaky model output."""
        if not questions:
            return []
        payload = [{"text": q.text, "options": q.options} for q in questions]
        try:
            text = self._chat(protocol.answer_prompt(spec.paragraph, payload))
            idx = protocol.parse_answers(text, len(questions))
        except Exception:  # noqa: BLE001 - a flaky local model must not crash the round
            idx = [0 for _ in questions]
        # Clamp each index into its question's option range.
        return [max(0, min(i, len(q.options) - 1)) for i, q in zip(idx, questions, strict=False)]
