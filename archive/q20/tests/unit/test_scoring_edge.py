"""Extra scoring edge cases: every outcome's config points, Hebrew/punctuation
normalization, whitespace-only guesses, and the judge's flat bonus invariance."""

import pytest

from q20.constants import Outcome, Role
from q20.game.round import Guess, RoundSpec
from q20.game.scoring import determine_outcome, score

_HE = RoundSpec(
    paragraph="פסקה", opening_sentence="פרוטוקול הקשר מחבר סוכנים.",
    associative_word="תקשורת", hint="רמז", chain=["MCP", "נחל"],
)


def _g(s, w):
    return Guess(opening_sentence=s, associative_word=w)


@pytest.mark.parametrize("outcome", [Outcome.WIN, Outcome.TIE, Outcome.LOSS])
def test_score_matches_config_grid_for_each_outcome(cfg, outcome):
    grid = cfg.setup["game"]["scoring"]
    pts = score(outcome, cfg)
    assert pts[Role.PLAYER.value] == grid[str(outcome)]
    assert pts[Role.JUDGE.value] == grid["judge"]


@pytest.mark.parametrize("outcome", [Outcome.WIN, Outcome.TIE, Outcome.LOSS])
def test_judge_bonus_is_invariant_to_outcome(cfg, outcome):
    grid = cfg.setup["game"]["scoring"]
    assert score(outcome, cfg)[Role.JUDGE.value] == grid["judge"]


def test_hebrew_exact_match_is_win():
    assert determine_outcome(_g("פרוטוקול הקשר מחבר סוכנים.", "תקשורת"), _HE) is Outcome.WIN


def test_hebrew_punctuation_is_normalized():
    assert determine_outcome(_g("  פרוטוקול הקשר מחבר סוכנים!! ", "תקשורת..."), _HE) is Outcome.WIN


def test_hebrew_one_correct_is_tie():
    assert determine_outcome(_g("פרוטוקול הקשר מחבר סוכנים.", "שגוי"), _HE) is Outcome.TIE


def test_whitespace_only_guess_is_loss():
    spec = RoundSpec("p", "real sentence.", "word", "h", ["a"])
    assert determine_outcome(_g("   ", "\t"), spec) is Outcome.LOSS


def test_case_and_edge_punctuation_are_ignored():
    spec = RoundSpec("p", "Hello World.", "Flow", "h", ["a"])
    assert determine_outcome(_g("  hello world!! ", "FLOW"), spec) is Outcome.WIN


def test_score_default_grid_without_config():
    from q20.constants import SCORE
    pts = score(Outcome.LOSS)
    assert pts[Role.PLAYER.value] == SCORE[Outcome.LOSS]
    assert pts[Role.JUDGE.value] == SCORE["judge"]
