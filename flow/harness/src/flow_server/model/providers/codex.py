"""Codex (ChatGPT subscription) auth provider.

Only the AUTH side lives here for now — login/refresh/runtime_auth. The Responses-API
model (the wire class) is deferred until the login CLI exists so it can be tested
end-to-end against a real subscription. Constants are cross-checked against the tau and
opencode implementations, which agree exactly.
"""

from __future__ import annotations

import time
from urllib.parse import urlencode

import httpx

from flow_server.model.auth import (
	AuthProvider,
	RuntimeAuth,
	account_id_from_tokens,
	decode_jwt_claims,
	post_token,
	register_auth_provider,
)
from flow_server.model.credentials import OAuthCredential

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/oauth/authorize"
TOKEN_URL = f"{ISSUER}/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"
ORIGINATOR = "flow_server"
API_BASE = "https://chatgpt.com/backend-api"
DEFAULT_EXPIRES_S = 3600


class CodexAuthProvider(AuthProvider):
	name = "codex"

	def authorize_url(self, *, challenge: str, state: str) -> str:
		params = {
			"response_type": "code",
			"client_id": CLIENT_ID,
			"redirect_uri": REDIRECT_URI,
			"scope": SCOPE,
			"code_challenge": challenge,
			"code_challenge_method": "S256",
			"state": state,
			"id_token_add_organizations": "true",
			"codex_cli_simplified_flow": "true",
			"originator": ORIGINATOR,
		}
		return f"{AUTHORIZE_URL}?{urlencode(params)}"

	async def exchange(
		self,
		code: str,
		verifier: str,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		tokens = await post_token(
			TOKEN_URL,
			{
				"grant_type": "authorization_code",
				"client_id": CLIENT_ID,
				"code": code,
				"code_verifier": verifier,
				"redirect_uri": REDIRECT_URI,
			},
			client,
		)
		return _credential(tokens, now_ms=now_ms)

	async def refresh(
		self,
		credential: OAuthCredential,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		tokens = await post_token(
			TOKEN_URL,
			{
				"grant_type": "refresh_token",
				"client_id": CLIENT_ID,
				"refresh_token": credential.refresh,
			},
			client,
		)
		return _credential(tokens, old_refresh=credential.refresh, now_ms=now_ms)

	def runtime_auth(self, credential: OAuthCredential) -> RuntimeAuth:
		return RuntimeAuth(
			token=credential.access,
			account_id=credential.account_id,
			base_url=API_BASE,
			headers={
				"chatgpt-account-id": credential.account_id or "",
				"originator": ORIGINATOR,
			},
		)


def _credential(
	tokens: dict, *, old_refresh: str | None = None, now_ms: int | None = None
) -> OAuthCredential:
	now = now_ms if now_ms is not None else int(time.time() * 1000)
	access = tokens["access_token"]
	return OAuthCredential(
		access=access,
		refresh=tokens.get("refresh_token") or old_refresh or "",
		expires=_expires_ms(tokens, access, now),
		account_id=account_id_from_tokens(tokens.get("id_token"), access),
	)


def _expires_ms(tokens: dict, access_token: str, now_ms: int) -> int:
	if tokens.get("expires_in"):
		return now_ms + int(tokens["expires_in"]) * 1000
	exp = decode_jwt_claims(access_token).get("exp")
	if exp:
		return int(exp) * 1000
	return now_ms + DEFAULT_EXPIRES_S * 1000


register_auth_provider(CodexAuthProvider())
