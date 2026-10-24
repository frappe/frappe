"""OrcaRouter: PKCE sign-in and durable-key lifecycle, the two origins, and the
catalog its chat picker, image filter and reasoning support read from."""

import base64
import hashlib

import httpx
import pytest

from flow_harness.model.auth import (
	AuthError,
	NeedsReauth,
	generate_pkce,
	get_auth_provider,
	resolve_oauth,
)
from flow_harness.model.catalog import PROVIDERS, model_supports_images
from flow_harness.model.credentials import CredentialStore, OAuthCredential
from flow_harness.model.discovery import available_models, context_window_for
from flow_harness.model.providers import orcarouter
from flow_harness.model.providers.orcarouter import (
	AUTO_MODEL,
	OrcaRouterAuthProvider,
	authorize_url,
	credential_from_exchange,
	entry_supports_chat,
	entry_supports_modality,
	flow_model_name,
	forget_catalog,
	metadata_for,
	orcarouter_model,
	reasoning_efforts,
	remember_catalog,
	wire_model_id,
)
from flow_harness.model.reasoning import reasoning_params


@pytest.fixture(autouse=True)
def clean_catalog():
	"""Live metadata is process-wide; a test must not inherit another's rows."""
	forget_catalog()
	yield
	forget_catalog()


@pytest.fixture(autouse=True)
def clean_orca_env(monkeypatch):
	for name in ("ORCA_BASE_URL", "ORCA_AUTH_BASE_URL", "ORCA_API_BASE_URL", "ORCAROUTER_API_KEY"):
		monkeypatch.delenv(name, raising=False)


def _store(tmp_path) -> CredentialStore:
	return CredentialStore(str(tmp_path / "credentials.json"))


def _client(handler) -> httpx.AsyncClient:
	return httpx.AsyncClient(transport=httpx.MockTransport(handler))


ROW = {
	"id": "openai/gpt-5.5",
	"name": "GPT-5.5",
	"supported_endpoint_types": ["openai", "openai-response"],
	"architecture": {"input_modalities": ["text"]},
	"context_length": 400_000,
	"max_completion_tokens": 128_000,
	"supported_parameters": ["reasoning_effort", "tools"],
}


# --- the two origins ------------------------------------------------------


def test_inference_and_sign_in_live_on_different_origins():
	assert orcarouter.auth_base_url() == "https://www.orcarouter.ai"
	assert orcarouter.api_base_url() == "https://api.orcarouter.ai/v1"
	assert orcarouter.models_url() == "https://api.orcarouter.ai/v1/models"
	assert f"{orcarouter.auth_base_url()}{orcarouter.EXCHANGE_PATH}" == (
		"https://www.orcarouter.ai/api/v1/auth/keys"
	)


def test_both_settings_are_explicitly_overridable(monkeypatch):
	monkeypatch.setenv("ORCA_AUTH_BASE_URL", "https://auth.internal.example")
	monkeypatch.setenv("ORCA_API_BASE_URL", "https://relay.internal.example/v1/")
	assert orcarouter.auth_base_url() == "https://auth.internal.example"
	assert orcarouter.api_base_url() == "https://relay.internal.example/v1"


def test_shared_base_sets_both_and_gains_one_v1_for_inference(monkeypatch):
	monkeypatch.setenv("ORCA_BASE_URL", "https://gateway.internal.example")
	assert orcarouter.auth_base_url() == "https://gateway.internal.example"
	assert orcarouter.api_base_url() == "https://gateway.internal.example/v1"

	monkeypatch.setenv("ORCA_BASE_URL", "https://gateway.internal.example/v1")
	assert orcarouter.api_base_url() == "https://gateway.internal.example/v1"


def test_overrides_stay_on_https_except_for_loopback(monkeypatch):
	monkeypatch.setenv("ORCA_BASE_URL", "http://127.0.0.1:8080")
	assert orcarouter.api_base_url() == "http://127.0.0.1:8080/v1"

	for insecure in ("http://gateway.example", "ftp://gateway.example", "gateway.example"):
		monkeypatch.setenv("ORCA_API_BASE_URL", insecure)
		with pytest.raises(AuthError):
			orcarouter.api_base_url()


# --- PKCE sign-in ---------------------------------------------------------


