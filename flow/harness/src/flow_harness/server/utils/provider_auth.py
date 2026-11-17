"""Browser-facing provider setup over the daemon's credential machinery.

The CLI (`flow login`) and this module share the same primitives — PKCE from
`model/auth.py`, the credential store, the provider's own loopback redirect —
so a login completed from the web UI is indistinguishable from one done in the
terminal. Flows live in memory on the daemon; the browser polls status.
"""

from __future__ import annotations

import asyncio
import os
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from http.server import ThreadingHTTPServer
from socketserver import BaseServer

from flow_harness.model.auth import AuthError, generate_pkce, get_auth_provider, new_state
from flow_harness.model.catalog import PROVIDERS, ProviderSpec, get_provider
from flow_harness.model.credentials import CredentialStore, CustomProviderCredential
from flow_harness.model.oauth_callback import (
	REJECTED,
	CallbackResult,
	Rejected,
	callback_server,
	parse_callback,
)

OAUTH_TIMEOUT_SECONDS = 300


def provider_catalog(store: CredentialStore) -> list[dict]:
	"""One row per known provider: how (and whether) it is configured."""
	stored = {entry.provider_id: entry.type for entry in store.list()}
	rows = []
	for provider in PROVIDERS:
		credential_type = stored.get(provider.id)
		env_source = next((name for name in provider.api_key_envs if os.environ.get(name)), None)
		source = (
			"OAuth"
			if credential_type == "oauth"
			else "Stored API key"
			if credential_type == "api_key"
			else env_source
		)
		rows.append(
			{
				"id": provider.id,
				"name": provider.display_name,
				"model_prefixes": list(provider.model_prefixes),
				"auth_methods": list(provider.auth_methods),
				"configured": bool(source),
				"credential_type": credential_type,
				"source": source,
				"custom": False,
			}
		)
	for entry in store.list():
		if entry.type != "custom":
			continue
		credential = store.get_custom(entry.provider_id)
		if credential is not None:
			rows.append(_custom_provider_row(entry.provider_id, credential))
	return rows


def create_custom_provider(
	store: CredentialStore,
	*,
	name: str,
	base_url: str,
	models: tuple[str, ...],
	api_key: str | None,
) -> dict:
	"""Store an endpoint under a slug from its name; collisions get a suffix."""
	slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "endpoint"
	provider_id = f"custom-{slug}"
	suffix = 2
	while store.get(provider_id) is not None or get_provider(provider_id) is not None:
		provider_id = f"custom-{slug}-{suffix}"
		suffix += 1
	store.set_custom(
		provider_id,
		display_name=name,
		base_url=base_url,
		models=models,
		api_key=api_key,
	)
	credential = store.get_custom(provider_id)
	if credential is None:  # pragma: no cover — set_custom just wrote it
		raise AuthError("Failed to store the custom endpoint")
	return _custom_provider_row(provider_id, credential)


def update_custom_provider(
	store: CredentialStore,
	provider_id: str,
	*,
	name: str,
	base_url: str,
	models: tuple[str, ...],
	api_key: str | None,
) -> dict | None:
	"""Rewrite an endpoint under its existing id; no api_key keeps the stored one
	unless base_url changed. Returns None when the id has no stored custom endpoint."""
	existing = store.get_custom(provider_id)
	if existing is None:
		return None
	store.set_custom(
		provider_id,
		display_name=name,
		base_url=base_url,
		models=models,
		# a blank key keeps the stored one — but never across a base_url change:
		# repointing the endpoint must not leak the old key to the new host
		api_key=api_key or (existing.api_key if base_url == existing.base_url else None),
	)
	credential = store.get_custom(provider_id)
	if credential is None:  # pragma: no cover — set_custom just wrote it
		raise AuthError("Failed to store the custom endpoint")
	return _custom_provider_row(provider_id, credential)


def _custom_provider_row(provider_id: str, credential: CustomProviderCredential) -> dict:
	prefixes = sorted({model.split("/", 1)[0] for model in credential.models})
	return {
		"id": provider_id,
		"name": credential.name,
		"model_prefixes": prefixes,
		"models": list(credential.models),
		"auth_methods": ["custom"],
		"configured": True,
		"credential_type": "custom",
		"source": credential.base_url,
		"custom": True,
		"icon": "ollama" if "ollama" in prefixes else "server",
	}


def require_provider(provider_id: str) -> ProviderSpec:
	provider = get_provider(provider_id)
	if provider is None:
		raise AuthError(f"Unknown provider {provider_id!r}")
	return provider


@dataclass
class OAuthFlow:
	provider_id: str
	state: str
	verifier: str
	authorize_url: str
	status: str = "pending"
	error: str | None = None
	server: ThreadingHTTPServer | None = None
	callbacks: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1))
	lock: asyncio.Lock = field(default_factory=asyncio.Lock)
	started_at: float = field(default_factory=time.monotonic)
	done: asyncio.Event = field(default_factory=asyncio.Event)
	result: tuple[str | None, str | None, str | None] | None = None


