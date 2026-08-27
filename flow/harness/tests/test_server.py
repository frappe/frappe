import asyncio
import difflib
import json
import os
import shlex
import socket
import subprocess

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from flow.events import AssistantMessage, ToolCall, Usage
from flow.model import Model, ModelRequest
from flow.model.credentials import CredentialStore
from flow.model.mock import MockModel
from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.store import SessionStore


def _client(tmp_path, **store_kw):
	store_kw.setdefault(
		"credential_store",
		CredentialStore(str(tmp_path / "credentials.json")),
	)
	store = SessionStore(str(tmp_path / "data"), **store_kw)
	return TestClient(create_app(store))


def test_healthz(tmp_path):
	assert _client(tmp_path).get("/healthz").json() == {"ok": True}


def test_daemon_bearer_auth(tmp_path):
	store = SessionStore(str(tmp_path / "data"))
	c = TestClient(create_app(store, auth_token="daemon-secret"))

	assert c.get("/healthz").status_code == 200
	assert c.post("/sessions", json={"cwd": str(tmp_path)}).status_code == 401
	assert (
		c.post(
			"/sessions",
			json={"cwd": str(tmp_path)},
			headers={"Authorization": "Bearer wrong"},
		).status_code
		== 401
	)
	assert (
		c.post(
			"/sessions",
			json={"cwd": str(tmp_path)},
			headers={"Authorization": "Bearer daemon-secret"},
		).status_code
		== 200
	)


def test_create_prompt_wait_and_entries(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	# blocking prompt returns the terminal summary (Flow-like synchronous response)
	r = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hello"})
	res = r.json()
	assert res["reason"] == "done"
	assert "Mock reply" in res["output"]
	# the durable log replays the whole turn
	types = [e["type"] for e in c.get(f"/sessions/{sid}/entries").json()["entries"]]
	assert types[0] == "run_started"
	assert "user_message" in types and "assistant_message" in types
	assert types[-1] == "run_ended"


def test_wait_summary_includes_cache_usage(tmp_path, monkeypatch):
	class CacheUsageModel(Model):
		async def run(self, request):
			yield AssistantMessage(content="cached")
			yield Usage(
				input_tokens=100,
				output_tokens=5,
				cache_read_tokens=80,
				cache_write_tokens=10,
			)

	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: CacheUsageModel())
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]

	usage = c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "hello"},
	).json()["usage"]

	assert usage == {
		"input_tokens": 100,
		"output_tokens": 5,
		"cache_read_tokens": 80,
		"cache_write_tokens": 10,
	}


def test_set_model_is_a_durable_entry_used_by_later_runs(tmp_path, monkeypatch):
	resolved = []

	def spy(name, **kwargs):
		resolved.append(name)
		return MockModel()

	monkeypatch.setattr("flow.agent.loop.get_model", spy)
	monkeypatch.setattr(
		"flow.server.app.context_window_for",
		lambda model: 1_000_000 if model == "mock/v2" else None,
	)
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]

	r = c.post(f"/sessions/{sid}/model", json={"model": "mock/v2", "credential_id": "mock-profile"})
	assert r.json() == {
		"model": "mock/v2",
		"credential_id": "mock-profile",
		"reasoning_effort": None,
		"context_window": 1_000_000,
		"supports_images": False,
	}
	assert (
		c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"}).json()["reason"]
		== "done"
	)
	assert resolved == ["mock/v2"]

	info = c.get(f"/sessions/{sid}").json()
	assert (info["model"], info["credential_id"]) == ("mock/v2", "mock-profile")
	assert info["config"]["model"] == "mock"  # the creation config is fixed
	assert c.get(f"/sessions/{sid}/entries").json()["entries"][0]["type"] == "model_changed"


def test_reasoning_effort_travels_with_the_selection_and_rewinds_with_it(tmp_path, monkeypatch):
	captured = []

	def spy(name, **kwargs):
		captured.append(kwargs.get("params"))
		return MockModel()

	monkeypatch.setattr("flow.agent.loop.get_model", spy)
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path), "reasoning_effort": "low"}).json()[
		"session_id"
	]
	assert c.get(f"/sessions/{sid}").json()["reasoning_effort"] == "low"

	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})
	assert [p["reasoning_effort"] for p in captured] == ["low"]
	branch_point = c.get(f"/sessions/{sid}").json()["latest_seq"]

	# same model, different effort: still a durable selection change
	r = c.post(f"/sessions/{sid}/model", json={"model": "mock", "reasoning_effort": "high"})
	assert r.json() == {
		"model": "mock",
		"credential_id": None,
		"reasoning_effort": "high",
		"context_window": None,
		"supports_images": False,
	}
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "again"})
	assert captured[-1]["reasoning_effort"] == "high"

	# rewinding to before the change restores the creation-config effort
	c.post(f"/sessions/{sid}/rewind", json={"target_seq": branch_point})
	assert c.get(f"/sessions/{sid}").json()["reasoning_effort"] == "low"
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "back"})
	assert captured[-1]["reasoning_effort"] == "low"


