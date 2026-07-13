"""Agent construction shared by the CLI and (later) the cross-group MCP bridge.

``live_agents`` builds the Ollama-backed Judge+Player (sharing one client);
``fake_agents`` builds the deterministic test pair. Both return the same
``{"judge": ..., "player": ...}`` shape so the SDK is agnostic to which it drives.
"""

from q20.constants import Role
from q20.shared.ollama_client import OllamaClient


def live_agents(cfg, gatekeeper, corpus=None) -> dict[str, object]:
    """Both live brains, sharing one Ollama client (Judge model != Player model).

    ``corpus`` (the shared article set) is handed to the Player so it can retrieve the
    Judge's paragraph from public info — the real win mechanism. Pass None to fall back
    to LLM-only guessing (e.g. if the rule says the corpus is NOT shared).
    """
    from q20.agents.judge import JudgeAgent
    from q20.agents.player import PlayerAgent

    client = OllamaClient(cfg.ollama_base_url)
    g = cfg.setup["game"]
    shared = cfg.setup.get("player", {}).get("shared_corpus", True)
    return {
        Role.JUDGE.value: JudgeAgent(client, gatekeeper, cfg.model_for(Role.JUDGE.value)),
        Role.PLAYER.value: PlayerAgent(client, gatekeeper, cfg.model_for(Role.PLAYER.value),
                                       int(g["questions"]), int(g["options"]),
                                       corpus if shared else None, cfg),
    }


def fake_agents(cfg) -> dict[str, object]:
    """Deterministic Judge/Player pair (CI / no-GPU path)."""
    from q20.agents.fake import FakeJudge, FakePlayer

    g = cfg.setup["game"]
    return {
        Role.JUDGE.value: FakeJudge(),
        Role.PLAYER.value: FakePlayer(int(g["questions"]), int(g["options"])),
    }
