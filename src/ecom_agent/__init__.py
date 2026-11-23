"""AI operations agent for a small e-commerce business.

Turns a product photo into a buy/pass verdict, keeps a Google Sheets ledger
in sync, and exposes everything to Claude through an MCP server, with a
human approval gate on every write action.
"""

__version__ = "0.1.0"
