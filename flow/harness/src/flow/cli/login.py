"""Interactive provider credential setup for the flowd CLI."""

from __future__ import annotations

import getpass
import html
import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

from flow.model.auth import AuthError, generate_pkce, get_auth_provider, new_state
from flow.model.catalog import PROVIDERS, ProviderSpec, get_provider
from flow.model.credentials import CredentialStore
from flow.model.providers.codex import REDIRECT_URI

LOGIN_TIMEOUT_SECONDS = 300


def login(
	store: CredentialStore,
	provider_id: str | None,
	*,
	manual: bool = False,
) -> None:
	provider = _select_provider(provider_id)
	if "oauth" in provider.auth_methods:
		credential = _oauth_login(provider, manual=manual)
		store.set_oauth(provider.id, credential)
		print(f"Logged in to {provider.display_name}.")
		return

	key = getpass.getpass(f"API key for {provider.display_name}: ").strip()
	if not key:
		raise AuthError("API key cannot be empty")
	store.set_api_key(provider.id, key)
	print(f"Saved API key for {provider.display_name}.")


def logout(store: CredentialStore, provider_id: str) -> None:
	provider = _required_provider(provider_id)
	if store.get(provider.id) is None:
		print(f"{provider.display_name} is not configured.")
		return
	store.delete(provider.id)
	print(f"Logged out of {provider.display_name}.")


def show_providers(store: CredentialStore) -> None:
	stored = {entry.provider_id: entry.type for entry in store.list()}
	width = max(len(provider.id) for provider in PROVIDERS)
	for provider in PROVIDERS:
		kind = stored.get(provider.id)
		if kind == "api_key":
			source = "stored API key"
		elif kind == "oauth":
			source = "OAuth"
		else:
			source = next((name for name in provider.api_key_envs if os.environ.get(name)), None)
		print(f"{provider.id:<{width}}  {source or 'not configured'}")


def _select_provider(provider_id: str | None) -> ProviderSpec:
	if provider_id:
		return _required_provider(provider_id)
	for index, provider in enumerate(PROVIDERS, start=1):
		print(f"{index:>2}. {provider.display_name}")
	raw = input("Provider: ").strip()
	try:
		index = int(raw)
		if index < 1:
			raise IndexError
		return PROVIDERS[index - 1]
	except ValueError, IndexError:
		return _required_provider(raw)


def _required_provider(provider_id: str) -> ProviderSpec:
	provider = get_provider(provider_id)
	if provider is None:
		available = ", ".join(item.id for item in PROVIDERS)
		raise AuthError(f"Unknown provider {provider_id!r}. Available: {available}")
	return provider


def _oauth_login(provider: ProviderSpec, *, manual: bool):
	auth_provider = get_auth_provider(provider.id)
	pkce = generate_pkce()
	state = new_state()
	url = auth_provider.authorize_url(challenge=pkce.challenge, state=state)

	if manual:
		print(f"Open this URL in a browser:\n{url}\n")
		value = input("Paste the full callback URL: ")
		code, returned_state = _parse_callback(value)
	else:
		code, returned_state = _browser_callback(url)

	if returned_state != state:
		raise AuthError("OAuth state mismatch; login was not accepted")
	if not code:
		raise AuthError("OAuth callback did not contain an authorization code")
	try:
		return _run_async(auth_provider.exchange(code, pkce.verifier))
	except (httpx.HTTPError, KeyError, ValueError) as e:
		raise AuthError("OAuth token exchange failed") from e


def _browser_callback(url: str) -> tuple[str | None, str | None]:
	redirect = urlparse(REDIRECT_URI)
	expected_state = _first(parse_qs(urlparse(url).query), "state")
	result: dict[str, str | None] = {"code": None, "state": None, "error": None}

	class CallbackHandler(BaseHTTPRequestHandler):
		def do_GET(self) -> None:  # BaseHTTPRequestHandler API
			parsed = urlparse(self.path)
			if parsed.path != redirect.path:
				self.send_error(404)
				return
			query = parse_qs(parsed.query)
			result["code"] = _first(query, "code")
			result["state"] = _first(query, "state")
			result["error"] = _first(query, "error")
			if not result["error"] and result["state"] != expected_state:
				result["error"] = "state_mismatch"
			body = _callback_page(result["error"])
			self.send_response(200 if not result["error"] else 400)
			self.send_header("Content-Type", "text/html; charset=utf-8")
			self.send_header("Content-Length", str(len(body)))
			self.send_header("Cache-Control", "no-store")
			self.end_headers()
			self.wfile.write(body)

		def log_message(self, format: str, *args) -> None:
			pass

	try:
		server = ThreadingHTTPServer(
			("127.0.0.1", redirect.port or 80),
			CallbackHandler,
		)
	except OSError as e:
		raise AuthError(
			"Could not start the loopback OAuth callback. Retry with `flowd login codex --manual`."
		) from e

	server.timeout = 1
	print("Opening your browser for sign-in...")
	print(f"If it does not open, visit:\n{url}")
	webbrowser.open(url)
	deadline = time.monotonic() + LOGIN_TIMEOUT_SECONDS
	try:
		while time.monotonic() < deadline and result["code"] is None and result["error"] is None:
			server.handle_request()
	finally:
		server.server_close()
	if result["error"]:
		raise AuthError(f"OAuth provider returned {result['error']}")
	if result["code"] is None:
		raise AuthError("OAuth login timed out")
	return result["code"], result["state"]


def _parse_callback(value: str) -> tuple[str | None, str | None]:
	value = value.strip()
	parsed = urlparse(value)
	if parsed.scheme and parsed.netloc:
		query = parse_qs(parsed.query)
		return _first(query, "code"), _first(query, "state")
	if "#" in value:
		code, state = value.split("#", 1)
		return code or None, state or None
	query = parse_qs(value.removeprefix("?"))
	return _first(query, "code"), _first(query, "state")


def _first(query: dict[str, list[str]], name: str) -> str | None:
	values = query.get(name)
	return values[0] if values else None


def _callback_page(error: str | None) -> bytes:
	if error:
		title = "Authentication failed"
		message = html.escape(error)
	else:
		title = "Authentication successful"
		message = "You can close this window and return to Flow."
	return (
		"<!doctype html><html><head><meta charset='utf-8'>"
		f"<title>{title}</title></head><body><main><h1>{title}</h1>"
		f"<p>{message}</p></main></body></html>"
	).encode()


def _run_async(awaitable):
	import asyncio

	return asyncio.run(awaitable)
