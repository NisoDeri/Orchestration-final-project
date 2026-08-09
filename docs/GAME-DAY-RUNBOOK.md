# GAME-DAY RUNBOOK — one counted league game, step by step

Group **nis-yar1** (Nissim Deri, Yarden Tziar). This is the copy-paste checklist a human follows
to play **one pairing** end-to-end. It is the operational floor under `planning/LEAGUE-OPS.md`
(policy + WhatsApp templates) and the pod's `reference/copthief-league-protocol/docs/PAIRING-PLAYBOOK.md`
(lifecycle). When those disagree with a live instruction here, stop and reconcile before playing.

**Our defaults (what we ship):** dialects = **reference commit** (`SHA256(canonical_json(payload)|nonce)`)
+ **subtractive scent** (`max(0, τ−0.10)`, radial emit); setting = **New York**. Every one of these is
**negotiable and must be AGREED** — we align to the opponent, we do not impose. Turn order is fixed:
**thief moves first, unconditionally.**

**Addressing has NO `--peer` flag.** A peer is wired entirely from `config/<role>/game.toml`:
`[network] my_port` (the port our server listens on) + `[network] opponent_url` (the opponent's
tunnel URL, path-terminated in `/mcp`). Editing those two lines is how we "dial".

Paths used below (run from repo root):
- vectors gate: `python reference/copthief-league-protocol/verify_vectors.py`
- sparring doctor: `python -m sparring.cli doctor --peer <url>` (run inside `reference/copthief-league-protocol/`)
- artifact gate: `python tools/check_artifacts.py <our-bundle>` (kit at `reference/copthief-league-protocol/tools/check_artifacts.py`)

---

## 0 — PRE (T-30 min): agree the terms, open the tunnel, verify, spar

**0.1 Agree all 14 shared terms + the setting.** Fill the LEAGUE-OPS §5(b) form with the opponent.
Nothing plays until every row matches BOTH sides byte-for-byte (`verify_peer` enforces exact dict
equality — a mismatch is a hard refuse, not a bargaining round).

| # | Term (`game.json` key) | Our default |
|---|---|---|
| 1 | board size (`board_and_agents.grid_size`) | 7 |
| 2 | smell grid (`pheromones.pheromone_grid_size`) | 5 |
| 3 | scent decay (`pheromones.pheromone_decay`) | 0.1 |
| 4 | scent emit / center (`pheromones.pheromone_center_intensity`) | 0.9 |
| 5 | min center (`pheromones.pheromone_min_center_intensity`) | 0.5 |
| 6 | max steps / survival (`movement_and_barriers.max_moves` = `survival_threshold`) | 35 |
| 7 | max barriers (`movement_and_barriers.max_barriers`) | 14 |
| 8 | setting (`world.map_area`) | "New York" — **align to opponent** |
| 9 | hint max words (`world.hint_max_words`) | 15 |
| 10 | thief start (`board_and_agents.thief_start`) | [3, 3] |
| 11 | cop start (`board_and_agents.cop_start`) | [0, 0] |
| 12 | num_games (`network_and_league.num_games`) | 6 (fixed) |
| 13 | commit dialect (`crypto.dialect`) | reference |
| 14 | scent dialect (`pheromones.dialect`) | reference (subtractive) |

Also lock the rule-23 scent SHA (formula text + one worked 5×5 decay tick, both sides hash it) and
the crash rule (technical loss 0/0, audit still runs). Record `agreed_between: ["nis-yar1", "<opp>"]`
(sorted). Write the agreed file to `config_<game_id>_g<NN>.json`, exchange its `config_sha256`, and
proceed only on an exact match.

**0.2 Open a tunnel** (pick one; both terminate in `/cop/mcp` and `/thief/mcp`):
- **Fresh ngrok:** one command per role —
  `ngrok http --url=<cop-domain> 8802` (police) and `ngrok http --url=<thief-domain> 8801` (thief).
- **Free named Cloudflare tunnel:** one tunnel, path-routed
  `https://<host>/cop/mcp → localhost:8802` and `https://<host>/thief/mcp → localhost:8801`.

**0.3 Point our configs at the opponent.** For EACH role we will run, edit `config/<role>/game.toml`:
- `[network] opponent_url` → the opponent's tunnel URL for the role we are dialing (their **thief**
  URL when we play cop; their **cop** URL when we play thief), path ending `/mcp`.
- `[network] my_port` → 8802 for police, 8801 for thief (defaults; leave unless the port is held).

**0.4 Gate our bytes + spar the peer:**
```
python reference/copthief-league-protocol/verify_vectors.py          # our crypto/scent = kit vectors
python -m sparring.cli doctor --peer <opponent-role-url>             # is their URL a playable peer?
```
`verify_vectors.py` must print all-pass. `doctor` classifies the opponent edge: a `406` to a browser
GET = ready; `502` = edge up, no peer yet (normal before T); `421`/`530` = tunnel misconfig (fix at
the tunnel, §Troubleshooting). Do not announce READY until both are green.

**0.5 Friendlies FIRST.** Play at least one full uncounted series against this opponent before any
counted run (`email.enabled = false`, both sides report to their own inboxes only). A counted game is
armed only after a clean friendly both ways — see §1. Never gamble the one counted slot on an unproven pairing.

---

## 1 — ARM (only after a clean friendly)

1. Decide **which role we take in sub-game 1** and set `[game] sub_game_number = 1` + the correct
   `--role`. Roles alternate across the 6 sub-games; confirm the sub-game→role map with the opponent
   (LEAGUE-OPS §1 / PAIRING-PLAYBOOK Stage 3).
