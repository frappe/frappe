"""Interactive provider credential setup for the flow CLI."""

from __future__ import annotations

import getpass
import time
import webbrowser
from socketserver import BaseServer
from urllib.parse import parse_qs, urlparse

import httpx

from flow_harness.model.auth import AuthError, generate_pkce, get_auth_provider, new_state
from flow_harness.model.catalog import PROVIDERS, ProviderSpec, configured_env, get_provider
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.oauth_callback import CallbackResult, Rejected, callback_server, first, parse_callback

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
			source = configured_env(provider)
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
	except (ValueError, IndexError):
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
	expected_state = first(parse_qs(urlparse(url).query), "state")
	result: dict[str, str | None] = {"code": None, "state": None, "error": None}

	def accept(parsed: CallbackResult, server: BaseServer) -> str | Rejected | None:
		code, state, error = parsed
		if not error and state != expected_state:
			error = "state_mismatch"
		result["code"], result["state"], result["error"] = code, state, error
		return error

	try:
		server = callback_server(accept)
	except OSError as e:
		raise AuthError(
			"Could not start the loopback OAuth callback. Retry with `flow login codex --manual`."
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
	"""Manual-paste input: a full callback URL, a raw query string, or `code#state`."""
	value = value.strip()
	parsed = urlparse(value)
	if parsed.scheme and parsed.netloc:
		code, state, _ = parse_callback(value)
		return code, state
	if "#" in value:
		code, state = value.split("#", 1)
		return code or None, state or None
	query = parse_qs(value.removeprefix("?"))
	return first(query, "code"), first(query, "state")


def _run_async(awaitable):
	import asyncio

	return asyncio.run(awaitable)
