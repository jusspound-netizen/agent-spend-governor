import os
import json
import sqlite3
import pathlib
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("Agent Spend & Policy Governor", host="0.0.0.0", port=9000)

DB_PATH = "governor.db"
POLICY_PATH = "policy.json"

# Default policy if none exists
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

def get_policy():
    p = pathlib.Path(POLICY_PATH)
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_POLICY, indent=2))
        return DEFAULT_POLICY
    return json.loads(p.read_text())

def get_daily_spend():
    import time
    start_of_day = time.time() - (time.time() % 86400)
    with sqlite3.connect(DB_PATH) as conn:
        res = conn.execute("SELECT SUM(cost) FROM spends WHERE timestamp >= ?", (start_of_day,)).fetchone()
        return res[0] or 0.0

@mcp.tool()
def check_action(tool_name: str, arguments: str, estimated_cost: float, ctx: Context) -> str:
    """Ask the Governor for permission before running a tool. Returns 'approved' or 'denied: reason'."""
    policy = get_policy()
    current_spend = get_daily_spend()
    
    # 1. Check Budget
    if current_spend + estimated_cost > policy.get("daily_budget_usd", 5.00):
        return f"denied: Daily budget of ${policy['daily_budget_usd']} exceeded (current spend: ${current_spend:.2f})."
    
    # 2. Check Forbidden Tools
    if tool_name in policy.get("forbidden_tools", []):
        return f"denied: Tool '{tool_name}' is permanently forbidden by policy."
    
    # 3. Check Forbidden Paths (simple string match for demo)
    for path in policy.get("forbidden_paths", []):
        if path in arguments:
            return f"denied: Argument contains forbidden path '{path}'."
            
    return "approved"

@mcp.tool()
def record_spend(tool_name: str, actual_cost: float, ctx: Context) -> str:
    """Log the actual cost of an action after it runs."""
    import time
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO spends (timestamp, tool_name, cost) VALUES (?, ?, ?)", (time.time(), tool_name, actual_cost))
    return f"Logged ${actual_cost:.4f} for {tool_name}."

@mcp.tool()
def get_budget_status(ctx: Context) -> str:
    """Check current daily spend vs budget."""
    policy = get_policy()
    spend = get_daily_spend()
    return f"Spent: ${spend:.2f} / Budget: ${policy.get('daily_budget_usd', 5.00):.2f}"

if __name__ == "__main__":
    init_db()
    mcp.run(transport="streamable-http")