2. Confirm the **Gmail OAuth token** is valid now (dry-run the HW6 sender's refresh; send-only scope).
   Re-auth now if expired — never mid-game.
3. `[email] enabled` **stays `false`** through every friendly and flips to `true` **only** for the
   counted run, and only after the token check passes. An armed counted run that cannot deliver the
   league report must refuse to play, not discover the dead rail after sub-game 6.

---

## 2 — PLAY

1. Servers up by T-5. Start our peer (one process per role we own this window):
   ```
   python -m pursuit peer --role police --config-dir config/police --gui
   python -m pursuit peer --role thief  --config-dir config/thief  --gui
   ```
   (`--config-dir` defaults to `config/<role>`, so it may be omitted.)
2. The clock starts **at handshake** — do not dawdle after launch. **Thief moves first.**
3. Watch the GUI:
   - Status line WAITING→THINKING→PLAYING. A stuck WAITING past the poll interval = the pipe is down.
   - Belief **heatmap** evolving (also the mandatory screenshot — capture at least one clean frame).
   - Step counter vs the 35 ceiling; barrier count vs 14; our scent deposits.
   - Watchdog panel: last-message age vs the 60 s freeze threshold.
4. A human pause past the agreed turn timeout is indistinguishable from a freeze = **0/0 technical
   loss**. If a pause is truly needed, announce it on WhatsApp, get an explicit "ok", resume well
   inside the window. On a tunnel flap restart **only the tunnel** (same hostname = session resumes),
   never the peer process.

---

## 3 — SETTLE

1. At game end AuditPayloads exchange automatically. Run our replay verifier on OUR log:
   ```
   python -m pursuit replay logs/<group_id>/log_<game_id>_g<NN>.json --no-gui
   ```
   Require **"Verified OK"**. Re-hash their revealed records against their committed hashes; any
   mismatch = `technical_loss` 0/0 for that sub-game (still reported).
2. Gate our four artifacts BEFORE emailing:
   ```
   python reference/copthief-league-protocol/tools/check_artifacts.py <our-counted-bundle>
   ```
3. **Consensus check.** Both sides' independently-emitted result files must agree byte-identically on
   the consensus subset. Confirm the consensus signature **חתימת_קונסנזוס_משותפת**
   (`mutual_agreement.sha256`) matches the opponent's. **A mismatch = 0/0 to BOTH groups — do NOT
   send until it matches.** If it differs, diff the canonical consensus strings
   (`{game_id, aggregate, trimmed sub-game rows}`, `sort_keys`, `ensure_ascii=False`), fix the
   diverging field, re-emit; never negotiate prose.
4. Only once the signature matches: **both sides email the SAME result JSON separately** (JSON as the
   attachment, never free text) to **rmisegal+uoh26finalgame@gmail.com**. Free text, a missing mail,
   or contradictory reports = 0 to both. Confirm on WhatsApp that both mails are out ("CONFIRMED + SENT").

---

## 4 — EVIDENCE

Capture and commit before closing out the pairing:
- **GUI heatmap** screenshot — at least one clean per-game frame (mandatory README artifact).
- **Replay "Verified OK"** screenshot from the §3.1 run.
- Commit + push the four artifacts (config, declaration, log, result) + the ledger row (opponent,
  date, counted, result, diversity reward). An uncommitted artifact is invisible evidence.
- De-arm: `[email] enabled = false`, next `sub_game_number` reset for the next pairing.

---

## TROUBLESHOOTING

| Symptom | Likely cause | What to check / do |
|---|---|---|
| Opponent **refuses at handshake** ("terms differ") | one of the 14 terms or a dialect not byte-identical | Re-diff the §0.1 form field-by-field incl. types; compare `config_sha256`; confirm both `crypto.dialect` and `pheromones.dialect` match. Refuse-to-play is correct until fixed — do not approximate. |
| **Port held** (server won't bind 8801/8802) | stale peer process / another listener | Kill the old process; confirm the port is free; if it must change, update `[network] my_port` AND the opponent's `opponent_url` to the new port, then re-exchange. |
| `doctor` shows **502** before T | edge up, no peer behind it | Normal pre-handshake. Permanent 502 = tunnel has no ingress: restart the tunnel process, re-run doctor. |
| `doctor` shows **421** | host-header guard | Fix at the tunnel (`--host-header=rewrite` / `httpHostHeader`) — no code change. |
| `doctor` shows **530 / connection refused** | DNS or no tunnel process | Restart the tunnel; confirm the hostname resolves from an outside network (phone on cellular). |
| **Timeout / stuck WAITING** mid-game | pipe down, or opponent slow | Transport retries 1 s×60 s and our deadline resets on every received message, so a slow-but-alive peer never times us out. Restart only the tunnel, not the peer. Past the watchdog threshold, treat as a crash: extract the log, declare 0/0, run the audit anyway, both email the 0/0 JSON. |
| **Audit disagreement / consensus mismatch** | one side's serializer or a divergent field | Do NOT email. Re-run `check_artifacts.py`; diff the canonical consensus strings and the named diverging field; timestamps/key-order/envelope prose may differ, but scores, `game_uid`, all four `github_commit`, and חתימת_קונסנזוס_משותפת must be identical. Re-emit until the signature matches; a provable hash mismatch = 0/0 both, still reported. |
| **Email won't send** on the counted run | expired OAuth token / `enabled` still false | Never happens if §1.2 preflight passed. Re-auth send-only scope; confirm `[email] enabled = true` and `recipient = rmisegal+uoh26finalgame@gmail.com`. An armed run that cannot deliver must refuse, not play. |
