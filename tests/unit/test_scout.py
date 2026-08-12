"""Scouting: greedy prediction, best-response, profile fitting + trust gate."""

from __future__ import annotations

from pursuit.domain.board import Board
from pursuit.strategy import scout

MOVES = ["N", "S", "E", "W", "STAY"]
BOARD = Board(7, MOVES)
NO_BARRIERS: set = set()


def test_predict_greedy_thief_flees_from_cop():
    # thief at centre, cop top-left -> greedy thief steps to the farther-from-cop neighbour
    pred = scout.predict_greedy(BOARD, NO_BARRIERS, (3, 3), (0, 0), opp_is_thief=True)
    assert scout._dist(BOARD, NO_BARRIERS, pred, (0, 0)) >= scout._dist(
        BOARD, NO_BARRIERS, (3, 3), (0, 0))
    assert pred in {(4, 3), (3, 4)}  # both increase Manhattan distance from (0,0)


def test_predict_greedy_cop_chases_thief():
    pred = scout.predict_greedy(BOARD, NO_BARRIERS, (0, 0), (3, 3), opp_is_thief=False)
    assert scout._dist(BOARD, NO_BARRIERS, pred, (3, 3)) <= scout._dist(
        BOARD, NO_BARRIERS, (0, 0), (3, 3))
    assert pred in {(1, 0), (0, 1)}  # both step toward the thief


def test_best_response_chase_leads_to_target():
    moves = BOARD.legal_moves((2, 2), NO_BARRIERS)
    d, cell = scout.best_response(BOARD, NO_BARRIERS, moves, (2, 2), (2, 4), chase=True)
    assert scout._dist(BOARD, NO_BARRIERS, cell, (2, 4)) < scout._dist(
        BOARD, NO_BARRIERS, (2, 2), (2, 4))  # closed the gap toward the predicted square


def test_best_response_flee_opens_distance():
    moves = BOARD.legal_moves((3, 3), NO_BARRIERS)
    d, cell = scout.best_response(BOARD, NO_BARRIERS, moves, (3, 3), (3, 2), chase=False)
    assert scout._dist(BOARD, NO_BARRIERS, cell, (3, 2)) >= scout._dist(
        BOARD, NO_BARRIERS, (3, 3), (3, 2))


def test_greedy_score_flags_a_greedy_thief():
    # a thief that always takes the greedy-flee step scores ~1.0
    cop = [(0, 0)] * 5
    thief = [(3, 3)]
    for _ in range(4):
        thief.append(scout.predict_greedy(BOARD, NO_BARRIERS, thief[-1], (0, 0),
                                          opp_is_thief=True))
    prof = scout.greedy_score(cop, thief, BOARD, NO_BARRIERS, opp_is_thief=True)
    assert prof["greedy_score"] == 1.0 and prof["samples"] == 4


def test_trusted_role_gate():
    good = {"thief": {"greedy_score": 0.9, "samples": 6, "opp_role": "thief"}}
    weak = {"thief": {"greedy_score": 0.4, "samples": 6, "opp_role": "thief"}}
    few = {"thief": {"greedy_score": 0.9, "samples": 2, "opp_role": "thief"}}
    assert scout.trusted_role(good, opp_is_thief=True)
    assert not scout.trusted_role(weak, opp_is_thief=True)
    assert not scout.trusted_role(few, opp_is_thief=True)
    assert not scout.trusted_role(None, opp_is_thief=True)


def test_merge_profiles_sample_weighted():
    a = {"police": {"greedy_score": 1.0, "samples": 2, "opp_role": "police"}}
    b = {"police": {"greedy_score": 0.0, "samples": 2, "opp_role": "police"}}
    merged = scout.merge_profiles(a, b)
    assert merged["police"]["greedy_score"] == 0.5 and merged["police"]["samples"] == 4
