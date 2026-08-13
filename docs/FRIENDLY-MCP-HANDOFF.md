# Friendly MCP Handoff for Itay / bestteam

We are group `nis-yar1`. We want to run a non-counted friendly P2P match with `bestteam`.

This friendly is an honest demo. It must not be reported to the lecturer, must not be counted, and should not intentionally reveal or learn best counted-game strategy.

## MCP Server Requirements

Please expose an MCP streamable-HTTP endpoint ending in `/mcp`, for example:

```text
https://<your-public-domain>/mcp
```

Your MCP server must provide these game tools with these argument keys:

```json
{
  "negotiate": { "message": {} },
  "receive_turn": { "message": {} },
  "submit_audit": { "payload": {} }
}
```

`receive_control` is optional. Since `bestteam` confirmed it is not supported, we will coordinate readiness, endpoint URL, SHAs, and start timing in chat instead of calling that tool.

If you use separate fixed-role endpoints, expose both and tell us which is which. If you use one unified endpoint, `/mcp` must route correctly for the role you play.

## Optional Control Message Format

If a future endpoint supports `receive_control`, the body sent to `receive_control` should be a JSON object under the `message` argument:

```json
{
  "kind": "status",
  "sender": "police",
  "sub_game_number": 1,
  "status": "HELLO",
  "step_budget": 30.0,
  "payload": {
    "from_group_id": "nis-yar1",
    "to_group_id": "bestteam",
    "message": "Friendly coordination ping. Please ACK with TERMS_ACK when ready."
  }
}
```

Required fields:

- `kind`: one of `enable`, `status`, `restart`, `quit`
- `sender`: one of `police`, `thief`

Optional fields:

- `sub_game_number`: integer or `null`
- `status`: string or `null`
- `step_budget`: number or `null`
- `payload`: object or `null`

Our parser tolerates extra fields on control messages, but please keep the fields above for compatibility.

## Game JSON Format

Use [friendly_mcp_formats.json](friendly_mcp_formats.json) as the source template. It has been adapted to your `schema_version: "1.2"` format from `game.json`.

Important: before starting, both teams must confirm the exact same `game.json` and the same `game_json_sha256`. Do not add or remove fields after the hash is agreed.

The agreed friendly `game.json` should be this shape:

```json
{
  "agreed_between": ["bestteam", "nis-yar1"],
  "board_and_agents": {
    "axis_origin_corner": "top-left",
    "axis_start_index": 0,
    "cop_start": [0, 0],
    "grid_size": 7,
    "num_agents": 2,
    "thief_start": [3, 3]
  },
  "capture": {
    "resolution": "after_moves",
    "stay_counts_as_move": false,
    "swap_is_capture": true
  },
  "movement_and_barriers": {
    "max_barriers": 14,
    "max_moves": 35,
    "move_set": ["N", "S", "E", "W", "STAY"],
    "seal_barrier_cell": true,
    "survival_threshold": 35
  },
  "network_and_league": {
    "diversity_reward": 10,
    "max_games_per_team": 10,
    "min_games_to_pass": 2,
    "num_games": 6,
    "response_timeout_sec": 30,
    "token_budget_per_series": 200000,
    "watchdog_timeout_sec": 60
  },
  "pheromones": {
    "decay_model": "multiplicative",
    "field_includes_current_turn": true,
    "pheromone_center_intensity": 0.9,
    "pheromone_decay": 0.1,
    "pheromone_grid_size": 5,
    "seal_scent_digest": true
  },
  "rate_limiter_gatekeeper": {
    "concurrent_requests": 2,
    "max_retries": 3,
    "queue_depth": 100,
    "requests_per_minute": 30,
    "retry_backoff_sec": 5
  },
  "schema_version": "1.2",
  "scoring": {
    "capture_cop": 20,
    "capture_thief": 5,
    "survival_cop": 5,
    "survival_thief": 10,
    "technical_loss": 0,
    "tie_score": 2
  },
  "version": "1.00",
  "world": {
    "hint_max_words": 15,
    "map_area": "New York"
  }
}
```

Notes:

- Your downloaded `game.json` had `agreed_between: ["bestteam"]`; for the shared match file, please confirm whether we should use `["bestteam", "nis-yar1"]`.
- This format uses `pheromones.decay_model = "multiplicative"`, so we should run with `--scent-dialect multiplicative_book_v1` unless both teams explicitly agree otherwise.
- Our runtime can accept this `1.2` format even though it omits `crypto.dialect` and `pheromone_min_center_intensity`.

## Please Send Us

- your MCP endpoint ending in `/mcp`
- confirmation that `receive_control` is not supported and we should coordinate in chat
- whether you use one unified endpoint or separate cop/thief endpoints
- your expected full 40-character Git commit SHA
- your GitHub repo link
- your friendly email recipients
- confirmation this is friendly, not counted
- confirmation that the `game.json` above is byte-identical to your intended format, or send the exact file you want us both to use
- the `game_json_sha256` you compute

## Starting the Friendly

For `bestteam`, we agreed on block scheduling:

- sub-games 1, 2, 3: `bestteam` cop vs `nis-yar1` thief
- sub-games 4, 5, 6: `bestteam` thief vs `nis-yar1` police

Our run commands:

```powershell
python -m pursuit peer --role thief --config-dir config/thief --games 3 --fixed-role --scent-dialect multiplicative_book_v1 --mode friendly
```

```powershell
python -m pursuit peer --role police --config-dir config/police --games 3 --fixed-role --scent-dialect multiplicative_book_v1 --mode friendly
```

Together these cover all six sub-games. Our `config/thief/game.toml` declares fixed-role sub-games `[1, 2, 3]`; our `config/police/game.toml` declares `[4, 5, 6]`. We will keep `game.mode = "friendly"` unless both teams explicitly agree to a counted game later.

## Friendly Reporting Rules

After all six sub-games finish, both teams should verify the same aggregated result JSON:

- one aggregate over all six sub-games
- `links.github` includes both teams
- every sub-game row has full 40-character `github_commit` values for both groups
- totals recompute from rows
- audits are `true` for clean games

Friendly report email:

- sender on our side: `yardentziar@gmail.com`
- lecturer is not included
- body is the full pretty-printed result JSON only
- attachment is exactly one file: `result_<game_id>.json`

Subject:

```text
FRIENDLY P2P league SERIES result - <game_id> - winner=<winner_group> - <groupA>:<points> <groupB>:<points>
```

## Important Safety Rules

- Do not intentionally throw games.
- Do not falsify reports.
- Friendly games are honest non-counted demos.
- Friendly mode should not reveal our best counted strategy.
- Friendly mode should not be used to learn opponent strategy.
- Counted games require explicit agreement before running with `--mode counted`.
- Counted reports include the lecturer only after explicit counted agreement.
