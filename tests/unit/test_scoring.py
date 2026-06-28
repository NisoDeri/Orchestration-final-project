"""Unit tests for the pure referee: determine_outcome + score."""

from q20.constants import SCORE, Outcome, Role
from q20.game.round import Guess, RoundSpec
from q20.game.scoring import determine_outcome, score

_SPEC = RoundSpec(
    paragraph="p", opening_sentence="The cat sat on the mat.",
    associative_word="feline", hint="h", chain=["a", "b"],
)


def _guess(s, w):
    return Guess(opening_sentence=s, associative_word=w)


def test_both_correct_is_win():
    out = determine_outcome(_guess("The cat sat on the mat.", "feline"), _SPEC)
    assert out is Outcome.WIN


def test_one_correct_is_tie():
    assert determine_outcome(_guess("The cat sat on the mat.", "wrong"), _SPEC) is Outcome.TIE
    assert determine_outcome(_guess("wrong", "feline"), _SPEC) is Outcome.TIE


def test_none_correct_is_loss():
    assert determine_outcome(_guess("nope", "nope"), _SPEC) is Outcome.LOSS


def test_matching_is_normalized():
    out = determine_outcome(_guess("  the CAT sat on the mat!! ", "FELINE."), _SPEC)
    assert out is Outcome.WIN


def test_empty_guess_is_loss():
    assert determine_outcome(_guess("", ""), _SPEC) is Outcome.LOSS


def test_score_uses_default_constants():
    pts = score(Outcome.WIN)
    assert pts[Role.PLAYER.value] == SCORE[Outcome.WIN]
    assert pts[Role.JUDGE.value] == SCORE["judge"]


def test_score_reads_config_grid(cfg):
    pts = score(Outcome.TIE, cfg)
    grid = cfg.setup["game"]["scoring"]
    assert pts[Role.PLAYER.value] == grid["tie"]
    assert pts[Role.JUDGE.value] == grid["judge"]
