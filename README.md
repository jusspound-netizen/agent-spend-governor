# agent-spend-governor

[![agent-spend-governor MCP server](https://mcprush.com/badge/agent-spend-governor-mcp/card.svg)](https://mcprush.com/to/agent-spend-governor-mcp?ref=badge)

A budget and policy gate for AI agents. Before an agent runs an expensive or
dangerous tool, it asks the Governor: is this within today's budget, is this
tool allowed, does this argument touch a forbidden path? The Governor answers
approved with a nonce, or denied with a reason, and records every decision
to a local SQLite database.

Part of the ghost observability stack: ghost-tracer observes actions,
ghost-reason observes reasoning, and the Governor turns that data into
prevention.

## Tools

| Tool | What it does |
|---|---|
| check_action | Ask permission before running a tool. Reserves the estimated cost and returns a nonce. |
| record_spend | Settle an approved action with its actual cost. Requires the nonce from check_action. |
| get_budget_status | Report today's spend (settled + reserved) against the budget. |

## Policy

On first run the server writes a default policy.json:

    {
      "daily_budget_usd": 5.0,
      "forbidden_tools": ["delete_database", "rm_rf"],
      "forbidden_paths": ["/etc", "C:\\\\Windows"]
    }

## Run it

    pip install -r requirements.txt
    python server.py

Speaks Streamable HTTP on 0.0.0.0:9000, MCP path /mcp.

## Limitations

Budget enforcement relies on the nonce returned by check_action being passed
to record_spend. Abandoned approvals count against the budget as reservations
until a maintenance job cleans them up. Path blocking uses substring matching
on serialized arguments - defense in depth, not a sandbox.

## License

MIT
