"""FastMCP server assembly and tool registration.

Exposes an ASGI app via ``build_mcp_app()`` that the main FastAPI app mounts
at ``/mcp``. All tools are thin wrappers that resolve the calling PAT via the
MCP ``AccessToken`` context and delegate to pure functions in :mod:`fourdpocket.mcp.tools`.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl
from sqlmodel import Session

from fourdpocket.api.api_token_utils import resolve_token
from fourdpocket.db.session import get_engine
from fourdpocket.mcp import tools as tools_mod
from fourdpocket.mcp.auth import PATTokenVerifier
from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.user import User

logger = logging.getLogger(__name__)


def _build_mcp() -> FastMCP:
    verifier = PATTokenVerifier()
    issuer = AnyHttpUrl("http://localhost:4040")
    resource = AnyHttpUrl("http://localhost:4040")
    return FastMCP(
        "4dpocket",
        instructions=(
            "4dpocket is the user's personal knowledge base. "
            "Use these tools as persistent memory: save_knowledge to persist, "
            "search_knowledge to recall, get_entity + get_related_entities to "
            "navigate associations. All calls are scoped to the user's PAT."
        ),
        json_response=True,
        stateless_http=True,
        # FastAPI mounts this app at /mcp; FastMCP defaults to nesting the
        # streamable-HTTP handler under /mcp again, which would expose the
        # endpoint at /mcp/mcp. Anchor it at the mount root so the public URL
        # matches the documented /mcp.
        streamable_http_path="/",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=issuer,
            resource_server_url=resource,
            required_scopes=["mcp"],
        ),
    )


mcp = _build_mcp()


@contextmanager
def _tool_ctx():
    """Yield ``(User, ApiToken, Session)`` for the current tool call.

    Raises :class:`tools_mod.ToolError` if the caller is unauthenticated or
    the PAT has been revoked since the transport layer validated it.
    """
    access = get_access_token()
    if access is None:
        raise tools_mod.ToolError("Authentication required.")

    with Session(get_engine()) as db:
        pat: ApiToken | None = resolve_token(db, access.token)
        if pat is None:
            raise tools_mod.ToolError("Token has been revoked or expired.")
        user = db.get(User, pat.user_id)
        if user is None or user.is_active is False:
            raise tools_mod.ToolError("User account disabled.")
        yield user, pat, db


# ─── Tool registration ────────────────────────────────────────────────────


@mcp.tool()
def search_knowledge(
    query: str,
    limit: int = 20,
    item_type: str | None = None,
    tags: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    collection_id: str | None = None,
) -> dict[str, Any]:
    """Search the user's knowledge base using chunk-level hybrid retrieval.

    Returns the top matches with title, url, summary, and a short snippet.
    Filters: item_type (url|note|image|pdf|code_snippet), tags list, date range
    (after/before, ISO-8601), collection_id.
    """
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.search_knowledge,
            db,
            user,
            pat,
            query=query,
            limit=limit,
            item_type=item_type,
            tags=tags,
            after=after,
            before=before,
            collection_id=collection_id,
        )


@mcp.tool()
def get_knowledge(knowledge_id: str) -> dict[str, Any]:
    """Fetch full detail for a single knowledge item (title, content, tags,
    entities, collections, chunks)."""
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.get_knowledge,
            db,
            user,
            pat,
            knowledge_id=knowledge_id,
        )


@mcp.tool()
def save_knowledge(
    url: str | None = None,
    content: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    collection_id: str | None = None,
) -> dict[str, Any]:
    """Persist a new item to the knowledge base.

    Pass either a ``url`` (which triggers the fetcher) or raw ``content``
    (which creates a note). Optional: title, tags, collection_id.

    Requires an editor-role PAT.
    """
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.save_knowledge,
            db,
            user,
            pat,
            url=url,
            content=content,
            title=title,
            tags=tags,
            collection_id=collection_id,
        )


@mcp.tool()
def update_knowledge(
    knowledge_id: str,
    title: str | None = None,
    content: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
) -> dict[str, Any]:
    """Edit fields on an existing knowledge item. Only fields you pass are
    changed. Tags, when provided, fully replace the existing tag set.

    Requires an editor-role PAT.
    """
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.update_knowledge,
            db,
            user,
            pat,
            knowledge_id=knowledge_id,
            title=title,
            content=content,
            description=description,
            tags=tags,
            is_favorite=is_favorite,
            is_archived=is_archived,
        )


@mcp.tool()
def refresh_knowledge(
    knowledge_id: str, refetch: bool = False
) -> dict[str, Any]:
    """Re-run the enrichment pipeline for an item (re-chunk, re-embed,
    re-extract entities, re-synthesize). Pass ``refetch=true`` to also
    re-download URL content.

    Requires an editor-role PAT.
    """
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.refresh_knowledge,
            db,
            user,
            pat,
            knowledge_id=knowledge_id,
            refetch=refetch,
        )


@mcp.tool()
def delete_knowledge(knowledge_id: str) -> dict[str, Any]:
    """Hard-delete a knowledge item. Cascades through chunks, embeddings,
    entity mentions, and relations.

    Requires an editor-role PAT with ``allow_deletion=true``.
    """
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.delete_knowledge,
            db,
            user,
            pat,
            knowledge_id=knowledge_id,
        )


@mcp.tool()
def list_collections() -> dict[str, Any]:
    """List collections the current PAT has access to."""
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(tools_mod.list_collections, db, user, pat)


@mcp.tool()
def add_to_collection(
    collection_id: str, knowledge_id: str
) -> dict[str, Any]:
    """Link an existing knowledge item into a collection.

    Requires an editor-role PAT."""
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.add_to_collection,
            db,
            user,
            pat,
            collection_id=collection_id,
            knowledge_id=knowledge_id,
        )


@mcp.tool()
def get_entity(id_or_name: str) -> dict[str, Any]:
    """Fetch entity detail including LLM-authored synthesis and aliases.

    Accepts either the entity UUID or its canonical name / alias.
    """
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.get_entity,
            db,
            user,
            pat,
            id_or_name=id_or_name,
        )


@mcp.tool()
def get_related_entities(
    id_or_name: str, limit: int = 10
) -> dict[str, Any]:
    """Return entities connected to the given one via the concept graph,
    ranked by relation weight (repeated co-occurrence)."""
    with _tool_ctx() as (user, pat, db):
        return tools_mod.call(
            tools_mod.get_related_entities,
            db,
            user,
            pat,
            id_or_name=id_or_name,
            limit=limit,
        )


def build_mcp_app():
    """Return the streamable-HTTP ASGI app for mounting into FastAPI."""
    return mcp.streamable_http_app()
