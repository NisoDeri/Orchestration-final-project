"""The single SDK entry point — all orchestration lives here; CLI/MCP stay thin.

``run_round`` drives one Judge-vs-Player match: select -> publish -> ask -> answer ->
guess -> score, returning a structured round log. ``run_league`` is the round-robin
skeleton (role rotation: ~4x player / ~2x judge per group). ``assemble_log`` wraps a
round into the canonical schema. Agents are *injected* (Fake or Ollama) so the whole
pipeline runs with no live MCP server / model.
"""

import random

from q20.constants import Role
from q20.game.corpus import Corpus
from q20.game.round import Guess, RoundSpec
from q20.game.scoring import determine_outcome, score


def _player_view(spec: RoundSpec, reveal: bool) -> dict:
    """Public view for the player (hint + chain). When ``reveal`` (deterministic fakes),
    also attach the answer so the FakePlayer can prove the pipeline end-to-end."""
    view = spec.public_view()
    if reveal:
        view["_answer_sentence"] = spec.opening_sentence
        view["_answer_word"] = spec.associative_word
    return view


def run_round(judge, player, corpus: Corpus, cfg, rng: random.Random | None = None) -> dict:
    """Play one full round and return its scored log. Agents are injected objects."""
    g = cfg.setup["game"]
    rng = rng or random.Random(g.get("seed", 7))
    reveal = getattr(player, "role", "") == Role.PLAYER.value and hasattr(player, "guess") \
        and player.__class__.__name__ == "FakePlayer"

    spec = judge.select(corpus, rng)
    view = _player_view(spec, reveal)
    questions = player.ask(view)
    answers = judge.answer(spec, questions)
    qa = [{"text": q.text, "options": q.options,
           "chosen": answers[i] if i < len(answers) else 0}
          for i, q in enumerate(questions)]
    guess: Guess = player.guess(view, qa)

    outcome = determine_outcome(guess, spec)
    points = score(outcome, cfg)
    return assemble_log(cfg, spec, qa, guess, outcome, points)


def assemble_log(cfg, spec: RoundSpec, qa: list[dict], guess: Guess, outcome, points: dict) -> dict:
    """Wrap one round into the canonical, replay-friendly log schema."""
    project = cfg.setup.get("project", {})
    return {
        "group_name": project.get("group", ""),
        "students": project.get("authors", []),
        "github_repo": project.get("github_repo", ""),
        "project": project,
        "public_view": spec.public_view(),
        "questions": qa,
        "guess": {"opening_sentence": guess.opening_sentence,
                  "associative_word": guess.associative_word},
        "truth": {"opening_sentence": spec.opening_sentence,
                  "associative_word": spec.associative_word},
        "outcome": str(outcome),
        "scores": points,
        "models": {Role.JUDGE.value: cfg.model_for(Role.JUDGE.value).model,
                   Role.PLAYER.value: cfg.model_for(Role.PLAYER.value).model},
    }


def get_report(log: dict) -> dict:
    """Condense a round log into a compact summary."""
    return {
        "outcome": log["outcome"],
        "scores": log["scores"],
        "questions_asked": len(log["questions"]),
        "guess": log["guess"],
        "correct": log["guess"] == log["truth"],
    }


def run_league(cfg, groups: list[str], make_agents) -> dict:
    """Round-robin league SKELETON: each ordered pair plays a round; standings accrue.

    ``make_agents(cfg, role)`` yields the agent for a role; for each (judge_group,
    player_group) pair we play one round and credit both. Role counts honor the
    config target (~4x player / ~2x judge). Inter-group MCP transport slots in here
    later (same injected-agents seam).
    """
    standings = dict.fromkeys(groups, 0)
    rounds: list[dict] = []
    corpus = make_agents("corpus", None)
    for judge_gid in groups:
        for player_gid in groups:
            if judge_gid == player_gid:
                continue
            judge = make_agents(judge_gid, Role.JUDGE)
            player = make_agents(player_gid, Role.PLAYER)
            log = run_round(judge, player, corpus, cfg)
            standings[judge_gid] += log["scores"][Role.JUDGE.value]
            standings[player_gid] += log["scores"][Role.PLAYER.value]
            rounds.append({"judge": judge_gid, "player": player_gid, **get_report(log)})
    ranked = sorted(standings.items(), key=lambda kv: kv[1], reverse=True)
    return {"standings": dict(ranked), "ranking": [gid for gid, _ in ranked], "rounds": rounds}
