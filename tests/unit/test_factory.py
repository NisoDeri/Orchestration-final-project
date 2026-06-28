"""Unit tests for the agent factory — both the fake and the live (lazy) builders.

``live_agents`` is exercised without a network: it only *constructs* the brains
(an injected Ollama client + gatekeeper), it does not call the model, so building
them proves the wiring and the lazy imports without touching Ollama.
"""

from q20.agents.factory import fake_agents, live_agents
from q20.agents.judge import JudgeAgent
from q20.agents.player import PlayerAgent
from q20.shared.config import ConfigLoader


def test_live_agents_build_without_network(cfg):
    gate = ConfigLoader.build_gatekeeper(cfg)
    agents = live_agents(cfg, gate)
    assert isinstance(agents["judge"], JudgeAgent)
    assert isinstance(agents["player"], PlayerAgent)


def test_live_agents_use_role_specific_models(cfg):
    gate = ConfigLoader.build_gatekeeper(cfg)
    agents = live_agents(cfg, gate)
    # Judge and Player are configured with two different local models on purpose.
    judge_model = cfg.model_for("judge").model
    player_model = cfg.model_for("player").model
    assert agents["judge"]._model.model == judge_model
    assert agents["player"]._model.model == player_model
    assert judge_model != player_model


def test_live_agents_share_one_client(cfg):
    gate = ConfigLoader.build_gatekeeper(cfg)
    agents = live_agents(cfg, gate)
    assert agents["judge"]._client is agents["player"]._client


def test_player_batch_size_from_config(cfg):
    gate = ConfigLoader.build_gatekeeper(cfg)
    player = live_agents(cfg, gate)["player"]
    assert player._n == cfg.setup["game"]["questions"]
    assert player._opts == cfg.setup["game"]["options"]


def test_fake_and_live_share_shape(cfg):
    gate = ConfigLoader.build_gatekeeper(cfg)
    assert set(fake_agents(cfg)) == set(live_agents(cfg, gate)) == {"judge", "player"}