def test_run_does_not_accept_model_overrides(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	r = c.post(f"/sessions/{sid}/run", json={"message": "hi", "model": "mock/v2"})
	assert r.status_code == 422  # model changes go through POST /sessions/{sid}/model


def test_provider_secrets_and_endpoints_are_not_client_inputs(tmp_path):
	c = _client(tmp_path)
	for field, value in (("api_key", "secret"), ("api_base", "https://attacker.test")):
		response = c.post(
			"/sessions",
			json={"model": "mock", "cwd": str(tmp_path), field: value},
		)
		assert response.status_code == 422

	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	for field, value in (("api_key", "secret"), ("api_base", "https://attacker.test")):
		response = c.post(
			f"/sessions/{sid}/run",
			json={"message": "hello", field: value},
		)
		assert response.status_code == 422


def test_unknown_session_404(tmp_path):
	assert _client(tmp_path).get("/sessions/nope").status_code == 404


def test_resume_without_pending_is_rejected_without_writing_events(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	res = c.post(
		f"/sessions/{sid}/resume",
		params={"wait": "true"},
		json={"approval_seq": 1, "answers": {}},
	)
	assert res.status_code == 409
	assert c.get(f"/sessions/{sid}/entries").json()["entries"] == []


def test_abort_idle(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	assert c.post(f"/sessions/{sid}/abort").json()["status"] == "idle"


def test_read_workspace_file(tmp_path):
	c = _client(tmp_path)
	(tmp_path / "notes.txt").write_text("hello\nworld\n")

	r = c.get("/fs/file", params={"cwd": str(tmp_path), "path": "notes.txt"})
	assert r.status_code == 200
	assert r.json() == {"path": str(tmp_path / "notes.txt"), "content": "hello\nworld\n"}

	assert c.get("/fs/file", params={"cwd": str(tmp_path), "path": "missing.txt"}).status_code == 404

	(tmp_path / "blob.bin").write_bytes(b"\xff\xfe\x00garbage\x80")
	assert c.get("/fs/file", params={"cwd": str(tmp_path), "path": "blob.bin"}).status_code == 415


def test_list_workspace_files(tmp_path):
	c = _client(tmp_path)
	work = tmp_path / "work"
	(work / "src").mkdir(parents=True)
	(work / "src" / "app.py").write_text("x")
	(work / "zeta.txt").write_text("x")
	(work / "Alpha.txt").write_text("x")

	r = c.get("/fs/files", params={"cwd": str(work)})  # default path lists the cwd
	assert r.status_code == 200
	body = r.json()
	assert body["path"] == str(work)
	names = [(e["name"], e["type"]) for e in body["entries"]]
	# directories first, then case-insensitive alphabetical
	assert names == [("src", "dir"), ("Alpha.txt", "file"), ("zeta.txt", "file")]

	sub = c.get("/fs/files", params={"cwd": str(work), "path": "src"}).json()
	assert sub["entries"] == [{"name": "app.py", "type": "file"}]

	assert c.get("/fs/files", params={"cwd": str(work), "path": "missing"}).status_code == 404
	assert c.get("/fs/files", params={"cwd": str(work), "path": "zeta.txt"}).status_code == 400
	assert c.get("/fs/files", params={"cwd": "relative/path"}).status_code == 400


def test_search_workspace_files(tmp_path):
	c = _client(tmp_path)
	work = tmp_path / "work"
	(work / "src" / "deep").mkdir(parents=True)
	(work / "node_modules" / "pkg").mkdir(parents=True)
	(work / ".git").mkdir()
	(work / "app.py").write_text("x")
	(work / "src" / "deep" / "app_helpers.py").write_text("x")
	(work / "src" / "readme.md").write_text("x")
	(work / "node_modules" / "pkg" / "app.py").write_text("x")
	(work / ".git" / "app.py").write_text("x")

	body = c.get("/fs/files/search", params={"cwd": str(work), "query": "APP"}).json()
	assert body["path"] == str(work)
	# hidden and dependency trees are pruned; matching is case-insensitive
	assert body["matches"] == ["app.py", "src/deep/app_helpers.py"]
	assert body["truncated"] is False

	assert c.get("/fs/files/search", params={"cwd": str(work), "query": "  "}).json()["matches"] == []
	gone = c.get("/fs/files/search", params={"cwd": str(work / "gone"), "query": "app"})
	assert gone.status_code == 404


def test_workspace_files_are_fenced_by_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	(tmp_path / "secret.txt").write_text("nope")
	(allowed / "ok.txt").write_text("fine")
	c = _client(tmp_path, allowed_roots=[str(allowed)])

	assert c.get("/fs/file", params={"cwd": str(allowed), "path": "ok.txt"}).status_code == 200
	assert c.get("/fs/file", params={"cwd": str(allowed), "path": "../secret.txt"}).status_code == 403
	assert (
		c.get("/fs/file", params={"cwd": str(allowed), "path": str(tmp_path / "secret.txt")}).status_code
		== 403
	)
	assert c.get("/fs/files", params={"cwd": str(allowed)}).status_code == 200
	assert c.get("/fs/files", params={"cwd": str(allowed), "path": ".."}).status_code == 403
	assert c.get("/fs/files", params={"cwd": str(tmp_path)}).status_code == 403
	assert c.get("/fs/files/search", params={"cwd": str(tmp_path), "query": "x"}).status_code == 403


def test_write_workspace_file(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]

	# parent directories are created, and the write round-trips through the read endpoint
	r = c.put(f"/sessions/{sid}/file", json={"path": "new/notes.txt", "content": "draft\n"})
	assert r.status_code == 200
	assert (tmp_path / "new" / "notes.txt").read_text() == "draft\n"
	read = c.get("/fs/file", params={"cwd": str(tmp_path), "path": "new/notes.txt"})
	assert read.json()["content"] == "draft\n"
	# writing over a directory is a client error, not a 500
	assert c.put(f"/sessions/{sid}/file", json={"path": "new", "content": "x"}).status_code == 400


def test_write_workspace_file_is_fenced_by_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	c = _client(tmp_path, allowed_roots=[str(allowed)])
	sid = c.post("/sessions", json={"cwd": str(allowed)}).json()["session_id"]

	assert c.put(f"/sessions/{sid}/file", json={"path": "ok.txt", "content": "x"}).status_code == 200
	assert c.put(f"/sessions/{sid}/file", json={"path": "../escape.txt", "content": "x"}).status_code == 403
	assert not (tmp_path / "escape.txt").exists()


def _append_log_rows(tmp_path, sid, rows):
	"""Fabricate durable tool_result rows, chained onto the session's log tip."""
	meta = next((tmp_path / "data" / "sessions").rglob(f"{sid}.meta.json"))
	log = meta.with_name(f"{sid}.jsonl")  # created lazily on the first real append
	existing = (
		[json.loads(line) for line in log.read_text().splitlines() if line.strip()] if log.exists() else []
	)
	seq = existing[-1]["seq"] if existing else 0
	with log.open("a") as f:
		for row in rows:
			seq += 1
			f.write(json.dumps({"seq": seq, "parent_seq": seq - 1, "ts": 0.0, **row}) + "\n")


def _edit_result(path, old, new, call_id="edit-1"):
	diff = "".join(
		difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), path, path)
	)
	return {
		"type": "tool_result",
		"tool_call_id": call_id,
		"name": "edit",
		"content": f"[edited {path} (1 block(s))]",
		"details": {"path": path, "edits": 1, "lines_added": 1, "lines_removed": 1, "diff": diff},
	}


def test_file_diff_reconstructs_original_from_edits(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	target = tmp_path / "app.py"
	v0 = "a\nb\nc\n"
	v1 = "a\nB\nc\n"
	v2 = "a\nB\nc\nd\n"
	target.write_text(v2)
	_append_log_rows(
		tmp_path,
		sid,
		[_edit_result(str(target), v0, v1, "e1"), _edit_result(str(target), v1, v2, "e2")],
	)

	r = c.get(f"/sessions/{sid}/file/diff", params={"path": "app.py"})
	assert r.status_code == 200
	assert r.json() == {"path": str(target), "original": v0, "modified": v2}


def test_file_diff_write_counts_as_created(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	target = tmp_path / "new.py"
	v1 = "print('hi')\n"
	v2 = "print('hi')\nprint('bye')\n"
	target.write_text(v2)
	_append_log_rows(
		tmp_path,
		sid,
		[
			{
				"type": "tool_result",
				"tool_call_id": "w1",
				"name": "write",
				"content": f"[wrote {target} (1 lines)]",
				"details": {"path": str(target), "chars": len(v1), "lines": 1},
			},
			_edit_result(str(target), v1, v2),
		],
	)

	r = c.get(f"/sessions/{sid}/file/diff", params={"path": "new.py"})
	assert r.status_code == 200
	assert r.json() == {"path": str(target), "original": "", "modified": v2}


def test_file_diff_unchanged_file_and_stale_diff(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	target = tmp_path / "app.py"
	target.write_text("x\n")

	# the session never touched this file
	assert c.get(f"/sessions/{sid}/file/diff", params={"path": "app.py"}).status_code == 404

	# an error result does not count as a change
	row = _edit_result(str(target), "a\n", "b\n")
	_append_log_rows(tmp_path, sid, [{**row, "is_error": True}])
	assert c.get(f"/sessions/{sid}/file/diff", params={"path": "app.py"}).status_code == 404

	# a recorded diff that no longer matches the file is skipped, not an error:
	# the response shows only the diff that still applies (none here)
	_append_log_rows(tmp_path, sid, [_edit_result(str(target), "a\n", "b\n", "e2")])
	r = c.get(f"/sessions/{sid}/file/diff", params={"path": "app.py"})
	assert r.status_code == 200
	assert r.json() == {"path": str(target), "original": "x\n", "modified": "x\n"}


def test_file_diff_keeps_matching_hunks_when_the_file_moved_on(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	target = tmp_path / "app.py"
	v0 = "a\nb\nc\n"
	v1 = "a\nB\nc\n"
	target.write_text("a\nB\nc\nuser-added\n")  # edited again after the session
	_append_log_rows(tmp_path, sid, [_edit_result(str(target), v0, v1)])

	r = c.get(f"/sessions/{sid}/file/diff", params={"path": "app.py"})
	assert r.status_code == 200
	# the session's b->B change is still undone; the later user line stays
	assert r.json()["original"] == "a\nb\nc\nuser-added\n"
	assert r.json()["modified"] == "a\nB\nc\nuser-added\n"


def test_file_diff_is_fenced_by_allowed_roots(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	c = _client(tmp_path, allowed_roots=[str(allowed)])
	sid = c.post("/sessions", json={"cwd": str(allowed)}).json()["session_id"]

	r = c.get(f"/sessions/{sid}/file/diff", params={"path": "../secret.txt"})
	assert r.status_code == 403


def _git(cwd, *args):
	subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _git_repo(base):
	repo = base / "repo"
	repo.mkdir()
	_git(repo, "init", "-q")
	_git(repo, "config", "user.email", "test@example.com")
	_git(repo, "config", "user.name", "Test")
	return repo


def test_git_changes_lists_the_repositorys_uncommitted_files(tmp_path):
	c = _client(tmp_path)
	repo = _git_repo(tmp_path)
	(repo / "app.py").write_text("one\ntwo\n")
	(repo / "gone.py").write_text("x\n")
	_git(repo, "add", ".")
	_git(repo, "commit", "-q", "-m", "init")
	(repo / "app.py").write_text("one\nthree\nfour\n")
	(repo / "new.txt").write_text("a\nb\nc")  # no trailing newline: still 3 lines
	(repo / "gone.py").unlink()

	body = c.get("/fs/git/changes", params={"cwd": str(repo)}).json()
	root = body["root"]
	assert root == os.path.realpath(str(repo))
	rows = {os.path.relpath(f["path"], root): (f["added"], f["removed"]) for f in body["files"]}
	assert rows == {"app.py": (2, 1), "gone.py": (0, 1), "new.txt": (3, 0)}

	plain = tmp_path / "plain"
	plain.mkdir()
	assert c.get("/fs/git/changes", params={"cwd": str(plain)}).json() == {
		"root": None,
		"files": [],
	}


def test_git_changes_dedupes_paths_listed_twice_by_status(tmp_path):
	c = _client(tmp_path)
	repo = _git_repo(tmp_path)
	(repo / "f.txt").write_text("hi\n")
	_git(repo, "add", ".")
	_git(repo, "commit", "-q", "-m", "init")
	_git(repo, "rm", "-q", "--cached", "f.txt")  # status lists f.txt as `D ` and `??`

	files = c.get("/fs/git/changes", params={"cwd": str(repo)}).json()["files"]
	assert [os.path.basename(f["path"]) for f in files] == ["f.txt"]


def test_git_file_diff_serves_head_and_worktree_sides(tmp_path):
	c = _client(tmp_path)
	repo = _git_repo(tmp_path)
	(repo / "app.py").write_text("one\ntwo\n")
	(repo / "gone.py").write_text("x\n")
	_git(repo, "add", ".")
	_git(repo, "commit", "-q", "-m", "init")
	(repo / "app.py").write_text("one\nthree\n")
	(repo / "new.txt").write_text("fresh\n")
	(repo / "gone.py").unlink()

	changed = c.get("/fs/git/file/diff", params={"cwd": str(repo), "path": "app.py"}).json()
	assert changed == {
		"path": str(repo / "app.py"),
		"original": "one\ntwo\n",
		"modified": "one\nthree\n",
	}

	untracked = c.get("/fs/git/file/diff", params={"cwd": str(repo), "path": "new.txt"}).json()
	assert (untracked["original"], untracked["modified"]) == ("", "fresh\n")

	deleted = c.get("/fs/git/file/diff", params={"cwd": str(repo), "path": "gone.py"}).json()
	assert (deleted["original"], deleted["modified"]) == ("x\n", "")

	plain = tmp_path / "plain"
	plain.mkdir()
	(plain / "f.txt").write_text("x\n")
	assert c.get("/fs/git/file/diff", params={"cwd": str(plain), "path": "f.txt"}).status_code == 400


def test_git_endpoints_are_fenced_by_allowed_roots(tmp_path):
	repo = _git_repo(tmp_path)
	inside = repo / "inside"
	inside.mkdir()
	(inside / "a.txt").write_text("a\n")
	(repo / "outside.txt").write_text("b\n")
	c = _client(tmp_path, allowed_roots=[str(inside)])

	body = c.get("/fs/git/changes", params={"cwd": str(inside)}).json()
	assert [os.path.basename(f["path"]) for f in body["files"]] == ["a.txt"]

	assert c.get("/fs/git/changes", params={"cwd": str(repo)}).status_code == 403
	r = c.get("/fs/git/file/diff", params={"cwd": str(inside), "path": "../outside.txt"})
	assert r.status_code == 403


def test_allowed_roots_fences_cwd(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	c = _client(tmp_path, allowed_roots=[str(allowed)])
	assert c.post("/sessions", json={"cwd": str(allowed / "proj")}).status_code == 200
	assert c.post("/sessions", json={"cwd": str(tmp_path / "elsewhere")}).status_code == 400


def test_corrupt_log_reports_where_and_spares_other_sessions(tmp_path):
	c = _client(tmp_path)
	broken = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	healthy = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	good_line = json.dumps({"seq": 1, "type": "user_message", "content": "ok"}) + "\n"
	meta = next((tmp_path / "data" / "sessions").rglob(f"{broken}.meta.json"))
	log = meta.with_name(f"{broken}.jsonl")
	log.write_text(good_line + '{"seq":2,"type":"bad\n')
	restarted = _client(tmp_path)  # a fresh store caches nothing

	response = restarted.get(f"/sessions/{broken}")

	assert response.status_code == 500
	detail = response.json()["detail"]
	assert detail["error"] == "session_log_corrupt"
	assert detail["line"] == 2
	assert detail["offset"] == len(good_line.encode())
	assert str(tmp_path) not in json.dumps(detail)  # never leak the on-disk path
	# one damaged session must not take the rest of the daemon down
	assert restarted.get(f"/sessions/{healthy}").status_code == 200


def test_allowed_roots_expand_home_relative_paths(tmp_path, monkeypatch):
	home = tmp_path / "home"
	(home / "projects").mkdir(parents=True)
	monkeypatch.setenv("HOME", str(home))
	c = _client(tmp_path, allowed_roots=["~/projects"])

	# the root is configured home-relative; the client addresses it absolutely
	assert c.post("/sessions", json={"cwd": str(home / "projects" / "app")}).status_code == 200
	assert c.post("/sessions", json={"cwd": str(tmp_path / "elsewhere")}).status_code == 400
	# only roots are expanded: an addressed `~` stays literal and is fenced out
	assert c.post("/sessions", json={"cwd": "~/projects/app"}).status_code == 400


def test_allowed_roots_revalidate_stored_session_on_load(tmp_path):
	outside = tmp_path / "outside"
	allowed = tmp_path / "allowed"
	outside.mkdir()
	allowed.mkdir()
	data_dir = tmp_path / "data"
	first_store = SessionStore(
		str(data_dir),
		allowed_roots=[],
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	sid = first_store.create(SessionConfig(cwd=str(outside))).id

	restricted_store = SessionStore(
		str(data_dir),
		allowed_roots=[str(allowed)],
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	with pytest.raises(ValueError, match="not under an allowed root"):
		restricted_store.get(sid)


def test_rejects_path_traversal_session_id(tmp_path):
	c = _client(tmp_path)
	# a session_id that would escape the sessions dir must be rejected
	r = c.post("/sessions", json={"session_id": "../../etc/x", "cwd": str(tmp_path)})
	assert r.status_code == 400


def test_stream_replays_completed_run(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})
	with c.stream("GET", f"/sessions/{sid}/stream") as r:
		rows = [json.loads(ln[5:]) for ln in r.iter_lines() if ln.startswith("data:")]
	assert rows[-1]["type"] == "run_ended"


def test_paused_run_requires_exact_current_approval_batch(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("SECRET")
	mock = MockModel(
		replies=[
			AssistantMessage(
				content=[
					ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
					ToolCall(id="c2", name="read_file", arguments={"path": "a.txt"}),
				]
			),
			AssistantMessage(content="done"),
		]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={
			"cwd": str(tmp_path),
			"confirm_tools": ["read_file"],
		},
	).json()["session_id"]

	paused = c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read"},
	).json()
	approval_seq = paused["approval_seq"]
	assert paused["reason"] == "paused"
	assert c.get(f"/sessions/{sid}").json()["state"] == "paused"
	assert c.post(f"/sessions/{sid}/run", json={"message": "overlap"}).status_code == 409

	for payload in (
		{"approval_seq": approval_seq, "answers": {"c1": "Approve"}},
		{
			"approval_seq": approval_seq,
			"answers": {"c1": "Approve", "c2": "Approve", "extra": "Deny"},
		},
		{
			"approval_seq": approval_seq - 1,
			"answers": {"c1": "Approve", "c2": "Approve"},
		},
	):
		response = c.post(f"/sessions/{sid}/resume", json=payload)
		assert response.status_code == 409

	resumed = c.post(
		f"/sessions/{sid}/resume",
		params={"wait": "true"},
		json={
			"approval_seq": approval_seq,
			"answers": {"c1": "Approve", "c2": "Approve"},
		},
	)
	assert resumed.status_code == 200
	assert resumed.json()["reason"] == "done"
	assert c.get(f"/sessions/{sid}").json()["state"] == "idle"
	assert (
		c.post(
			f"/sessions/{sid}/resume",
			json={
				"approval_seq": approval_seq,
				"answers": {"c1": "Approve", "c2": "Approve"},
			},
		).status_code
		== 409
	)


def test_paused_state_and_approval_survive_store_reload(tmp_path, monkeypatch):
	mock = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
	data_dir = tmp_path / "data"
	store = SessionStore(
		str(data_dir),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	c = TestClient(create_app(store))
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	paused = c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read"},
	).json()

	reloaded = SessionStore(
		str(data_dir),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	).get(sid)
	assert reloaded.state == "paused"
	assert reloaded.log.read_since(paused["approval_seq"] - 1)[0]["type"] == "approval_required"


class _BlockingModel(Model):
	name = "blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.call_count = 0

	async def run(self, request: ModelRequest):
		self.call_count += 1
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(content="done")
		yield Usage()


class _ResumeBlockingModel(Model):
	name = "resume-blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.call_count = 0

	async def run(self, request: ModelRequest):
		self.call_count += 1
		if self.call_count == 1:
			yield AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])
			yield Usage()
			return
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(content="done")
		yield Usage()


class _AbortBlockingModel(Model):
	name = "abort-blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.cancelled = asyncio.Event()
		self.release_cleanup = asyncio.Event()
		self.request: ModelRequest | None = None

	async def run(self, request: ModelRequest):
		self.request = request
		self.started.set()
		try:
			await asyncio.Event().wait()
		finally:
			self.cancelled.set()
			await self.release_cleanup.wait()
		if False:
			yield


async def test_waiting_run_is_registered_and_concurrent_run_steers(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
		sid = (
			await c.post(
				"/sessions",
				json={"cwd": str(tmp_path)},
			)
		).json()["session_id"]
		first = asyncio.create_task(
			c.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "first"},
			)
		)
		await model.started.wait()

		state = (await c.get(f"/sessions/{sid}")).json()
		assert state["state"] == "running"
		assert state["running"] is True
		second = await c.post(f"/sessions/{sid}/run", json={"message": "second"})
		assert second.json() == {"status": "steered"}

		model.release.set()
		assert (await first).json()["reason"] == "done"
		assert (await c.get(f"/sessions/{sid}")).json()["state"] == "idle"
		assert model.call_count == 2
		entries = (await c.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["content"] for row in entries if row["type"] == "user_message"] == [
			"first",
			"second",
		]


async def test_abort_interrupts_stream_clears_steering_and_returns_session_to_idle(tmp_path, monkeypatch):
	model = _AbortBlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (
			await client.post(
				"/sessions",
				json={"cwd": str(tmp_path)},
			)
		).json()["session_id"]
		run_request = asyncio.create_task(
			client.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "first"},
			)
		)
		await model.started.wait()

		steered = await client.post(f"/sessions/{sid}/run", json={"message": "discard me"})
		assert steered.json() == {"status": "steered"}
		assert (await client.post(f"/sessions/{sid}/abort")).json() == {"status": "aborting"}
		await model.cancelled.wait()

		rejected = await client.post(f"/sessions/{sid}/run", json={"message": "too late"})
		assert rejected.status_code == 409
		assert rejected.json()["detail"] == "run is aborting"
		assert model.request is not None
		cancellation = model.request.cancellation
		assert cancellation is store.get(sid).abort_signal
		assert cancellation is not None and cancellation.is_set()

		model.release_cleanup.set()
		assert (await run_request).json()["reason"] == "aborted"
		state = (await client.get(f"/sessions/{sid}")).json()
		assert state["state"] == "idle"
		assert state["running"] is False
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["content"] for row in entries if row["type"] == "user_message"] == ["first"]
		assert [row["stop_reason"] for row in entries if row["type"] == "assistant_message"] == ["aborted"]
		assert [row["reason"] for row in entries if row["type"] == "run_ended"] == ["aborted"]


async def test_http_abort_kills_active_bash_process_tree_and_repairs_transcript(tmp_path, monkeypatch):
	pid_file = tmp_path / "child.pid"
	command = f'sleep 30 & child=$!; printf \'%s\\n\' "$child" > {shlex.quote(str(pid_file))}; wait "$child"'
	model = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="bash-1", name="bash", arguments={"command": command})])
		]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (
			await client.post(
				"/sessions",
				json={"cwd": str(tmp_path), "tools": ["bash"], "auto_approve": True},
			)
		).json()["session_id"]
		run_request = asyncio.create_task(
			client.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "run the command"},
			)
		)
		for _ in range(100):
			if pid_file.exists() and pid_file.read_text().strip():
				break
			await asyncio.sleep(0.01)
		assert pid_file.exists()
		child_pid = int(pid_file.read_text().strip())

		assert (await client.post(f"/sessions/{sid}/abort")).json() == {"status": "aborting"}
		assert (await asyncio.wait_for(run_request, timeout=2)).json()["reason"] == "aborted"

		for _ in range(100):
			try:
				os.kill(child_pid, 0)
			except ProcessLookupError:
				break
			await asyncio.sleep(0.01)
		else:
			pytest.fail("Bash child process survived HTTP cancellation")

		state = (await client.get(f"/sessions/{sid}")).json()
		assert state["state"] == "idle"
		assert state["running"] is False
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["stop_reason"] for row in entries if row["type"] == "assistant_message"][-1] == "aborted"
		assert [row["tool_call_id"] for row in entries if row["type"] == "tool_result"] == ["bash-1"]
		assert [row["reason"] for row in entries if row["type"] == "run_ended"] == ["aborted"]


