"""Round data structures: the judge's secret spec, the player's batch, and a guess.

These are plain, serializable carriers shared by the in-process SDK and (later) the
MCP wire. ``RoundSpec`` holds the answer the judge must NOT leak; the public view it
publishes is just ``hint`` + ``chain``.
"""

from dataclasses import dataclass, field

from q20.game.corpus import Paragraph


@dataclass(frozen=True)
class Question:
    """One multiple-choice question with exactly ``options`` answers."""

    text: str
    options: list[str]


@dataclass(frozen=True)
class RoundSpec:
    """The judge's full secret state for a round (answer included)."""

    paragraph: str
    opening_sentence: str
    associative_word: str
    hint: str
    chain: list[str]

    @staticmethod
    def from_paragraph(p: Paragraph) -> "RoundSpec":
        return RoundSpec(
            paragraph=p.paragraph,
            opening_sentence=p.opening_sentence,
            associative_word=p.associative_word,
            hint=p.hint,
            chain=list(p.chain),
        )

    def public_view(self) -> dict:
        """What the judge publishes — the answer (paragraph/sentence/word) stays hidden."""
        return {"hint": self.hint, "chain": list(self.chain)}


@dataclass(frozen=True)
class Guess:
    """The player's final answer: the opening sentence + the associative word."""

    opening_sentence: str
    associative_word: str


@dataclass
class RoundState:
    """Mutable record of one round as it progresses (for logging/replay)."""

    spec: RoundSpec
    questions: list[Question] = field(default_factory=list)
    answers: list[int] = field(default_factory=list)
    guess: Guess | None = None
