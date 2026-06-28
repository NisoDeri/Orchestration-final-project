"""Player retrieval tactics: from the public hint+chain, find the Judge's paragraph."""

from q20.agents import player_tactics
from q20.game.corpus import BundledCorpus, Paragraph

_ITEMS = [
    Paragraph(paragraph="A round-robin tournament pairs every competitor once.",
              opening_sentence="A round-robin tournament pairs every competitor once.",
              associative_word="fairness",
              hint="every team meets every other", chain=["schedule", "pairing", "fairness"]),
    Paragraph(paragraph="Photosynthesis converts sunlight into chemical energy in plants.",
              opening_sentence="Photosynthesis converts sunlight into chemical energy in plants.",
              associative_word="energy",
              hint="leaves capture light", chain=["sun", "chlorophyll", "energy"]),
    Paragraph(paragraph="The referee adjudicates moves over an MCP transport.",
              opening_sentence="The referee adjudicates moves over an MCP transport.",
              associative_word="communication",
              hint="agents talk on a stream", chain=["MCP", "stream", "communication"]),
]
_CORPUS = BundledCorpus(list(_ITEMS))


def test_rank_puts_the_judges_paragraph_first():
    view = _ITEMS[2].chain and {"hint": _ITEMS[2].hint, "chain": _ITEMS[2].chain}
    ranked = player_tactics.rank_candidates(view, _CORPUS)
    assert ranked[0][0].associative_word == "communication"        # the MCP paragraph wins
    assert ranked[0][1] >= ranked[1][1]                            # sorted best-first


def test_best_guess_recovers_sentence_and_word():
    for item in _ITEMS:
        view = {"hint": item.hint, "chain": item.chain}
        g = player_tactics.best_guess(view, _CORPUS, [], None)
        assert g.opening_sentence == item.opening_sentence
        assert g.associative_word == item.associative_word


def test_empty_chain_is_safe():
    g = player_tactics.best_guess({"hint": "", "chain": []}, _CORPUS, [], None)
    assert isinstance(g.opening_sentence, str)  # never raises, always a Guess