async def test_concurrent_resume_is_rejected_before_duplicate_tool_execution(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("SECRET")
	model = _ResumeBlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (
			await client.post(
				"/sessions",
				json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
			)
		).json()["session_id"]
		paused = (
			await client.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "read"},
			)
		).json()
		payload = {
			"approval_seq": paused["approval_seq"],
			"answers": {"c1": "Approve"},
		}

		first = asyncio.create_task(
			client.post(
				f"/sessions/{sid}/resume",
				params={"wait": "true"},
				json=payload,
			)
		)
		await model.started.wait()

		overlap = await client.post(f"/sessions/{sid}/resume", json=payload)
		assert overlap.status_code == 409
		assert overlap.json()["detail"] == "run is not paused"

		model.release.set()
		assert (await first).json()["reason"] == "done"
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert len([row for row in entries if row["type"] == "tool_result"]) == 1


async def test_stream_reconnect_with_since_continues_a_live_run(tmp_path, monkeypatch):
	# a live SSE stream needs a real server: httpx's ASGITransport buffers whole bodies
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)

	sock = socket.socket()
	sock.bind(("127.0.0.1", 0))
	port = sock.getsockname()[1]
	server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
	serve_task = asyncio.create_task(server.serve(sockets=[sock]))
	try:
		while not server.started:
			await asyncio.sleep(0.01)
		async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
			sid = (await client.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
			assert (await client.post(f"/sessions/{sid}/run", json={"message": "hi"})).json() == {
				"status": "started"
			}
			await asyncio.wait_for(model.started.wait(), timeout=2)

			seen = []
			async with client.stream("GET", f"/sessions/{sid}/stream") as response:
				async for line in response.aiter_lines():
					if not line.startswith("data:"):
						continue
					seen.append(json.loads(line[5:]))
					if len(seen) == 2:
						break  # drop the connection mid-run
			assert [row["type"] for row in seen] == ["run_started", "user_message"]

			model.release.set()
			for _ in range(100):
				if (await client.get(f"/sessions/{sid}")).json()["state"] == "idle":
					break
				await asyncio.sleep(0.01)
			else:
				pytest.fail("run never finished after release")

			# reconnect from the last seen cursor: the rest of the run, no duplicates
			cursor = seen[-1]["seq"]
			async with client.stream("GET", f"/sessions/{sid}/stream", params={"since": cursor}) as response:
				continued = [
					json.loads(line[5:]) async for line in response.aiter_lines() if line.startswith("data:")
				]
			assert continued[0]["seq"] == cursor + 1
			assert all(row["seq"] > cursor for row in continued)
			assert any(row["type"] == "assistant_message" for row in continued)
			assert continued[-1]["type"] == "run_ended"
	finally:
		server.should_exit = True
		await asyncio.wait_for(serve_task, timeout=5)


def test_cancel_pending_closes_a_paused_run(tmp_path, monkeypatch):
	mock = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})]),
			AssistantMessage(content="done"),
		]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	paused = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "read"}).json()
	assert paused["reason"] == "paused"

	assert c.post(f"/sessions/{sid}/cancel_pending").json() == {"status": "cancelled"}

	assert c.get(f"/sessions/{sid}").json()["state"] == "idle"
	results = [
		row for row in c.get(f"/sessions/{sid}/entries").json()["entries"] if row["type"] == "tool_result"
	]
	assert [row["tool_call_id"] for row in results] == ["c1"]
	assert all(row["is_error"] for row in results)
	# the batch is settled; a late resume has nothing left to act on
	late = c.post(
		f"/sessions/{sid}/resume",
		json={"approval_seq": paused["approval_seq"], "answers": {"c1": "Approve"}},
	)
	assert late.status_code == 409