def test_the_authorize_url_asks_for_s256_on_the_sign_in_origin():
	pkce = generate_pkce()
	url = authorize_url(pkce.challenge, "st-123")

	assert url.startswith("https://www.orcarouter.ai/auth?")
	query = dict(httpx.URL(url).params)
	assert query["code_challenge"] == pkce.challenge
	assert query["code_challenge_method"] == "S256"
	assert query["state"] == "st-123"
	assert query["callback_url"] == orcarouter.REDIRECT_URI
	assert query["app_name"] == "Flow"
	assert query["scope"] == "api"
	# the verifier itself never travels in the browser leg
	assert pkce.verifier not in url


def test_the_challenge_is_the_s256_digest_of_the_verifier():
	pkce = generate_pkce()
	expected = base64.urlsafe_b64encode(hashlib.sha256(pkce.verifier.encode()).digest())
	assert pkce.challenge == expected.decode().rstrip("=")


async def test_exchange_posts_the_verifier_to_the_key_endpoint_as_json():
	seen = {}

	def handler(request):
		seen["url"] = str(request.url)
		seen["body"] = request.read().decode()
		seen["content_type"] = request.headers["content-type"]
		return httpx.Response(200, json={"key": "sk-orca-issued", "scope": "api", "user_id": 42})

	credential = await OrcaRouterAuthProvider().exchange("the-code", "the-verifier", client=_client(handler))

	assert seen["url"] == "https://www.orcarouter.ai/api/v1/auth/keys"
	assert seen["url"].count("/v1/auth/keys") == 1
	assert seen["content_type"].startswith("application/json")
	assert '"code": "the-code"' not in seen["body"]  # json.dumps has no spaces
	assert '"code":"the-code"' in seen["body"]
	assert '"code_verifier":"the-verifier"' in seen["body"]
	assert '"code_challenge_method":"S256"' in seen["body"]
	assert credential == OAuthCredential(access="sk-orca-issued", refresh="", expires=0, account_id="42")


async def test_the_issued_key_is_durable_rather_than_a_token_pair():
	credential = credential_from_exchange({"key": "sk-orca-k", "scope": "api"})
	assert credential.is_durable
	assert credential.expires == 0
	assert credential.refresh == ""
	assert credential.account_id is None


@pytest.mark.parametrize(
	("status", "message"),
	[
		(400, "code challenge mismatch"),
		(403, "invalid, expired or already used"),
		(429, "Too many OrcaRouter sign-ins"),
		(500, "HTTP 500"),
	],
)
async def test_exchange_failures_are_actionable_and_leak_nothing(status, message):
	def handler(request):
		return httpx.Response(status, json={"error": "sk-orca-secret-leak", "detail": "the-verifier"})

	with pytest.raises(AuthError) as raised:
		await OrcaRouterAuthProvider().exchange("c", "the-verifier", client=_client(handler))

	assert message in str(raised.value)
	assert "sk-orca-secret-leak" not in str(raised.value)
	assert "the-verifier" not in str(raised.value)


async def test_a_network_failure_is_reported_as_such():
	def handler(request):
		raise httpx.ConnectError("no route", request=request)

	with pytest.raises(AuthError) as raised:
		await OrcaRouterAuthProvider().exchange("c", "v", client=_client(handler))
	assert "Could not reach OrcaRouter" in str(raised.value)


def test_exchange_without_a_key_or_with_a_narrower_scope_is_refused():
	with pytest.raises(AuthError, match="did not return an API key"):
		credential_from_exchange({"scope": "api"})
	with pytest.raises(AuthError, match="did not return an API key"):
		credential_from_exchange({"key": "   ", "scope": "api"})
	# the granted scope is read back, never assumed
	with pytest.raises(AuthError, match="granted scope 'chat'"):
		credential_from_exchange({"key": "sk-orca-k", "scope": "chat"})


async def test_refresh_is_terminal_rather_than_a_invented_grant():
	with pytest.raises(NeedsReauth, match="do not refresh"):
		await OrcaRouterAuthProvider().refresh(OAuthCredential(access="sk-orca-k", refresh="", expires=0))


