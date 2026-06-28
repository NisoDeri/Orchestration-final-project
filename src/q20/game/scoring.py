"""The referee's pure scoring — the single, swappable source of truth for outcomes.

``determine_outcome`` is the one rule most likely to change when the brief is
finalized, so it is tiny, pure, and isolated: the player WINS if it gets BOTH the
opening sentence and the associative word, TIES if exactly one, LOSES if none.
``score`` turns that outcome into per-role points using the config grid (falling
back to ``constants.SCORE``). No I/O, no globals — trivially unit-testable.
"""

import re

from q20.constants import SCORE, Outcome, Role
from q20.game.round import Guess, RoundSpec


def _norm(text: str) -> str:
    """Case/space/punctuation-insensitive normalization for fair string matching."""
    return re.sub(r"[^a-z0-9֐-׿ ]", "", text.lower()).strip()


def _matches(guess: str, truth: str) -> bool:
    """True if a guess matches the truth (exact after normalization)."""
    return bool(guess) and _norm(guess) == _norm(truth)


def determine_outcome(guess: Guess, spec: RoundSpec) -> Outcome:
    """Map a player guess against the secret spec to WIN / TIE / LOSS.

    Provisional rule (PRD §4, ``[TBD-confirm]``): both correct -> WIN; exactly one
    -> TIE; neither -> LOSS. Swap this body when the official rule lands.
    """
    sentence_ok = _matches(guess.opening_sentence, spec.opening_sentence)
    word_ok = _matches(guess.associative_word, spec.associative_word)
    hits = sentence_ok + word_ok
    if hits == 2:
        return Outcome.WIN
    if hits == 1:
        return Outcome.TIE
    return Outcome.LOSS


def score(outcome: Outcome, cfg=None) -> dict[str, int]:
    """Per-role points for an outcome, from config (fallback: ``constants.SCORE``).

    The player earns its outcome's points; the judge always earns the flat judge
    bonus for running a clean round (brief: judge +2).
    """
    grid = SCORE
    if cfg is not None:
        grid = cfg.setup["game"]["scoring"]
    player_pts = int(grid[str(outcome)])
    judge_pts = int(grid["judge"])
    return {Role.PLAYER.value: player_pts, Role.JUDGE.value: judge_pts}