def test_cancel_pending_without_a_pause_is_a_noop(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	assert c.post(f"/sessions/{sid}/cancel_pending").json() == {"status": "idle"}
	assert c.get(f"/sessions/{sid}/entries").json()["entries"] == []


async def test_cancel_pending_while_running_is_rejected(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (await client.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
		first = asyncio.create_task(
			client.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "go"})
		)
		await model.started.wait()

		assert (await client.post(f"/sessions/{sid}/cancel_pending")).status_code == 409

		model.release.set()
		assert (await first).json()["reason"] == "done"


def test_rewind_branches_the_conversation_over_http(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "first"})

	assert c.post(f"/sessions/{sid}/rewind", json={"target_seq": 1}).json() == {"status": "rewound"}

	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "second"})
	active = c.get(f"/sessions/{sid}/entries").json()["entries"]  # the conversation view is the default
	assert [r["content"] for r in active if r["type"] == "user_message"] == ["second"]
	everything = c.get(f"/sessions/{sid}/entries", params={"path": "all"}).json()["entries"]
	assert [r["content"] for r in everything if r["type"] == "user_message"] == ["first", "second"]
	assert "rewind" in [r["type"] for r in everything]  # the old branch is still there

	assert c.post(f"/sessions/{sid}/rewind", json={"target_seq": 999}).status_code == 409


