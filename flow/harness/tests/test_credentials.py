"""The credential store: one owner-only JSON file, atomic writes, typed entries."""

import os

from flow_server.model.credentials import ApiKeyCredential, CredentialStore, OAuthCredential


def test_roundtrip(tmp_path):
	store = CredentialStore(str(tmp_path / "creds.json"))
	assert store.get("codex") is None
	store.set("codex", OAuthCredential(access="a", refresh="r", expires=123, account_id="acc"))
	assert store.get("codex") == OAuthCredential(access="a", refresh="r", expires=123, account_id="acc")
	store.delete("codex")
	assert store.get("codex") is None


def test_typed_getters_and_listing(tmp_path):
	store = CredentialStore(str(tmp_path / "creds.json"))
	store.set_api_key("anthropic", " sk-test ")

	assert store.get("anthropic") == ApiKeyCredential(key="sk-test")
	assert store.get_api_key("anthropic").key == "sk-test"
	assert store.get_oauth("anthropic") is None
	assert store.list()[0].provider_id == "anthropic"
	assert store.list()[0].type == "api_key"


def test_file_is_0600_in_a_0700_directory(tmp_path):
	path = tmp_path / "sub" / "creds.json"
	store = CredentialStore(str(path))
	store.set("codex", OAuthCredential(access="a", refresh="r", expires=1))
	assert oct(os.stat(path).st_mode & 0o777) == "0o600"
	assert oct(os.stat(path.parent).st_mode & 0o777) == "0o700"


def test_repairs_file_permissions_on_access(tmp_path):
	path = tmp_path / "creds.json"
	path.write_text('{"openai":{"type":"api_key","key":"secret"}}')
	path.chmod(0o644)

	assert CredentialStore(str(path)).get_api_key("openai").key == "secret"
	assert oct(os.stat(path).st_mode & 0o777) == "0o600"
