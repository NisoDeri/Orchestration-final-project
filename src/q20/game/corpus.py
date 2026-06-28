"""The corpus seam — a pluggable source of target paragraphs.

The ``Corpus`` protocol is the one place the article/dataset source can change
(bundled sample today; provided dataset / Wikipedia / arXiv later) without touching
game logic. ``BundledCorpus`` loads ``data/corpus.sample.json``; ``load_corpus``
picks an implementation from ``config/setup.json:game.corpus.source``.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from q20.shared.exceptions import CorpusError


@dataclass(frozen=True)
class Paragraph:
    """One corpus item: the target text plus the two things the player must guess."""

    paragraph: str
    opening_sentence: str
    associative_word: str
    hint: str
    chain: list[str]

    @staticmethod
    def from_dict(d: dict) -> "Paragraph":
        try:
            return Paragraph(
                paragraph=str(d["paragraph"]),
                opening_sentence=str(d["opening_sentence"]),
                associative_word=str(d["associative_word"]),
                hint=str(d.get("hint", "")),
                chain=[str(w) for w in d.get("chain", [])],
            )
        except KeyError as exc:
            raise CorpusError(f"corpus item missing field: {exc}") from exc


class Corpus(Protocol):
    """A source of target paragraphs."""

    def sample(self, rng: random.Random) -> Paragraph:
        """Return one paragraph chosen with the given RNG (reproducible)."""
        ...

    def all(self) -> list[Paragraph]:
        """Return every paragraph (for league round assignment / inspection)."""
        ...


class BundledCorpus:
    """A corpus backed by a JSON file of paragraph objects."""

    def __init__(self, items: list[Paragraph]):
        if not items:
            raise CorpusError("corpus is empty")
        self._items = items

    @classmethod
    def from_path(cls, path: Path) -> "BundledCorpus":
        p = Path(path)
        if not p.exists():
            raise CorpusError(f"missing corpus file: {p}")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CorpusError(f"invalid JSON in {p}: {exc}") from exc
        items = raw["paragraphs"] if isinstance(raw, dict) else raw
        return cls([Paragraph.from_dict(d) for d in items])

    def sample(self, rng: random.Random) -> Paragraph:
        return rng.choice(self._items)

    def all(self) -> list[Paragraph]:
        return list(self._items)


def load_corpus(cfg, base_dir: Path) -> BundledCorpus:
    """Build the configured corpus (only 'bundled' supported today; pluggable)."""
    spec = cfg.setup["game"]["corpus"]
    source = spec.get("source", "bundled")
    if source != "bundled":
        raise CorpusError(f"unsupported corpus source: {source!r}")
    return BundledCorpus.from_path(Path(base_dir) / spec["path"])