def test_the_provider_declares_its_own_callback_and_is_registered():
	provider = get_auth_provider("orcarouter")
	assert provider.name == "orcarouter"
	assert provider.redirect_uri == "http://127.0.0.1:1456/cb"
	spec = next(p for p in PROVIDERS if p.id == "orcarouter")
	assert spec.display_name == "OrcaRouter"
	assert spec.auth_methods == ("api_key", "oauth")
	assert spec.api_key_envs == ("ORCAROUTER_API_KEY",)


# --- durable-key lifecycle ------------------------------------------------


async def test_a_stored_key_is_reused_without_any_refresh_call(tmp_path):
	store = _store(tmp_path)
	store.set_oauth("orcarouter", OAuthCredential(access="sk-orca-k", refresh="", expires=0, account_id="7"))

	def handler(request):
		raise AssertionError("a durable key has nothing to refresh")

	auth = await resolve_oauth(store, "orcarouter", client=_client(handler))
	assert auth.token == "sk-orca-k"
	assert auth.account_id == "7"
	assert auth.base_url == "https://api.orcarouter.ai/v1"


async def test_a_rejected_key_becomes_needs_reauth_without_being_deleted(tmp_path):
	store = _store(tmp_path)
	store.set_oauth("orcarouter", OAuthCredential(access="sk-orca-old", refresh="", expires=0))

	with pytest.raises(NeedsReauth):
		await resolve_oauth(store, "orcarouter", refresh_access_token="sk-orca-old")

	stored = store.get_oauth("orcarouter")
	assert stored.access == "sk-orca-old"  # kept for the user to see, not silently dropped
	assert stored.needs_reauth is True
	# and it stays a terminal state on the next request rather than looping
	with pytest.raises(NeedsReauth):
		await resolve_oauth(store, "orcarouter")


async def test_a_late_rejection_of_the_old_key_does_not_mark_the_new_sign_in(tmp_path):
	store = _store(tmp_path)
	store.set_oauth("orcarouter", OAuthCredential(access="sk-orca-new", refresh="", expires=0))

	auth = await resolve_oauth(store, "orcarouter", refresh_access_token="sk-orca-old")

	assert auth.token == "sk-orca-new"
	assert store.get_oauth("orcarouter").needs_reauth is False


async def test_a_new_sign_in_clears_the_needs_reauth_flag(tmp_path):
	store = _store(tmp_path)
	store.set_oauth(
		"orcarouter", OAuthCredential(access="sk-orca-old", refresh="", expires=0, needs_reauth=True)
	)
	store.set_oauth("orcarouter", credential_from_exchange({"key": "sk-orca-new", "scope": "api"}))
	assert store.get_oauth("orcarouter").needs_reauth is False
	assert (await resolve_oauth(store, "orcarouter")).token == "sk-orca-new"


def test_an_api_key_credential_is_independently_usable(tmp_path):
	store = _store(tmp_path)
	store.set_api_key("orcarouter", "sk-orca-pasted")
	assert store.get_api_key("orcarouter").key == "sk-orca-pasted"
	assert store.get_oauth("orcarouter") is None


def test_the_credential_file_roundtrips_a_durable_key(tmp_path):
	path = tmp_path / "credentials.json"
	store = CredentialStore(str(path))
	store.set_oauth(
		"orcarouter", OAuthCredential(access="sk-orca-k", refresh="", expires=0, needs_reauth=True)
	)
	reloaded = CredentialStore(str(path)).get_oauth("orcarouter")
	assert reloaded == OAuthCredential(access="sk-orca-k", refresh="", expires=0, needs_reauth=True)
	assert reloaded.is_durable


# --- the catalog ----------------------------------------------------------


@pytest.mark.parametrize(
	("endpoints", "chat"),
	[
		(["openai"], True),
		(["anthropic"], True),
		(["gemini"], True),
		(["openai-response"], True),
		(["openai", "image-generation"], False),
		(["image-generation"], False),
		(["openai-video"], False),
		(["jina-rerank"], False),
		(["embeddings"], False),
		([], False),
		("openai", False),
	],
)
def test_only_chat_wire_formats_reach_the_picker(endpoints, chat):
	row = {"id": "x", "supported_endpoint_types": endpoints}
	assert entry_supports_chat(row) is (chat and True)


def test_a_modality_is_only_believed_when_the_catalog_declares_it():
	assert entry_supports_modality({"architecture": {"input_modalities": ["text", "image"]}}, "image")
	assert not entry_supports_modality({"architecture": {"input_modalities": ["text"]}}, "image")
	assert not entry_supports_modality({}, "image")
	assert not entry_supports_modality({"architecture": None}, "image")