class OAuthCoordinator:
	"""Per-daemon registry of in-flight browser OAuth logins, one per provider."""

	def __init__(self, store: CredentialStore):
		self.store = store
		self.flows: dict[str, OAuthFlow] = {}
		self.tasks: set[asyncio.Task] = set()

	async def start(self, provider_id: str) -> dict:
		provider = require_provider(provider_id)
		if "oauth" not in provider.auth_methods:
			raise AuthError(f"{provider.display_name} does not support OAuth")

		await self._stop_existing(provider_id)
		pkce = generate_pkce()
		state = new_state()
		auth_provider = get_auth_provider(provider_id)
		flow = OAuthFlow(
			provider_id=provider_id,
			state=state,
			verifier=pkce.verifier,
			authorize_url=auth_provider.authorize_url(challenge=pkce.challenge, state=state),
		)
		self.flows[provider_id] = flow

		try:
			flow.server = _callback_server(flow)
		except OSError:
			# loopback port taken (e.g. a concurrent `flow login`); the UI can
			# still paste the callback URL into /oauth/complete
			flow.status = "waiting_manual"
		else:
			# a daemon thread, never asyncio.to_thread: executor threads are
			# non-daemon and a long-lived listener would block interpreter exit
			loop = asyncio.get_running_loop()
			threading.Thread(target=_serve_callback, args=(flow, flow.server, loop), daemon=True).start()
			task = asyncio.create_task(self._wait_for_callback(flow))
			self.tasks.add(task)
			task.add_done_callback(self.tasks.discard)

		return {"authorize_url": flow.authorize_url, "status": flow.status}

	def status(self, provider_id: str) -> dict:
		flow = self.flows.get(provider_id)
		if flow is None:
			return {"status": "idle", "error": None}
		if (
			flow.status in {"pending", "waiting_manual"}
			and time.monotonic() - flow.started_at >= OAUTH_TIMEOUT_SECONDS
		):
			flow.status = "expired"
			flow.error = "OAuth login timed out"
		return {"status": flow.status, "error": flow.error}

	async def complete(self, provider_id: str, callback_url: str) -> dict:
		flow = self.flows.get(provider_id)
		if flow is None:
			raise AuthError("Start OAuth before completing it")
		code, state, error = parse_callback(callback_url)
		await self._exchange(flow, code=code, state=state, error=error)
		await self._close_server(flow)
		return self.status(provider_id)

	async def _wait_for_callback(self, flow: OAuthFlow) -> None:
		try:
			await asyncio.wait_for(flow.done.wait(), timeout=OAUTH_TIMEOUT_SECONDS)
		except TimeoutError:
			flow.status = "expired"
			flow.error = "OAuth login timed out"
			await self._close_server(flow)
			return

		if flow.result is not None:
			code, state, error = flow.result
			await self._exchange(flow, code=code, state=state, error=error)
		await self._close_server(flow)

	async def _exchange(
		self,
		flow: OAuthFlow,
		*,
		code: str | None,
		state: str | None,
		error: str | None,
	) -> None:
		async with flow.lock:
			if flow.status == "connected":
				return
			if error:
				flow.status = "error"
				flow.error = f"OAuth provider returned {error}"
				return
			if state != flow.state:
				flow.status = "error"
				flow.error = "OAuth state mismatch; login was not accepted"
				return
			if not code:
				flow.status = "error"
				flow.error = "OAuth callback did not contain an authorization code"
				return

			flow.status = "exchanging"
			try:
				credential = await get_auth_provider(flow.provider_id).exchange(code, flow.verifier)
				self.store.set_oauth(flow.provider_id, credential)
			except Exception:
				flow.status = "error"
				flow.error = "OAuth token exchange failed"
				return
			flow.status = "connected"
			flow.error = None

	async def _stop_existing(self, provider_id: str) -> None:
		flow = self.flows.get(provider_id)
		if flow is not None:
			await self._close_server(flow)

	async def _close_server(self, flow: OAuthFlow) -> None:
		server, flow.server = flow.server, None
		if server is None:
			return
		await asyncio.to_thread(server.shutdown)
		server.server_close()


def _callback_server(flow: OAuthFlow) -> ThreadingHTTPServer:
	def accept(result: CallbackResult, server: BaseServer) -> str | Rejected | None:
		# without this any local page hitting the port kills a pending login
		if result[1] != flow.state:
			return REJECTED
		try:
			flow.callbacks.put_nowait(result)
		except queue.Full:
			pass
		threading.Thread(target=server.shutdown, daemon=True).start()
		return result[2]

	server = callback_server(accept)
	server.daemon_threads = True
	return server


def _serve_callback(flow: OAuthFlow, server: ThreadingHTTPServer, loop: asyncio.AbstractEventLoop) -> None:
	"""Daemon-thread body: serve the loopback redirect until shutdown, then hand
	the captured callback (if any) back to the event loop.

	serve_forever must run unconditionally: `shutdown()` blocks until the loop
	observes it, so skipping it would deadlock the closer."""
	server.serve_forever(poll_interval=0.2)
	try:
		flow.result = flow.callbacks.get_nowait()
	except queue.Empty:
		flow.result = None
	try:
		loop.call_soon_threadsafe(flow.done.set)
	except RuntimeError:
		pass  # loop already closed (daemon shutdown mid-flow)
