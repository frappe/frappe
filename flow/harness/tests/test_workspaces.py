"""Workspaces: the web UI's named folders, and the workspace each listed chat is in."""

import os

from fastapi.testclient import TestClient

from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.session import workspaces
from flow_harness.session.store import SessionStore


def _client(tmp_path, **store_kw) -> TestClient:
	credentials = CredentialStore(str(tmp_path / "credentials.json"))
	return TestClient(
		create_app(SessionStore(str(tmp_path / "data"), credential_store=credentials, **store_kw))
	)


def _chat(client: TestClient, cwd) -> str:
	sid = client.post("/sessions", json={"model": "mock", "cwd": str(cwd)}).json()["session_id"]
	client.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})
	return sid


def _workspace_of(client: TestClient, sid: str) -> str | None:
	rows = client.get("/sessions").json()["sessions"]
	return next(row["workspace"] for row in rows if row["session_id"] == sid)


def test_workspaces_start_from_the_chats_or_a_default_and_keep_folders_and_chats_when_removed(tmp_path):
	c = _client(tmp_path)
	# the first listing, with no chats yet, makes the default workspace
	default = os.path.realpath(workspaces.DEFAULT_WORKSPACE)
	assert c.get("/workspaces").json() == {"workspaces": [{"path": default, "name": "default-workspace"}]}
	assert os.path.isdir(default)
	assert oct(os.stat(tmp_path / "data" / "workspaces.json").st_mode & 0o777) == "0o600"

	# a chat joins its folder's workspace with its first message, the same one through a symlink
	app = tmp_path / "app"
	app.mkdir()
	(tmp_path / "link").symlink_to(app)
	path = os.path.realpath(app)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path / "link")}).json()["session_id"]
	assert len(c.get("/workspaces").json()["workspaces"]) == 1
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})
	assert c.get("/workspaces").json()["workspaces"][-1] == {"path": path, "name": "app"}
	assert _workspace_of(c, _chat(c, app)) == _workspace_of(c, sid) == path
	assert len(c.get("/workspaces").json()["workspaces"]) == 2

	# a rename changes the name alone
	assert c.patch("/workspaces", json={"path": path, "name": " Shop "}).json() == {
		"workspace": {"path": path, "name": "Shop"}
	}
	assert _workspace_of(c, sid) == path

	# removed, it leaves its folder and chats, which are then in none, even as they go on or start
	# over from a rewind; a new chat there brings it back, with them
	assert c.delete("/workspaces", params={"path": path}).json() == {"status": "removed"}
	assert app.is_dir()
	assert _workspace_of(c, sid) is None
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "again"})
	assert _workspace_of(c, sid) is None
	assert c.post(f"/sessions/{sid}/rewind", json={"target_seq": 0}).json() == {"status": "rewound"}
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "anew"})
	assert _workspace_of(c, sid) is None
	_chat(c, app)
	assert _workspace_of(c, sid) == path
	assert c.get("/workspaces").json()["workspaces"][-1] == {"path": path, "name": "app"}

	# an existing folder is added as it is, once, and only inside the allowed roots
	other = tmp_path / "other"
	other.mkdir()
	added = c.post("/workspaces", json={"path": str(other)}).json()["workspace"]
	assert added == {"path": os.path.realpath(other), "name": "other"}
	assert c.post("/workspaces", json={"path": str(other)}).json()["workspace"] == added
	for wrong in (str(tmp_path / "missing"), "other", str(tmp_path / "data" / "workspaces.json")):
		assert c.post("/workspaces", json={"path": wrong}).status_code == 400, wrong
	fenced = _client(tmp_path / "fenced", allowed_roots=[str(app)])
	assert fenced.get("/workspaces").json() == {"workspaces": []}  # the default lies outside
	assert fenced.post("/workspaces", json={"path": str(other)}).status_code == 400
	assert c.patch("/workspaces", json={"path": str(tmp_path / "nowhere"), "name": "x"}).status_code == 404
	assert c.patch("/workspaces", json={"path": path, "name": "  "}).status_code == 400
	assert c.delete("/workspaces", params={"path": str(tmp_path / "nowhere")}).status_code == 404

	# chats from before the first listing are in none until it, which adds their folders, oldest
	# first, and makes no default
	os.rmdir(default)
	c = _client(tmp_path / "older")
	sids = [_chat(c, folder) for folder in (app, other)]
	assert {_workspace_of(c, sid) for sid in sids} == {None}
	assert [w["name"] for w in c.get("/workspaces").json()["workspaces"]] == ["app", "other"]
	assert [_workspace_of(c, sid) for sid in sids] == [path, os.path.realpath(other)]
	assert not os.path.exists(default)
