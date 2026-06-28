"""Pure Player tactics: retrieve the Judge's paragraph from the SHARED corpus, then guess.

The win mechanism for q20: the corpus is shared, so the Player never guesses a verbatim
sentence blind — it RANKS every corpus paragraph by lexical similarity to the Judge's
published hint + associative chain (public info only, no leak), takes the top match, and
reads its opening sentence; the associative word comes from the matched paragraph (or the
chain tail). Deterministic + unit-tested; weights are config-driven so the rule (and
whether the corpus is shared) is a config edit. The 20 answered questions are carried for
future Bayesian refinement (config ``player.use_answers``).
"""

import re

from q20.game.corpus import Corpus
from q20.game.round import Guess

_WORD = re.compile(r"[\w֐-׿]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _similarity(query: set, cand: set) -> float:
    """Jaccard overlap — symmetric, length-robust, no external deps."""
    if not query or not cand:
        return 0.0
    return len(query & cand) / len(query | cand)


def _query_tokens(view: dict) -> set:
    toks = _tokens(view.get("hint", ""))
    for node in view.get("chain", []) or []:
        toks += _tokens(str(node))
    return set(toks)


def _cand_tokens(p) -> set:
    toks = _tokens(p.hint) + _tokens(p.associative_word) + _tokens(p.paragraph)
    for node in p.chain:
        toks += _tokens(str(node))
    return set(toks)


def rank_candidates(view: dict, corpus: Corpus, cfg=None) -> list:
    """Return ``[(Paragraph, score)]`` sorted best-first by similarity to the public view."""
    floor = 0.0
    if cfg is not None:
        floor = float(cfg.setup.get("player", {}).get("prior_floor", 0.0))
    q = _query_tokens(view)
    scored = [(p, _similarity(q, _cand_tokens(p)) + floor) for p in corpus.all()]
    scored.sort(key=lambda ps: ps[1], reverse=True)
    return scored


def best_guess(view: dict, corpus: Corpus, qa: list, cfg=None) -> Guess:  # noqa: ARG001
    """Guess opening sentence + associative word by retrieving the top corpus match."""
    ranked = rank_candidates(view, corpus, cfg)
    chain = view.get("chain") or []
    if not ranked:
        return Guess(opening_sentence="", associative_word=str(chain[-1]) if chain else "")
    top = ranked[0][0]
    word = top.associative_word or (str(chain[-1]) if chain else "")
    return Guess(opening_sentence=top.opening_sentence, associative_word=word)
