import importlib
import json

import pytest
from fastapi.testclient import TestClient

from flow_harness import config
from flow_harness.cli.daemon import DaemonError
from flow_harness.cli.login import _parse_callback, login, logout, show_providers
from flow_harness.cli.main import _is_loopback, _resolve_auth_token, _with_default_command
from flow_harness.model.credentials import CredentialStore


def test_login_status_and_logout_never_print_secrets(tmp_path, monkeypatch, capsys):
	store = CredentialStore(str(tmp_path / "credentials.json"))
	monkeypatch.setattr("getpass.getpass", lambda prompt: " secret-key ")
	monkeypatch.setenv("ANTHROPIC_API_KEY", "do-not-print")

	login(store, "openai")
	show_providers(store)
	output = capsys.readouterr().out
	assert "Saved API key for OpenAI API." in output
	assert "openai" in output and "stored API key" in output
	assert "ANTHROPIC_API_KEY" in output  # an environment key shows by name only
	assert "secret-key" not in output
	assert "do-not-print" not in output

	logout(store, "openai")
	assert store.get("openai") is None


def test_manual_callback_parser():
	assert _parse_callback("http://localhost:1455/auth/callback?code=C&state=S") == ("C", "S")
	assert _parse_callback("code=C&state=S") == ("C", "S")
	assert _parse_callback("C#S") == ("C", "S")


def test_loopback_detection():
	assert _is_loopback("localhost")
	assert _is_loopback("127.0.0.1")
	assert _is_loopback("::1")
	assert not _is_loopback("0.0.0.0")
	assert not _is_loopback("example.com")


def test_resolve_auth_token(tmp_path, monkeypatch):
	token_file = tmp_path / "token"
	token_file.write_text("file-token\n")
	monkeypatch.setattr(config, "AUTH_TOKEN", "env-token")
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", str(token_file))
	assert _resolve_auth_token() == "env-token"
	monkeypatch.setattr(config, "AUTH_TOKEN", None)
	assert _resolve_auth_token() == "file-token"
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	assert _resolve_auth_token() is None

	# a missing or empty token file fails loudly
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", str(tmp_path / "missing"))
	with pytest.raises(DaemonError, match="cannot read"):
		_resolve_auth_token()
	empty = tmp_path / "empty"
	empty.write_text(" \n")
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", str(empty))
	with pytest.raises(DaemonError, match="empty"):
		_resolve_auth_token()


def test_bare_invocation_defaults_to_web():
	commands = {"tui", "web", "serve", "attach", "login", "providers", "logout"}
	assert _with_default_command([], commands) == ["web"]
	assert _with_default_command(["--no-browser"], commands) == ["web", "--no-browser"]
	assert _with_default_command(["tui", "-c"], commands) == ["tui", "-c"]
	assert _with_default_command(["serve", "--port", "9001"], commands) == ["serve", "--port", "9001"]
	assert _with_default_command(["login", "openai"], commands) == ["login", "openai"]
	assert _with_default_command(["--help"], commands) == ["--help"]
	assert _with_default_command(["--version"], commands) == ["--version"]
	assert _with_default_command(["attach", "--url", "http://x"], commands) == [
		"attach",
		"--url",
		"http://x",
	]


def test_redis_sink_config(monkeypatch):
	cli = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "REDIS_URL", None)
	assert cli._redis_sink() is None

	# a bad URL is a clean config error that does not echo its credentials
	for url in ("https://secret:password@redis", "redis://secret:password@redis:bad"):
		monkeypatch.setattr(config, "REDIS_URL", url)
		with pytest.raises(DaemonError, match=r"^invalid FLOW_REDIS_URL$"):
			cli._redis_sink()

	monkeypatch.setattr("flow_harness.server.redis_sink.RedisEventSink", lambda url, **kwargs: (url, kwargs))
	monkeypatch.setattr(config, "REDIS_URL", "redis://unused")
	monkeypatch.setattr(config, "REDIS_MAX_PENDING", "8000")
	monkeypatch.setattr(config, "REDIS_MAX_PENDING_PER_SITE", "1000")
	assert cli._redis_sink() == (
		"redis://unused",
		{"max_pending": 8000, "max_pending_per_site": 1000},
	)

	for name in ("MAX_PENDING", "MAX_PENDING_PER_SITE"):
		for value in ("0", "-1", "", "1.5", "invalid"):
			monkeypatch.setattr(config, f"REDIS_{name}", value)
			with pytest.raises(DaemonError, match=f"FLOW_REDIS_{name} must be a positive integer"):
				cli._redis_sink()
		monkeypatch.setattr(config, f"REDIS_{name}", "1")

	# the limits are not checked while Redis is off
	monkeypatch.setattr(config, "REDIS_MAX_PENDING", "invalid")
	monkeypatch.setattr(config, "REDIS_URL", None)
	assert cli._redis_sink() is None


def test_cli_wires_redis_to_the_server_lifespan(tmp_path, monkeypatch):
	cli = importlib.import_module("flow_harness.cli.main")
	redis = []
	closed = []

	class Client:
		async def publish(self, _channel, message):
			redis.append(json.loads(message))

		async def aclose(self):
			closed.append(True)

	def run_server(app, **_kwargs):
		with TestClient(app) as client:
			sid = client.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
			assert (
				client.post(
					f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"}
				).status_code
				== 200
			)
			assert closed == []

	monkeypatch.setattr("redis.asyncio.from_url", lambda *_args, **_kwargs: Client())
	monkeypatch.setattr(cli, "_run_server", lambda app, _store, **kwargs: run_server(app, **kwargs))
	monkeypatch.setattr("flow_harness.server.logs.setup_terminal_logging", lambda: None)
	monkeypatch.setattr(cli, "_warm_litellm", lambda: None)
	monkeypatch.setattr(cli, "_resolve_auth_token", lambda: None)
	monkeypatch.setattr(cli, "_webui_dist", lambda: str(tmp_path))
	monkeypatch.setattr(config, "REDIS_URL", "redis://unused")
	monkeypatch.setattr(config, "TENANTS", None)
	monkeypatch.setattr(config, "POLICY", None)
	monkeypatch.setattr(config, "ALLOWED_ROOTS", [])
	monkeypatch.setattr(config, "CREDENTIALS_PATH", str(tmp_path / "credentials.json"))
	for command, options in (("serve", ["--profile", "local"]), ("web", ["--no-browser"])):
		redis.clear()
		closed.clear()
		monkeypatch.setattr(
			"sys.argv",
			[
				"flow",
				command,
				"--host",
				"127.0.0.1",
				"--data-dir",
				str(tmp_path / command),
				"--no-extensions",
				*options,
			],
		)
		cli.main()
		assert redis[-1]["type"] == "run_ended", command
		assert closed == [True], command
