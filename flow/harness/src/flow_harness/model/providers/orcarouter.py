"""OrcaRouter (https://www.orcarouter.ai) - one OpenAI-compatible gateway, two ways in.

A stored API key and the PKCE sign-in both end at the same durable `sk-orca-...`
key, so inference, model discovery and reasoning support never learn which one
was used. Authentication lives on a different origin from inference: the consent
screen and the code exchange are on `www.orcarouter.ai`, the relay and the model
catalog are on `api.orcarouter.ai/v1`.

The key the connect flow returns is not an access/refresh pair. It is persisted
as a durable credential (no expiry, no refresh token) and reused until the user
revokes it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from flow_harness.model.auth import AuthError, AuthProvider, NeedsReauth, RuntimeAuth
from flow_harness.model.credentials import OAuthCredential
from flow_harness.model.litellm import LiteLLMModel

PREFIX = "orcarouter"
DISPLAY_NAME = "OrcaRouter"
DEFAULT_AUTH_BASE = "https://www.orcarouter.ai"
DEFAULT_API_BASE = "https://api.orcarouter.ai/v1"
# The harness is a local desktop/web client, so the loopback redirect (Flow A)
# delivers the code without the user copying anything. The port only has to be
# free on 127.0.0.1; OrcaRouter does not pre-register redirect URIs.
REDIRECT_URI = "http://127.0.0.1:1456/cb"
APP_NAME = "Flow"
SCOPE = "api"
AUTHORIZE_PATH = "/auth"
EXCHANGE_PATH = "/api/v1/auth/keys"
AUTO_MODEL = "orcarouter/auto"
API_KEY_ENVS = ("ORCAROUTER_API_KEY",)

# Endpoint types the gateway advertises for models a chat-completions client can
# drive. Anything else (image generation, video, rerank, embeddings) is a
# different surface and is not offered in the chat picker.
CHAT_ENDPOINT_TYPES = frozenset({"openai", "anthropic", "gemini", "openai-response"})
NON_CHAT_ENDPOINT_TYPES = frozenset(
	{"image-generation", "openai-video", "jina-rerank", "embeddings", "rerank"}
)
EFFORT_ORDER = ("minimal", "low", "medium", "high", "xhigh", "max")


def _validated_origin(value: str, *, what: str) -> str:
	"""A configured origin: HTTPS for anything remote, HTTP only for loopback."""
	value = value.strip().rstrip("/")
	parsed = urlsplit(value)
	if not parsed.scheme or not parsed.netloc:
		raise AuthError(f"{what} base URL must be an absolute http(s) URL")
	if parsed.scheme == "https":
		return value
	host = (parsed.hostname or "").lower()
	if parsed.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}:
		return value
	raise AuthError(f"{what} base URL must use HTTPS unless it is on loopback")


def auth_base_url() -> str:
	"""Authentication origin: explicit override, then the shared self-hosted base, then public."""
	explicit = os.environ.get("ORCA_AUTH_BASE_URL")
	shared = os.environ.get("ORCA_BASE_URL")
	return _validated_origin(explicit or shared or DEFAULT_AUTH_BASE, what="OrcaRouter auth")


def api_base_url() -> str:
	"""Inference origin, including the `/v1` the OpenAI wire format lives under."""
	explicit = os.environ.get("ORCA_API_BASE_URL")
	if explicit:
		return _validated_origin(explicit, what="OrcaRouter API")
	shared = os.environ.get("ORCA_BASE_URL")
	if shared:
		origin = _validated_origin(shared, what="OrcaRouter API")
		return origin if origin.endswith("/v1") else f"{origin}/v1"
	return DEFAULT_API_BASE


def models_url() -> str:
	return f"{api_base_url()}/models"


def authorize_url(challenge: str, state: str) -> str:
	params = {
		"callback_url": REDIRECT_URI,
		"code_challenge": challenge,
		"code_challenge_method": "S256",
		"state": state,
		"app_name": APP_NAME,
		"scope": SCOPE,
	}
	return f"{auth_base_url()}{AUTHORIZE_PATH}?{urlencode(params)}"


class OrcaRouterAuthProvider(AuthProvider):
	name = PREFIX
	redirect_uri = REDIRECT_URI

	def authorize_url(self, *, challenge: str, state: str) -> str:
		return authorize_url(challenge, state)

	async def exchange(
		self,
		code: str,
		verifier: str,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		owns = client is None
		client = client or httpx.AsyncClient(timeout=30)
		try:
			response = await client.post(
				f"{auth_base_url()}{EXCHANGE_PATH}",
				json={
					"code": code,
					"code_verifier": verifier,
					"code_challenge_method": "S256",
				},
			)
		except httpx.HTTPError as e:
			raise AuthError("Could not reach OrcaRouter to finish sign-in") from e
		finally:
			if owns:
				await client.aclose()
		if response.status_code == 400:
			raise AuthError("OrcaRouter rejected the sign-in request (code challenge mismatch)")
		if response.status_code == 403:
			raise AuthError("This OrcaRouter sign-in code is invalid, expired or already used")
		if response.status_code == 429:
			raise AuthError("Too many OrcaRouter sign-ins; wait a few minutes and try again")
		if response.status_code >= 400:
			raise AuthError(f"OrcaRouter sign-in failed (HTTP {response.status_code})")
		try:
			payload = response.json()
		except ValueError as e:
			raise AuthError("OrcaRouter returned an unreadable sign-in response") from e
		return credential_from_exchange(payload)

	async def refresh(
		self,
		credential: OAuthCredential,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		"""An OrcaRouter key is durable: there is no refresh grant to redeem."""
		raise NeedsReauth("OrcaRouter keys do not refresh; sign in again to replace this one")

	def runtime_auth(self, credential: OAuthCredential) -> RuntimeAuth:
		return RuntimeAuth(
			token=credential.access,
			account_id=credential.account_id,
			base_url=api_base_url(),
		)


def credential_from_exchange(payload: dict) -> OAuthCredential:
	"""The granted scope is read back, not assumed; a key that cannot drive inference is refused."""
	key = payload.get("key")
	if not isinstance(key, str) or not key.strip():
		raise AuthError("OrcaRouter sign-in did not return an API key")
	scope = payload.get("scope")
	if scope != SCOPE:
		raise AuthError(
			f"OrcaRouter granted scope {scope!r}, which does not allow inference; ask a workspace admin"
		)
	user_id = payload.get("user_id")
	return OAuthCredential(
		access=key.strip(),
		refresh="",
		expires=0,
		account_id=str(user_id) if user_id else None,
	)


# --- models ---------------------------------------------------------------


@dataclass(frozen=True)
class ModelMetadata:
	input_modalities: frozenset[str] = frozenset({"text"})
	context_window: int | None = None
	max_output_tokens: int | None = None
	reasoning_efforts: tuple[str, ...] = ()

	@property
	def supports_images(self) -> bool:
		return "image" in self.input_modalities

	@property
	def supports_reasoning(self) -> bool:
		return bool(self.reasoning_efforts)


REASONING_LADDER = ("low", "medium", "high", "xhigh")

# Cold-start catalog for an outage, only used when live discovery fails. Every
# entry is text-only unless it is known to accept images, and only GPT-5.5 has a
# verified reasoning ladder; context windows stay unknown rather than guessed.
SEED_MODELS: tuple[tuple[str, str | None, ModelMetadata], ...] = (
	("openai/gpt-5.5", "GPT-5.5", ModelMetadata(reasoning_efforts=REASONING_LADDER)),
	("anthropic/claude-opus-4.8", "Claude Opus 4.8", ModelMetadata(reasoning_efforts=REASONING_LADDER)),
	("google/gemini-3.5-flash", "Gemini 3.5 Flash", ModelMetadata(reasoning_efforts=REASONING_LADDER)),
	("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro", ModelMetadata(reasoning_efforts=REASONING_LADDER)),
	(AUTO_MODEL, None, ModelMetadata(reasoning_efforts=REASONING_LADDER)),
)


def seed_models() -> tuple[tuple[str, str | None, ModelMetadata], ...]:
	"""The cold-start list, for the picker to show while live discovery is unreachable."""
	return SEED_MODELS


# Live discovery is authoritative once it has run; this only fills the gap before it.
_metadata: dict[str, ModelMetadata] = {}


def flow_model_name(remote_id: str) -> str:
	"""`openai/gpt-5.5` at the gateway is `orcarouter/openai/gpt-5.5` in Flow.

	The one exception is the gateway's own routing alias, whose wire id already
	carries the `orcarouter/` namespace."""
	if remote_id == AUTO_MODEL:
		return remote_id
	return remote_id if remote_id.startswith(f"{PREFIX}/") else f"{PREFIX}/{remote_id}"


def wire_model_id(name: str) -> str:
	"""The id to send to the relay for a Flow model name."""
	if name == AUTO_MODEL:
		return AUTO_MODEL
	return name.split("/", 1)[1] if "/" in name else name


def entry_endpoint_types(row: dict) -> frozenset[str]:
	value = row.get("supported_endpoint_types")
	if not isinstance(value, list):
		return frozenset()
	return frozenset(item for item in value if isinstance(item, str))


def entry_input_modalities(row: dict) -> frozenset[str]:
	architecture = row.get("architecture")
	value = architecture.get("input_modalities") if isinstance(architecture, dict) else None
	if not isinstance(value, list):
		return frozenset()
	return frozenset(item for item in value if isinstance(item, str))


def entry_supported_parameters(row: dict) -> frozenset[str]:
	value = row.get("supported_parameters")
	if not isinstance(value, list):
		return frozenset()
	return frozenset(item for item in value if isinstance(item, str))


def entry_supports_chat(row: dict) -> bool:
	"""A chat model is one the gateway says speaks a chat wire format and is not a
	dedicated image/video/rerank/embedding surface. An entry that advertises no
	endpoint type at all fails closed."""
	endpoints = entry_endpoint_types(row)
	if endpoints & NON_CHAT_ENDPOINT_TYPES:
		return False
	return bool(endpoints & CHAT_ENDPOINT_TYPES)


def entry_supports_modality(row: dict, modality: str) -> bool:
	"""Explicit catalog metadata only; an entry that does not declare a modality is never assumed to accept it."""
	return modality in entry_input_modalities(row)


def reasoning_efforts(row: dict) -> tuple[str, ...]:
	"""The verified effort ladder for an entry, from the parameters it declares."""
	parameters = entry_supported_parameters(row)
	if "reasoning_effort" in parameters:
		return REASONING_LADDER
	if parameters & {"reasoning", "include_reasoning", "thinking"}:
		return ("medium",)
	return ()


def metadata_from_row(row: dict) -> ModelMetadata:
	context = row.get("context_length")
	max_output = row.get("max_completion_tokens")
	return ModelMetadata(
		input_modalities=entry_input_modalities(row) or frozenset({"text"}),
		context_window=context if isinstance(context, int) and context > 0 else None,
		max_output_tokens=max_output if isinstance(max_output, int) and max_output > 0 else None,
		reasoning_efforts=reasoning_efforts(row),
	)


def remember_catalog(rows: list[dict]) -> None:
	"""Record what live discovery just reported so inference and the composer agree with the picker."""
	for row in rows:
		model = row.get("id")
		if isinstance(model, str) and model:
			_metadata[flow_model_name(model)] = metadata_from_row(row)
	# the context meter memoizes per name; the catalog just changed what it would answer
	from flow_harness.model.discovery import context_window_for

	context_window_for.cache_clear()


def forget_catalog() -> None:
	_metadata.clear()
	from flow_harness.model.discovery import context_window_for

	context_window_for.cache_clear()


def metadata_for(name: str) -> ModelMetadata | None:
	"""Live metadata first, then the verified seed; None means "not known", never a guess."""
	if name in _metadata:
		return _metadata[name]
	wire = wire_model_id(name)
	for remote, _label, meta in SEED_MODELS:
		if remote == wire:
			return meta
	return None


def supports_images(name: str) -> bool | None:
	meta = metadata_for(name)
	return meta.supports_images if meta is not None else None


def _clamp_effort(effort: str, allowed: tuple[str, ...]) -> str:
	if effort in allowed:
		return effort
	rank = EFFORT_ORDER.index(effort) if effort in EFFORT_ORDER else len(EFFORT_ORDER)
	within = [level for level in allowed if EFFORT_ORDER.index(level) <= rank]
	return within[-1] if within else allowed[0]


def reasoning_params(name: str, effort: str) -> dict[str, Any] | None:
	"""OrcaRouter takes the OpenAI-style `reasoning_effort`, but only where the catalog
	proves the model reasons. Unknown models are passed through for the gateway to judge."""
	meta = metadata_for(name)
	if meta is not None:
		if not meta.supports_reasoning:
			return None
		if meta.reasoning_efforts:
			effort = _clamp_effort(effort, meta.reasoning_efforts)
	return {"reasoning_effort": effort, "allowed_openai_params": ["reasoning_effort"]}


class OrcaRouterModel(LiteLLMModel):
	"""The OpenAI-compatible LiteLLM path with OrcaRouter's own catalog metadata on top."""

	def __init__(self, name: str, *, metadata: ModelMetadata | None = None, **kwargs: Any):
		self._metadata = metadata
		super().__init__(name, **kwargs)

	@property
	def context_window(self) -> int | None:
		if self._metadata is not None and self._metadata.context_window is not None:
			return self._metadata.context_window
		return super().context_window

	@property
	def max_output_tokens(self) -> int | None:
		if self._metadata is not None and self._metadata.max_output_tokens is not None:
			return self._metadata.max_output_tokens
		return super().max_output_tokens


def orcarouter_model(
	name: str,
	*,
	api_key: str | None = None,
	api_base: str | None = None,
	headers: dict[str, str] | None = None,
	params: dict[str, Any] | None = None,
	refresh_auth: Any = None,
) -> OrcaRouterModel:
	if "/" not in name:
		raise ValueError("OrcaRouter models are named `orcarouter/<vendor>/<model>`")
	meta = metadata_for(name)
	return OrcaRouterModel(
		f"openai/{wire_model_id(name)}",
		metadata=meta,
		api_key=api_key,
		api_base=api_base or api_base_url(),
		headers=headers,
		params=params,
		provider=PREFIX,
		model=name,
		supports_images=meta.supports_images if meta is not None else None,
		refresh_auth=refresh_auth,
	)