async def test_rewind_while_running_is_rejected_over_http(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (await client.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
		first = asyncio.create_task(
			client.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "go"})
		)
		await model.started.wait()

		assert (await client.post(f"/sessions/{sid}/rewind", json={"target_seq": 1})).status_code == 409

		model.release.set()
		assert (await first).json()["reason"] == "done"


def test_active_entries_reject_a_cursor(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})

	# a rewind can retract rows before a cursor, so the snapshot view refuses one
	assert c.get(f"/sessions/{sid}/entries", params={"since": 2}).status_code == 422
	assert c.get(f"/sessions/{sid}/entries", params={"since": 2, "path": "all"}).status_code == 200
	assert c.get(f"/sessions/{sid}/entries").status_code == 200


def test_compact_verb_summarizes_and_conflicts(tmp_path, monkeypatch):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]

	assert c.post(f"/sessions/{sid}/compact").status_code == 409  # nothing to compact yet

	mock = MockModel(
		replies=[
			AssistantMessage(content="answer one"),
			AssistantMessage(content="## Goal\nserver summary"),  # the summarizer's turn
		]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda name, **kw: mock)
	r = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hello"}).json()
	assert r["reason"] == "done"

	r = c.post(f"/sessions/{sid}/compact", params={"wait": "true"}, json={"instructions": "goals"}).json()
	assert r["reason"] == "done"

	entries = c.get(f"/sessions/{sid}/entries").json()["entries"]
	rows = [e for e in entries if e["type"] == "compaction"]
	assert len(rows) == 1
	assert rows[0]["reason"] == "manual"
	assert rows[0]["summary"] == "## Goal\nserver summary"
	# the replaced rows are still served — the fold is a read-time view, not a delete
	assert [e["type"] for e in entries][:2] == ["run_started", "user_message"]

	assert c.post(f"/sessions/{sid}/compact", json={"instructions": 7}).status_code == 422


