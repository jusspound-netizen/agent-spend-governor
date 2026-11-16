import os
import json
import sqlite3
import time
import uuid
import pathlib
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("Agent Spend & Policy Governor", host="0.0.0.0", port=9000)

DB_PATH = "governor.db"
POLICY_PATH = "policy.json"

DEFAULT_POLICY = {
    "daily_budget_usd": 5.00,
    "forbidden_tools": ["delete_database", "rm_rf"],
    "forbidden_paths": ["/etc", "C:\\Windows"]
}

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                tool_name TEXT,
                cost REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                nonce TEXT PRIMARY KEY,
                created REAL,
                tool_name TEXT,
                estimated REAL,
                status TEXT
            )
        """)

def get_policy():
    p = pathlib.Path(POLICY_PATH)
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_POLICY, indent=2), encoding="utf-8")
        return DEFAULT_POLICY
    return json.loads(p.read_text(encoding="utf-8"))

def get_daily_spend():
    start_of_day = time.time() - (time.time() % 86400)
    with sqlite3.connect(DB_PATH) as conn:
        settled = conn.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM spends WHERE timestamp >= ?",
            (start_of_day,)
        ).fetchone()[0]
        reserved = conn.execute(
            "SELECT COALESCE(SUM(estimated), 0) FROM reservations "
            "WHERE status = 'reserved' AND created >= ?",
            (start_of_day,)
        ).fetchone()[0]
    return settled + reserved

def _forbidden_path_hit(arguments: str, forbidden: list):
    try:
        parsed = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return None
    def walk(obj):
        if isinstance(obj, str):
            yield obj
        elif isinstance(obj, dict):
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                yield from walk(v)
    for value in walk(parsed):
        for bad in forbidden:
            if bad in value:
                return bad
    return None

@mcp.tool()
def check_action(tool_name: str, arguments: str, estimated_cost: float, ctx: Context) -> str:
    """Ask the Governor for permission before running a tool.

    Reserves the estimated cost against today's budget and returns a nonce.
    The caller must pass the nonce to record_spend after the action runs.
    """
    policy = get_policy()
    current_spend = get_daily_spend()

    if current_spend + estimated_cost > policy.get("daily_budget_usd", 5.00):
        return json.dumps({
            "status": "denied",
            "reason": f"Daily budget of ${policy['daily_budget_usd']} exceeded "
                      f"(current: ${current_spend:.2f}, requested: ${estimated_cost:.2f})."
        })
    if tool_name in policy.get("forbidden_tools", []):
        return json.dumps({
            "status": "denied",
            "reason": f"Tool '{tool_name}' is forbidden by policy."
        })
    hit = _forbidden_path_hit(arguments, policy.get("forbidden_paths", []))
    if hit:
        return json.dumps({
            "status": "denied",
            "reason": f"Argument references forbidden path '{hit}'."
        })

    nonce = uuid.uuid4().hex
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO reservations (nonce, created, tool_name, estimated, status) "
            "VALUES (?, ?, ?, ?, 'reserved')",
            (nonce, time.time(), tool_name, estimated_cost)
        )
    return json.dumps({"status": "approved", "nonce": nonce})

@mcp.tool()
def record_spend(nonce: str, actual_cost: float, ctx: Context) -> str:
    """Settle a previously approved action with its actual cost.

    The nonce comes from check_action. A missing, unknown, or already-used
    nonce is rejected and the budget is not changed.
    """
    if actual_cost < 0:
        return json.dumps({"status": "rejected", "reason": "actual_cost must be >= 0."})
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT tool_name, estimated, status FROM reservations WHERE nonce = ?",
            (nonce,)
        ).fetchone()
        if row is None:
            return json.dumps({"status": "rejected", "reason": "Unknown nonce."})
        tool_name, estimated, status = row
        if status != "reserved":
            return json.dumps({"status": "rejected", "reason": "Nonce already settled."})
        conn.execute(
            "UPDATE reservations SET status = 'settled' WHERE nonce = ?",
            (nonce,)
        )
        conn.execute(
            "INSERT INTO spends (timestamp, tool_name, cost) VALUES (?, ?, ?)",
            (time.time(), tool_name, actual_cost)
        )
    delta = actual_cost - estimated
    return json.dumps({
        "status": "recorded",
        "tool_name": tool_name,
        "estimated": estimated,
        "actual": actual_cost,
        "delta": round(delta, 6)
    })

@mcp.tool()
def get_budget_status(ctx: Context) -> str:
    """Report today's spend (settled + reserved) against the budget."""
    policy = get_policy()
    spend = get_daily_spend()
    return json.dumps({
        "spent_usd": round(spend, 4),
        "budget_usd": policy.get("daily_budget_usd", 5.00),
        "remaining_usd": round(policy.get("daily_budget_usd", 5.00) - spend, 4)
    })

if __name__ == "__main__":
    init_db()
    mcp.run(transport="streamable-http")
