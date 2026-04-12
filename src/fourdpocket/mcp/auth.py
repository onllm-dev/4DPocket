"""PAT-based TokenVerifier for the MCP server.

Wraps the shared ``api_token_utils.resolve_token`` so MCP requests authenticate
identically to HTTP API calls. The PAT plaintext is returned in
``AccessToken.token`` so tool handlers can re-resolve the current ``ApiToken``
row on each call (each lookup is O(1) via the prefix index).
"""

from __future__ import annotations

import asyncio

from mcp.server.auth.provider import AccessToken, TokenVerifier

from fourdpocket.api.api_token_utils import resolve_token, touch_last_used
from fourdpocket.db.session import get_engine


class PATTokenVerifier(TokenVerifier):
    """Validates ``fdp_pat_*`` bearer tokens against the database."""

    async def verify_token(self, token: str) -> AccessToken | None:
        return await asyncio.to_thread(self._verify_sync, token)

    def _verify_sync(self, token: str) -> AccessToken | None:
        from sqlmodel import Session

        with Session(get_engine()) as db:
            pat = resolve_token(db, token)
            if pat is None:
                return None

            touch_last_used(db, pat)

            scopes = ["mcp", pat.role.value]
            if pat.allow_deletion:
                scopes.append("knowledge:delete")
            if pat.admin_scope:
                scopes.append("admin")

            expires_at = None
            if pat.expires_at is not None:
                expires_at = int(pat.expires_at.timestamp())

            return AccessToken(
                token=token,
                client_id=str(pat.user_id),
                scopes=scopes,
                expires_at=expires_at,
            )
