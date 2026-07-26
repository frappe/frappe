from flow_server.cli.auth import _parse_callback, login, logout, show_providers
from flow_server.cli.main import _is_loopback
from flow_server.model.credentials import CredentialStore


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
