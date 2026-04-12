"""MCP (Model Context Protocol) server for 4dpocket.

Exposes 10 tools over streamable-HTTP at ``/mcp`` for external LLM agents to
use the user's knowledge base as persistent memory. Authentication via PATs
created in the `/settings` page.
"""

from fourdpocket.mcp.server import build_mcp_app, mcp

__all__ = ["build_mcp_app", "mcp"]
