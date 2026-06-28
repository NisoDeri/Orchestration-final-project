"""The LLM-backed Player brain — emits the MCQ batch and the final guess.

The Player reads only the public view (hint + chain), fires ``n_questions`` MCQs in
one batch, then guesses the opening sentence + associative word from the answered
questions. Every LLM call is gatekept; parsing is tolerant; the client is injected so
tests run with a fake client and no network. If the model under-produces questions,
we pad with safe fillers so the batch is always exactly ``n_questions`` long.
"""

from q20.agents import protocol
from q20.game.round import Guess, Question


class PlayerAgent:
    """LLM Player: one batch of MCQs, then a final guess. All calls gatekept."""

    role = "player"

    def __init__(self, client, gatekeeper, model_cfg, n_questions: int, n_options: int):
        self._client = client
        self._gate = gatekeeper
        self._model = model_cfg
        self._n = n_questions
        self._opts = n_options

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

    def _filler(self, view: dict) -> Question:
        chain = view.get("chain") or ["topic"]
        opts = [str(chain[i % len(chain)]) for i in range(max(1, self._opts))]
        return Question(text="Is it related to the chain?", options=opts)

    def ask(self, view: dict) -> list[Question]:
        """Emit exactly ``n_questions`` MCQs (LLM-written, padded if short)."""
        try:
            text = self._chat(protocol.ask_prompt(view, self._n, self._opts))
            parsed = protocol.parse_questions(text, self._opts)
        except Exception:  # noqa: BLE001
            parsed = []
        questions = [Question(text=q["text"], options=q["options"]) for q in parsed][: self._n]
        while len(questions) < self._n:
            questions.append(self._filler(view))
        return questions

    def guess(self, view: dict, qa: list[dict]) -> Guess:
        """Guess the opening sentence + associative word from the answered questions."""
        try:
            text = self._chat(protocol.guess_prompt(view, qa))
            g = protocol.parse_guess(text)
        except Exception:  # noqa: BLE001
            g = {"opening_sentence": "", "associative_word": ""}
        return Guess(opening_sentence=g["opening_sentence"], associative_word=g["associative_word"])
