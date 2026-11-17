"""The credential store: one owner-only JSON file, atomic writes, typed entries."""

import os

from flow_harness.model.credentials import ApiKeyCredential, CredentialStore, OAuthCredential


def test_roundtrip_with_typed_getters_and_listing(tmp_path):
	store = CredentialStore(str(tmp_path / "creds.json"))
	assert store.get("codex") is None
	store.set("codex", OAuthCredential(access="a", refresh="r", expires=123, account_id="acc"))
	assert store.get("codex") == OAuthCredential(access="a", refresh="r", expires=123, account_id="acc")

	store.set_api_key("anthropic", " sk-test ")
	assert store.get("anthropic") == ApiKeyCredential(key="sk-test")
	assert store.get_api_key("anthropic").key == "sk-test"
	assert store.get_oauth("anthropic") is None
	assert [(info.provider_id, info.type) for info in store.list()] == [
		("anthropic", "api_key"),
		("codex", "oauth"),
	]

	store.delete("codex")
	assert store.get("codex") is None


def test_file_is_0600_in_a_0700_directory_and_repaired_on_access(tmp_path):
	path = tmp_path / "sub" / "creds.json"
	store = CredentialStore(str(path))
	store.set("codex", OAuthCredential(access="a", refresh="r", expires=1))
	assert oct(os.stat(path).st_mode & 0o777) == "0o600"
	assert oct(os.stat(path.parent).st_mode & 0o777) == "0o700"

	# a file written or loosened outside the store is tightened on the next read
	loose = tmp_path / "creds.json"
	loose.write_text('{"openai":{"type":"api_key","key":"secret"}}')
	loose.chmod(0o644)

	assert CredentialStore(str(loose)).get_api_key("openai").key == "secret"
	assert oct(os.stat(loose).st_mode & 0o777) == "0o600"