async def test_discovery_asks_for_chat_models_and_filters_the_rows(tmp_path):
	store = _store(tmp_path)
	store.set_api_key("orcarouter", "sk-orca-k")

	def handler(request):
		assert str(request.url).startswith("https://api.orcarouter.ai/v1/models")
		assert dict(request.url.params) == {"capability": "chat"}
		assert request.headers["Authorization"] == "Bearer sk-orca-k"
		return httpx.Response(
			200,
			json={
				"data": [
					ROW,
					{
						"id": "acme/vision",
						"name": "Acme Vision",
						"supported_endpoint_types": ["openai"],
						"architecture": {"input_modalities": ["text", "image"]},
					},
					{"id": "acme/painter", "supported_endpoint_types": ["image-generation"]},
					{"id": "acme/parakeet", "supported_endpoint_types": ["openai-video"]},
					{"id": "acme/scholar", "supported_endpoint_types": ["jina-rerank"]},
					{"id": "acme/embed", "supported_endpoint_types": ["embeddings"]},
					{"id": "acme/mystery"},
				]
			},
		)

	models = (await available_models(store, client=_client(handler))).models

	assert [m.name for m in models] == [
		"orcarouter/acme/vision",
		"orcarouter/openai/gpt-5.5",
	]
	by_name = {m.name: m for m in models}
	assert by_name["orcarouter/acme/vision"].display_name == "Acme Vision"
	assert by_name["orcarouter/acme/vision"].supports_images is True
	assert by_name["orcarouter/openai/gpt-5.5"].supports_images is False
	# live metadata is remembered for inference and the composer
	meta = metadata_for("orcarouter/openai/gpt-5.5")
	assert meta.context_window == 400_000
	assert meta.max_output_tokens == 128_000
	assert meta.reasoning_efforts == ("low", "medium", "high", "xhigh")
	assert context_window_for("orcarouter/openai/gpt-5.5") == 400_000


async def test_an_outage_falls_back_to_the_verified_seed_only(tmp_path):
	store = _store(tmp_path)
	store.set_api_key("orcarouter", "sk-orca-k")

	def down(request):
		return httpx.Response(503, text="unavailable")

	catalog = await available_models(store, client=_client(down))
	assert [m.name for m in catalog.models] == [
		"orcarouter/anthropic/claude-opus-4.8",
		"orcarouter/auto",
		"orcarouter/deepseek/deepseek-v4-pro",
		"orcarouter/google/gemini-3.5-flash",
		"orcarouter/openai/gpt-5.5",
	]
	assert len(catalog.errors) == 1 and catalog.errors[0].startswith("orcarouter:")

	def up(request):
		return httpx.Response(200, json={"data": [ROW]})

	live = await available_models(store, client=_client(up))
	# live results are the whole catalog: the seed is not appended to them
	assert [m.name for m in live.models] == ["orcarouter/openai/gpt-5.5"]
	assert live.errors == []


def test_seed_entries_never_invent_what_the_catalog_did_not_verify():
	seed = {remote: (label, meta) for remote, label, meta in orcarouter.seed_models()}
	assert set(seed) == {
		"openai/gpt-5.5",
		"anthropic/claude-opus-4.8",
		"google/gemini-3.5-flash",
		"deepseek/deepseek-v4-pro",
		AUTO_MODEL,
	}
	for _remote, (_label, meta) in seed.items():
		assert meta.context_window is None
		assert meta.max_output_tokens is None
		# an entry is text-only unless the seed says it takes images, and none do
		assert meta.input_modalities == frozenset({"text"})


def test_reasoning_efforts_come_from_the_declared_parameters():
	assert reasoning_efforts({"supported_parameters": ["reasoning_effort"]}) == (
		"low",
		"medium",
		"high",
		"xhigh",
	)
	assert reasoning_efforts({"supported_parameters": ["thinking"]}) == ("medium",)
	assert reasoning_efforts({"supported_parameters": ["tools"]}) == ()
	assert reasoning_efforts({}) == ()