def test_models_endpoint_discovers_configured_providers_only(tmp_path, monkeypatch):
	from flow.model import discovery
	from flow.model.catalog import PROVIDERS

	for provider in PROVIDERS:
		for name in provider.api_key_envs:
			monkeypatch.delenv(name, raising=False)

	async def fake_http_models(url, auth, client, *, provider_id=None):
		assert provider_id == "openai"
		return ["gpt-4o"]

	monkeypatch.setattr(discovery, "_http_models", fake_http_models)
	c = _client(tmp_path)
	assert c.get("/models").json() == {"models": [], "errors": []}

	monkeypatch.setenv("OPENAI_API_KEY", "k")
	assert c.get("/models").json() == {
		"models": [{"name": "openai/gpt-4o", "provider": "openai", "supports_images": True}],
		"errors": [],
	}


def test_list_sessions_includes_cold_on_disk_sessions(tmp_path):
	c = _client(tmp_path)
	used = c.post(
		"/sessions",
		json={"model": "mock", "cwd": str(tmp_path / "a")},
	).json()["session_id"]
	fresh = c.post(
		"/sessions",
		json={"model": "mock/v2", "cwd": str(tmp_path / "b")},
	).json()["session_id"]
	c.post(f"/sessions/{used}/run", params={"wait": "true"}, json={"message": "hi"})
	latest_seq = c.get(f"/sessions/{used}").json()["latest_seq"]

	# a fresh store over the same dir caches nothing: the cold path reads meta + log tail
	for client in (c, _client(tmp_path)):
		rows = {row["session_id"]: row for row in client.get("/sessions").json()["sessions"]}
		assert rows[used] == {
			"session_id": used,
			"state": "idle",
			"model": "mock",
			"latest_seq": latest_seq,
			"cwd": str(tmp_path / "a"),
			"title": "hi",
		}
		# `fresh` has no durable entries — nothing to resume, so the listing omits it
		assert fresh not in rows


