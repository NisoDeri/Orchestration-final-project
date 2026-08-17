"""Pure rules for Beacon Hunt."""

from __future__ import annotations

from dataclasses import replace

from .model import Action, GameState, MoveResult, Player, Position

_DELTAS: dict[Action, tuple[int, int]] = {
    Action.NORTH: (-1, 0),
    Action.SOUTH: (1, 0),
    Action.EAST: (0, 1),
    Action.WEST: (0, -1),
}


def _inside(size: int, position: Position) -> bool:
    return 0 <= position[0] < size and 0 <= position[1] < size


def legal_actions(state: GameState, player: Player) -> tuple[Action, ...]:
    """Return movement plus the two game actions available this turn."""
    origin = state.position(player)
    movement = tuple(
        action
        for action, delta in _DELTAS.items()
        if _inside(state.board_size, (origin[0] + delta[0], origin[1] + delta[1]))
    )
    return movement + (Action.STAY, Action.SCAN, Action.CLAIM)


def apply_action(state: GameState, player: Player, action: Action) -> MoveResult:
    """Apply one action without I/O or randomness."""
    if action not in legal_actions(state, player):
        raise ValueError(f"illegal action {action!r} for {player.value}")

    position = state.position(player)
    if action in _DELTAS:
        delta = _DELTAS[action]
        position = (position[0] + delta[0], position[1] + delta[1])

    claimed_beacon = None
    claimed = dict(state.claimed)
    if action is Action.CLAIM and position in state.beacons:
        already_claimed = any(position in values for values in state.claimed.values())
        if not already_claimed:
            claimed[player] = frozenset((*claimed[player], position))
            claimed_beacon = position

    positions = dict(state.positions)
    positions[player] = position
    next_state = replace(state, turn=state.turn + 1, positions=positions, claimed=claimed)
    finished = next_state.turn >= 30 or any(next_state.score(p) >= 2 for p in Player)
    return MoveResult(next_state, action, player, position, claimed_beacon, finished)