def test_the_verified_ladder_survives_into_reasoning_params():
	remember_catalog([ROW])
	assert reasoning_params("orcarouter/openai/gpt-5.5", "xhigh") == {
		"reasoning_effort": "xhigh",
		"allowed_openai_params": ["reasoning_effort"],
	}
	# a level the model does not offer is clamped down to the nearest it does
	assert reasoning_params("orcarouter/openai/gpt-5.5", "max")["reasoning_effort"] == "xhigh"
	assert reasoning_params("orcarouter/openai/gpt-5.5", "minimal")["reasoning_effort"] == "low"


def test_a_model_without_reasoning_support_gets_no_reasoning_param():
	remember_catalog([{"id": "acme/plain", "supported_endpoint_types": ["openai"]}])
	assert reasoning_params("orcarouter/acme/plain", "high") is None
	# unknown models are left to the gateway rather than refused
	assert reasoning_params("orcarouter/acme/never-seen", "high") == {
		"reasoning_effort": "high",
		"allowed_openai_params": ["reasoning_effort"],
	}


def test_names_round_trip_between_flow_and_the_wire():
	assert flow_model_name("openai/gpt-5.5") == "orcarouter/openai/gpt-5.5"
	assert flow_model_name("orcarouter/openai/gpt-5.5") == "orcarouter/openai/gpt-5.5"
	assert wire_model_id("orcarouter/openai/gpt-5.5") == "openai/gpt-5.5"
	# the gateway's own routing alias already carries the namespace
	assert flow_model_name(AUTO_MODEL) == AUTO_MODEL
	assert wire_model_id(AUTO_MODEL) == AUTO_MODEL


def test_image_support_is_fail_closed_for_unadvertised_models():
	assert model_supports_images("orcarouter/auto") is False
	assert model_supports_images("orcarouter/acme/unlisted") is None
	remember_catalog(
		[
			{
				"id": "acme/vision",
				"supported_endpoint_types": ["openai"],
				"architecture": {"input_modalities": ["text", "image"]},
			}
		]
	)
	assert model_supports_images("orcarouter/acme/vision") is True


def test_the_model_uses_the_openai_compatible_path_with_catalog_limits():
	remember_catalog([ROW])
	model = orcarouter_model("orcarouter/openai/gpt-5.5", api_key="sk-orca-k")

	assert model.name == "openai/openai/gpt-5.5"
	assert model.provider == "orcarouter"
	assert model.model == "orcarouter/openai/gpt-5.5"
	assert model.context_window == 400_000
	assert model.max_output_tokens == 128_000
	assert model.supports_images is False

	with pytest.raises(ValueError):
		orcarouter_model("gpt-5.5")


async def test_the_sign_in_round_trip_against_a_local_origin(monkeypatch):
	"""The adapter's own URLs, over a real loopback HTTP server, with the shared base override."""
	import json
	import threading
	from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

	seen = {}

	class Handler(BaseHTTPRequestHandler):
		def do_POST(self):
			seen["path"] = self.path
			seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
			ok = seen["body"]["code"] == "the-code"
			payload = json.dumps(
				{"key": "sk-orca-local", "scope": "api", "user_id": 7} if ok else {"error": "bad code"}
			).encode()
			self.send_response(200 if ok else 403)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", str(len(payload)))
			self.end_headers()
			self.wfile.write(payload)

		def log_message(self, *args):
			pass

	server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
	threading.Thread(target=server.serve_forever, daemon=True).start()
	port = server.server_address[1]
	try:
		monkeypatch.setenv("ORCA_BASE_URL", f"http://127.0.0.1:{port}")
		pkce = generate_pkce()
		url = authorize_url(pkce.challenge, "st-local")
		assert url.startswith(f"http://127.0.0.1:{port}/auth?"), url
		assert dict(httpx.URL(url).params)["code_challenge"] == pkce.challenge
		assert orcarouter.api_base_url() == f"http://127.0.0.1:{port}/v1"

		credential = await OrcaRouterAuthProvider().exchange("the-code", pkce.verifier)

		assert seen["path"] == "/api/v1/auth/keys"
		assert seen["body"] == {
			"code": "the-code",
			"code_verifier": pkce.verifier,
			"code_challenge_method": "S256",
		}
		assert credential.access == "sk-orca-local"
		assert credential.account_id == "7"
		assert credential.is_durable
	finally:
		server.shutdown()
		server.server_close()
