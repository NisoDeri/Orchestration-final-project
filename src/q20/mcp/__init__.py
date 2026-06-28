"""MCP transport for q20 — expose the Judge/Player protocol over FastMCP.

The same injected agents that drive the in-process SDK (``sdk.run_round``) are
served here over **streamable-http** so groups can play each other across the wire
in the league. ``judge_server`` owns the secret ``RoundSpec`` (never leaked);
``player_server`` emits the MCQ batch + final guess; ``client`` is the thin
client-side counterpart and a wire-faithful ``run_round_over_mcp`` orchestrator.

``fastmcp`` is imported lazily inside ``build``/``main``/the client so the rest of
the package (and its unit tests) never need it installed.
"""