def test_list_sessions_reports_a_cold_paused_session(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("x")
	mock = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})]),
			AssistantMessage(content="done"),
		]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	paused = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "read"}).json()
	assert paused["reason"] == "paused"

	cold = _client(tmp_path)
	(row,) = cold.get("/sessions").json()["sessions"]
	assert row["state"] == "paused"

	# resolving the batch moves the tail past run_ended(paused): the cold state follows
	c.post(
		f"/sessions/{sid}/resume",
		params={"wait": "true"},
		json={"approval_seq": paused["approval_seq"], "answers": {"c1": "Approve"}},
	)
	(row,) = _client(tmp_path).get("/sessions").json()["sessions"]
	assert row["state"] == "idle"


async def test_stream_follow_stays_open_between_runs_with_keepalives(tmp_path, monkeypatch):
	monkeypatch.setattr("flow.server.app.KEEPALIVE_SECONDS", 0.05)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)

	sock = socket.socket()
	sock.bind(("127.0.0.1", 0))
	port = sock.getsockname()[1]
	server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=1))
	serve_task = asyncio.create_task(server.serve(sockets=[sock]))
	try:
		while not server.started:
			await asyncio.sleep(0.01)
		async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
			sid = (await client.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)})).json()[
				"session_id"
			]
			await client.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "first"})

			rows, saw_keepalive, second = [], False, None
			async with client.stream(
				"GET",
				f"/sessions/{sid}/stream",
				params={"follow": "true"},
				timeout=httpx.Timeout(5, read=5),
			) as response:
				async with asyncio.timeout(10):
					async for line in response.aiter_lines():
						if line.startswith(":"):
							saw_keepalive = True
							if second is None:  # the boundary passed without a close; run again
								second = asyncio.create_task(
									client.post(f"/sessions/{sid}/run", json={"message": "second"})
								)
						elif line.startswith("data:"):
							rows.append(json.loads(line[5:]))
							if sum(r["type"] == "run_ended" for r in rows) == 2:
								break
			if second is not None:
				await second

			assert saw_keepalive
			assert [r["content"] for r in rows if r["type"] == "user_message"] == ["first", "second"]
			seqs = [r["seq"] for r in rows if "seq" in r]
			assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
	finally:
		server.should_exit = True
		await asyncio.wait_for(serve_task, timeout=5)
