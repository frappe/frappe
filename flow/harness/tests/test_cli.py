import importlib
import json

import pytest
from fastapi.testclient import TestClient

from flow_harness import __version__, config
from flow_harness.cli.daemon import DaemonError
from flow_harness.cli.login import _parse_callback, login, logout, show_providers
from flow_harness.cli.main import _is_loopback, _resolve_auth_token, _with_default_command
from flow_harness.model.credentials import CredentialStore


def test_api_key_login_status_and_logout(tmp_path, monkeypatch, capsys):
	store = CredentialStore(str(tmp_path / "credentials.json"))
	monkeypatch.setattr("getpass.getpass", lambda prompt: " secret-key ")

	login(store, "openai")
	show_providers(store)
	output = capsys.readouterr().out
	assert "Saved API key for OpenAI API." in output
	assert "openai" in output and "stored API key" in output
	assert "secret-key" not in output

	logout(store, "openai")
	assert store.get("openai") is None


def test_provider_status_uses_environment_without_revealing_value(tmp_path, monkeypatch, capsys):
	store = CredentialStore(str(tmp_path / "credentials.json"))
	monkeypatch.setenv("ANTHROPIC_API_KEY", "do-not-print")

	show_providers(store)
	output = capsys.readouterr().out
	assert "ANTHROPIC_API_KEY" in output
	assert "do-not-print" not in output


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


def test_resolve_auth_token_prefers_env_then_file(tmp_path, monkeypatch):
	token_file = tmp_path / "token"
	token_file.write_text("file-token\n")
	monkeypatch.setattr(config, "AUTH_TOKEN", "env-token")
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", str(token_file))
	assert _resolve_auth_token() == "env-token"
	monkeypatch.setattr(config, "AUTH_TOKEN", None)
	assert _resolve_auth_token() == "file-token"
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	assert _resolve_auth_token() is None


def test_resolve_auth_token_rejects_missing_or_empty_file(tmp_path, monkeypatch):
	monkeypatch.setattr(config, "AUTH_TOKEN", None)
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


def test_version_flag(monkeypatch, capsys):
	cli = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr("sys.argv", ["flow", "--version"])
	with pytest.raises(SystemExit) as exc:
		cli.main()
	assert exc.value.code == 0
	assert capsys.readouterr().out.strip() == f"flow {__version__}"


def test_redis_sink_is_optional(monkeypatch):
	cli = importlib.import_module("flow_harness.cli.main")
	sink = object()
	monkeypatch.setattr(config, "REDIS_URL", "redis://unused")
	monkeypatch.setattr("flow_harness.server.redis_sink.RedisEventSink", lambda _url, **_kwargs: sink)
	assert cli._redis_sink() is sink

	monkeypatch.setattr(config, "REDIS_URL", None)
	assert cli._redis_sink() is None


def test_redis_queue_limits_are_passed_to_the_sink(monkeypatch):
	cli = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "REDIS_URL", "redis://unused")
	monkeypatch.setattr(config, "REDIS_MAX_PENDING", "8000")
	monkeypatch.setattr(config, "REDIS_MAX_PENDING_PER_SITE", "1000")
	monkeypatch.setattr("flow_harness.server.redis_sink.RedisEventSink", lambda url, **kwargs: (url, kwargs))
	assert cli._redis_sink() == (
		"redis://unused",
		{"max_pending": 8000, "max_pending_per_site": 1000},
	)


@pytest.mark.parametrize("name", ["MAX_PENDING", "MAX_PENDING_PER_SITE"])
@pytest.mark.parametrize("value", ["0", "-1", "", "1.5", "invalid"])
def test_invalid_redis_queue_limits_are_clean_config_errors(monkeypatch, name, value):
	cli = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "REDIS_URL", "redis://unused")
	monkeypatch.setattr(config, f"REDIS_{name}", value)
	with pytest.raises(DaemonError, match=f"FLOW_REDIS_{name} must be a positive integer"):
		cli._redis_sink()
	monkeypatch.setattr(config, "REDIS_URL", None)
	assert cli._redis_sink() is None


@pytest.mark.parametrize("url", ["https://secret:password@redis", "redis://secret:password@redis:bad"])
def test_invalid_redis_urls_are_clean_config_errors(monkeypatch, url):
	cli = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "REDIS_URL", url)
	with pytest.raises(DaemonError, match=r"^invalid FLOW_REDIS_URL$"):
		cli._redis_sink()


@pytest.mark.parametrize("command", ["serve", "web"])
def test_cli_wires_redis_to_the_server_lifespan(tmp_path, monkeypatch, command):
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
	monkeypatch.setattr("uvicorn.run", run_server)
	monkeypatch.setattr("flow_harness.server.logs.setup_terminal_logging", lambda: None)
	monkeypatch.setattr(cli, "_warm_litellm", lambda: None)
	monkeypatch.setattr(cli, "_resolve_auth_token", lambda: None)
	monkeypatch.setattr(cli, "_webui_dist", lambda: str(tmp_path))
	monkeypatch.setattr(config, "REDIS_URL", "redis://unused")
	monkeypatch.setattr(config, "TENANTS_FILE", None)
	monkeypatch.setattr(config, "POLICY", None)
	monkeypatch.setattr(config, "ALLOWED_ROOTS", [])
	monkeypatch.setattr(config, "CREDENTIALS_PATH", str(tmp_path / "credentials.json"))
	options = ["--profile", "local"] if command == "serve" else ["--no-browser"]
	monkeypatch.setattr(
		"sys.argv",
		[
			"flow",
			command,
			"--host",
			"127.0.0.1",
			"--data-dir",
			str(tmp_path / "data"),
			"--no-extensions",
			*options,
		],
	)
	cli.main()
	assert redis[-1]["type"] == "run_ended"
	assert closed == [True]
