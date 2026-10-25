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

from flow_harness.events import AssistantMessage, ToolCall, Usage
from flow_harness.model import Model, ModelRequest
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.mock import MockModel
from flow_harness.server import create_app
from flow_harness.session.store import SessionStore


def _client(tmp_path, **store_kw):
	return TestClient(create_app(_store(tmp_path, **store_kw)))


def _store(tmp_path, **store_kw):
	store_kw.setdefault(
		"credential_store",
		CredentialStore(str(tmp_path / "credentials.json")),
	)
	return SessionStore(str(tmp_path / "data"), **store_kw)


def test_create_prompt_wait_and_entries(tmp_path, monkeypatch):
	class CacheUsageModel(Model):
		async def run(self, request):
			yield AssistantMessage(content="cached")
			yield Usage(
				input_tokens=100,
				output_tokens=5,
				cache_read_tokens=80,
				cache_write_tokens=10,
			)

	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: CacheUsageModel())
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	# blocking prompt returns the terminal summary (Flow-like synchronous response)
	res = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hello"}).json()
	assert (res["reason"], res["output"]) == ("done", "cached")
	assert res["usage"] == {
		"input_tokens": 100,
		"output_tokens": 5,
		"cache_read_tokens": 80,
		"cache_write_tokens": 10,
	}
	# the durable log replays the whole turn
	types = [e["type"] for e in c.get(f"/sessions/{sid}/entries").json()["entries"]]
	assert types[0] == "run_started"
	assert "user_message" in types and "assistant_message" in types
	assert types[-1] == "run_ended"


def test_model_selection_is_durable_and_rewinds_with_its_branch(tmp_path, monkeypatch):
	resolved, efforts = [], []

	class Recording(MockModel):
		async def run(self, request):
			efforts.append(request.params["reasoning_effort"])
			async for event in super().run(request):
				yield event

	def spy(name, **kwargs):
		resolved.append(name)
		return Recording()

	monkeypatch.setattr("flow_harness.agent.loop.get_model", spy)
	monkeypatch.setattr(
		"flow_harness.server.routes.sessions.context_window_for",
		lambda model: 1_000_000 if model == "mock/v2" else None,
	)
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path), "reasoning_effort": "low"}).json()[
		"session_id"
	]
	assert c.get(f"/sessions/{sid}").json()["reasoning_effort"] == "low"
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})
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

	r = c.post(
		f"/sessions/{sid}/model",
		json={"model": "mock/v2", "credential_id": "mock-profile", "reasoning_effort": "high"},
	)
	assert r.json() == {
		"model": "mock/v2",
		"credential_id": "mock-profile",
		"reasoning_effort": "high",
		"context_window": 1_000_000,
		"supports_images": False,
	}
	assert (
		c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "v2"}).json()["reason"]
		== "done"
	)
	info = c.get(f"/sessions/{sid}").json()
	assert (info["model"], info["credential_id"]) == ("mock/v2", "mock-profile")
	assert info["config"]["model"] == "mock"  # the creation config is fixed
	types = [e["type"] for e in c.get(f"/sessions/{sid}/entries").json()["entries"]]
	assert types.count("model_changed") == 2

	# rewinding to before the changes restores the creation-config selection
	c.post(f"/sessions/{sid}/rewind", json={"target_seq": branch_point})
	assert c.get(f"/sessions/{sid}").json()["reasoning_effort"] == "low"
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "back"})
	assert list(zip(resolved, efforts, strict=True)) == [
		("mock", "low"),
		("mock", "high"),
		("mock/v2", "high"),
		("mock", "low"),
	]


def test_create_and_run_refuse_unsafe_client_inputs(tmp_path):
	# provider secrets and endpoints need a policy opt-in (see test_inline_credentials)
	c = _client(tmp_path)
	for field, value in (("api_key", "secret"), ("api_base", "https://attacker.test")):
		response = c.post(
			"/sessions",
			json={"model": "mock", "cwd": str(tmp_path), field: value},
		)
		assert response.status_code == 400
		assert "server policy" in response.json()["detail"]
	# a session_id that would escape the sessions dir
	assert c.post("/sessions", json={"session_id": "../../etc/x", "cwd": str(tmp_path)}).status_code == 400

	# model changes go through POST /sessions/{sid}/model
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	for field, value in (("api_key", "secret"), ("api_base", "https://attacker.test"), ("model", "mock/v2")):
		response = c.post(
			f"/sessions/{sid}/run",
			json={"message": "hello", field: value},
		)
		assert response.status_code == 422, field


def test_idle_session_verbs_change_nothing(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	assert c.post(f"/sessions/{sid}/abort").json() == {"status": "idle"}
	assert c.post(f"/sessions/{sid}/cancel_pending").json() == {"status": "idle"}
	res = c.post(
		f"/sessions/{sid}/resume",
		params={"wait": "true"},
		json={"approval_seq": 1, "answers": {}},
	)
	assert res.status_code == 409
	assert c.get(f"/sessions/{sid}/entries").json()["entries"] == []


def test_read_and_write_workspace_file(tmp_path):
	c = _client(tmp_path)

	# no session needed; parent directories are created, and the write
	# round-trips through the read endpoint
	r = c.put("/fs/file", json={"cwd": str(tmp_path), "path": "new/notes.txt", "content": "hello\nworld\n"})
	assert r.status_code == 200
	assert (tmp_path / "new" / "notes.txt").read_text() == "hello\nworld\n"
	r = c.get("/fs/file", params={"cwd": str(tmp_path), "path": "new/notes.txt"})
	assert r.status_code == 200
	assert r.json() == {"path": str(tmp_path / "new" / "notes.txt"), "content": "hello\nworld\n"}

	assert c.get("/fs/file", params={"cwd": str(tmp_path), "path": "missing.txt"}).status_code == 404
	(tmp_path / "blob.bin").write_bytes(b"\xff\xfe\x00garbage\x80")
	assert c.get("/fs/file", params={"cwd": str(tmp_path), "path": "blob.bin"}).status_code == 415
	# writing over a directory is a client error, not a 500
	assert c.put("/fs/file", json={"cwd": str(tmp_path), "path": "new", "content": "x"}).status_code == 400


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
	# folders are found too, by their own name, not what they hold; earlier
	# slash-separated terms match in order along the path, so a partial path skips levels
	by_dir = c.get("/fs/files/search", params={"cwd": str(work), "query": "src/"}).json()
	assert by_dir["matches"] == ["src/"]
	deep = c.get("/fs/files/search", params={"cwd": str(work), "query": "src dee"}).json()
	assert deep["matches"] == ["src/deep/"]
	partial = c.get("/fs/files/search", params={"cwd": str(work), "query": "src/app"}).json()
	assert partial["matches"] == ["src/deep/app_helpers.py"]

	assert c.get("/fs/files/search", params={"cwd": str(work), "query": "  "}).json()["matches"] == []
	gone = c.get("/fs/files/search", params={"cwd": str(work / "gone"), "query": "app"})
	assert gone.status_code == 404


def test_allowed_roots_fence_every_path(tmp_path, monkeypatch):
	repo = _git_repo(tmp_path)
	allowed = repo / "allowed"
	allowed.mkdir()
	(allowed / "ok.txt").write_text("fine")
	(repo / "outside.txt").write_text("nope")
	stored = _client(tmp_path).post("/sessions", json={"cwd": str(repo)}).json()["session_id"]
	c = _client(tmp_path, allowed_roots=[str(allowed)])

	r = c.post("/sessions", json={"cwd": str(allowed / "proj")})
	assert r.status_code == 200
	sid = r.json()["session_id"]
	assert c.post("/sessions", json={"cwd": str(tmp_path / "elsewhere")}).status_code == 400
	# a stored session does not outlive a tightened fence
	r = c.get(f"/sessions/{stored}")
	assert r.status_code == 400
	assert "not under an allowed root" in r.json()["detail"]

	assert c.get("/fs/file", params={"cwd": str(allowed), "path": "ok.txt"}).status_code == 200
	assert c.get("/fs/files", params={"cwd": str(allowed)}).status_code == 200
	assert c.put("/fs/file", json={"cwd": str(allowed), "path": "ok.txt", "content": "x"}).status_code == 200
	# the repository's changes outside the fence are dropped
	body = c.get("/fs/git/changes", params={"cwd": str(allowed)}).json()
	assert [os.path.basename(f["path"]) for f in body["files"]] == ["ok.txt"]
	for url, params in (
		("/fs/file", {"cwd": str(allowed), "path": "../outside.txt"}),
		("/fs/file", {"cwd": str(allowed), "path": str(repo / "outside.txt")}),
		("/fs/files", {"cwd": str(allowed), "path": ".."}),
		("/fs/files", {"cwd": str(repo)}),
		("/fs/files/search", {"cwd": str(repo), "query": "x"}),
		("/fs/git/changes", {"cwd": str(repo)}),
		("/fs/git/branch", {"cwd": str(repo)}),
		("/fs/git/file/diff", {"cwd": str(allowed), "path": "../outside.txt"}),
		(f"/sessions/{sid}/file/diff", {"path": "../../outside.txt"}),
	):
		assert c.get(url, params=params).status_code == 403, (url, params)
	assert (
		c.put("/fs/file", json={"cwd": str(allowed), "path": "../escape.txt", "content": "x"}).status_code
		== 403
	)
	assert not (repo / "escape.txt").exists()

	# a root may be home-relative; an addressed `~` stays literal and is fenced out
	monkeypatch.setenv("HOME", str(tmp_path))
	home = _client(tmp_path, allowed_roots=["~/repo/allowed"])
	assert home.post("/sessions", json={"cwd": str(allowed / "app")}).status_code == 200
	assert home.post("/sessions", json={"cwd": str(tmp_path / "elsewhere")}).status_code == 400
	assert home.post("/sessions", json={"cwd": "~/repo/allowed/app"}).status_code == 400


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


def test_file_diff_rebuilds_the_original_from_the_sessions_changes(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	v0, v1, v2 = "a\nb\nc\n", "a\nB\nc\n", "a\nB\nc\nd\n"

	def edit(name, old, new, call_id="edit-1"):
		return _edit_result(str(tmp_path / name), old, new, call_id)

	write = {
		"type": "tool_result",
		"tool_call_id": "w1",
		"name": "write",
		"content": f"[wrote {tmp_path / 'new.py'} (1 lines)]",
		"details": {"path": str(tmp_path / "new.py"), "chars": len(v1), "lines": 1},
	}
	cases = [
		# file, its text now, the session's rows, the original (None: 404)
		("app.py", v2, [edit("app.py", v0, v1, "e1"), edit("app.py", v1, v2, "e2")], v0),
		# a write counts as created
		("new.py", v2, [write, edit("new.py", v1, v2)], ""),
		# the session never touched this file, or its edit failed
		("untouched.py", "x\n", [], None),
		("failed.py", "x\n", [{**edit("failed.py", "a\n", "b\n"), "is_error": True}], None),
		# a recorded diff that no longer matches the file is skipped, not an error
		("stale.py", "x\n", [edit("stale.py", "a\n", "b\n")], "x\n"),
		# edited again after the session: the b->B change is still undone, the user line stays
		("moved_on.py", "a\nB\nc\nuser-added\n", [edit("moved_on.py", v0, v1)], "a\nb\nc\nuser-added\n"),
	]
	for name, text, rows, _ in cases:
		(tmp_path / name).write_text(text)
		_append_log_rows(tmp_path, sid, rows)

	for name, text, _, original in cases:
		r = c.get(f"/sessions/{sid}/file/diff", params={"path": name})
		if original is None:
			assert r.status_code == 404, name
		else:
			assert r.json() == {"path": str(tmp_path / name), "original": original, "modified": text}, name


def _git(cwd, *args):
	subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _git_repo(base):
	repo = base / "repo"
	repo.mkdir()
	_git(repo, "init", "-q")
	_git(repo, "config", "user.email", "test@example.com")
	_git(repo, "config", "user.name", "Test")
	return repo


def test_git_changes_and_file_diff_serve_uncommitted_files(tmp_path):
	c = _client(tmp_path)
	repo = _git_repo(tmp_path)
	(repo / "app.py").write_text("one\ntwo\n")
	(repo / "gone.py").write_text("x\n")
	(repo / "f.txt").write_text("hi\n")
	_git(repo, "add", ".")
	_git(repo, "commit", "-q", "-m", "init")
	(repo / "app.py").write_text("one\nthree\nfour\n")
	(repo / "new.txt").write_text("a\nb\nc")  # no trailing newline: still 3 lines
	(repo / "gone.py").unlink()
	_git(repo, "rm", "-q", "--cached", "f.txt")  # status lists f.txt as `D ` and `??`
	_git(repo, "checkout", "-q", "-b", "work")

	body = c.get("/fs/git/changes", params={"cwd": str(repo)}).json()
	root = body["root"]
	assert root == os.path.realpath(str(repo))
	rows = [(os.path.relpath(f["path"], root), f["added"], f["removed"]) for f in body["files"]]
	assert rows == [("app.py", 2, 1), ("f.txt", 0, 1), ("gone.py", 0, 1), ("new.txt", 3, 0)]

	def diff(path):
		return c.get("/fs/git/file/diff", params={"cwd": str(repo), "path": path}).json()

	assert diff("app.py") == {
		"path": str(repo / "app.py"),
		"original": "one\ntwo\n",
		"modified": "one\nthree\nfour\n",
	}
	untracked, deleted = diff("new.txt"), diff("gone.py")
	assert (untracked["original"], untracked["modified"]) == ("", "a\nb\nc")
	assert (deleted["original"], deleted["modified"]) == ("x\n", "")

	# the branch checked out; a linked worktree says so, on its own branch, the main checkout does not
	def head(cwd):
		return c.get("/fs/git/branch", params={"cwd": str(cwd)}).json()

	assert head(repo) == {"branch": "work", "worktree": False}
	_git(repo, "worktree", "add", "-q", "-b", "side", str(tmp_path / "side"))
	assert head(tmp_path / "side") == {"branch": "side", "worktree": True}
	# a detached HEAD has no branch
	_git(repo, "checkout", "-q", "--detach")
	assert head(repo)["branch"] is None

	plain = tmp_path / "plain"
	plain.mkdir()
	(plain / "f.txt").write_text("x\n")
	assert c.get("/fs/git/changes", params={"cwd": str(plain)}).json() == {
		"root": None,
		"files": [],
	}
	assert head(plain) == {"branch": None, "worktree": False}
	assert c.get("/fs/git/file/diff", params={"cwd": str(plain), "path": "f.txt"}).status_code == 400


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
			yield AssistantMessage(
				content=[
					ToolCall(id="c1", name="read", arguments={"path": "a.txt"}),
					ToolCall(id="c2", name="read", arguments={"path": "a.txt"}),
				]
			)
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


async def test_resume_takes_the_exact_current_approval_batch_once(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("SECRET")
	model = _ResumeBlockingModel()
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	transport = httpx.ASGITransport(app=create_app(_store(tmp_path)))
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (
			await client.post(
				"/sessions",
				json={"cwd": str(tmp_path), "confirm_tools": ["read"]},
			)
		).json()["session_id"]
		paused = (
			await client.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "read"},
			)
		).json()
		approval_seq = paused["approval_seq"]
		assert paused["reason"] == "paused"
		assert (await client.get(f"/sessions/{sid}")).json()["state"] == "paused"
		assert (await client.post(f"/sessions/{sid}/run", json={"message": "overlap"})).status_code == 409

		answers = {"c1": "Approve", "c2": "Approve"}
		for payload in (
			{"approval_seq": approval_seq, "answers": {"c1": "Approve"}},
			{"approval_seq": approval_seq, "answers": {**answers, "extra": "Deny"}},
			{"approval_seq": approval_seq - 1, "answers": answers},
		):
			assert (await client.post(f"/sessions/{sid}/resume", json=payload)).status_code == 409, payload

		# a concurrent resume is rejected before the tools run twice
		payload = {"approval_seq": approval_seq, "answers": answers}
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
		assert (await client.get(f"/sessions/{sid}")).json()["state"] == "idle"
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["tool_call_id"] for row in entries if row["type"] == "tool_result"] == ["c1", "c2"]
		assert (await client.post(f"/sessions/{sid}/resume", json=payload)).status_code == 409


def test_a_paused_run_survives_a_restart_until_cancelled(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("x")
	mock = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})])]
	)
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read"]},
	).json()["session_id"]
	paused = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "read"}).json()
	assert paused["reason"] == "paused"

	# fresh stores cache nothing: the state and the approval come from disk
	reloaded = _store(tmp_path).get(sid)
	assert reloaded.state == "paused"
	assert reloaded.log.read_since(paused["approval_seq"] - 1)[0]["type"] == "approval_required"
	(row,) = _client(tmp_path).get("/sessions").json()["sessions"]
	assert row["state"] == "paused"

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
	# the tail moved past run_ended(paused): the cold state follows
	(row,) = _client(tmp_path).get("/sessions").json()["sessions"]
	assert row["state"] == "idle"


async def test_a_running_session_steers_runs_and_refuses_state_changes(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	store = _store(tmp_path)
	transport = httpx.ASGITransport(app=create_app(store))
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
		sid = (await c.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
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
		assert (await c.post(f"/sessions/{sid}/cancel_pending")).status_code == 409
		assert (await c.post(f"/sessions/{sid}/rewind", json={"target_seq": 1})).status_code == 409
		assert (await c.delete(f"/sessions/{sid}")).status_code == 409
		# the loop shares the config object, so the next tool gate skips approval
		assert (await c.patch(f"/sessions/{sid}/config", json={"auto_approve": True})).status_code == 200
		assert store.get(sid).config.auto_approve is True

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
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	store = _store(tmp_path)
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
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	store = _store(tmp_path)
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


async def test_stream_catches_up_from_a_cursor_and_follows_across_runs(tmp_path, monkeypatch):
	# a live SSE stream needs a real server: httpx's ASGITransport buffers whole bodies
	monkeypatch.setattr("flow_harness.server.utils.sse.KEEPALIVE_SECONDS", 0.05)
	model = _BlockingModel()
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	app = create_app(_store(tmp_path))

	sock = socket.socket()
	sock.bind(("127.0.0.1", 0))
	port = sock.getsockname()[1]
	server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=1))
	serve_task = asyncio.create_task(server.serve(sockets=[sock]))
	try:
		while not server.started:
			await asyncio.sleep(0.01)
		async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
			sid = (await client.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
			assert (await client.post(f"/sessions/{sid}/run", json={"message": "first"})).json() == {
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

			# follow stays open past the run boundary, with keepalives, into the next run
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


async def test_a_posted_tool_result_reaches_the_client_tool_waiting_on_it(tmp_path, monkeypatch):
	tokens: asyncio.Queue[str] = asyncio.Queue()

	async def post(config, url, payload):
		tokens.put_nowait(payload["result_token"])
		return {"pending": True, "timeout": 5}

	monkeypatch.setattr("flow_harness.agent.client_tools._post", post)
	model = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="report", arguments={})]),
			AssistantMessage(content="done"),
		]
	)
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	transport = httpx.ASGITransport(app=create_app(_store(tmp_path)))
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		config = {
			"cwd": str(tmp_path),
			"client_tools": [
				{
					"type": "function",
					"function": {
						"name": "report",
						"description": "build",
						"parameters": {"type": "object", "properties": {}},
					},
				}
			],
			"callback_url": "https://client.invalid/tools",
			"auto_approve": True,
		}
		sid = (await client.post("/sessions", json=config)).json()["session_id"]
		run = asyncio.create_task(
			client.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "report"})
		)
		token = await asyncio.wait_for(tokens.get(), timeout=5)
		waiting = await client.post(f"/sessions/{sid}/tool_waiting", json={"token": token})
		assert waiting.json() == {"waiting": True}

		assert (await client.post("/sessions/nope/tool_result", json={"token": token})).status_code == 404
		wrong = await client.post(f"/sessions/{sid}/tool_result", json={"token": "wrong"})
		assert wrong.json() == {"delivered": False}
		posted = await client.post(f"/sessions/{sid}/tool_result", json={"token": token, "content": "ready"})
		assert posted.json() == {"delivered": True}
		waiting = await client.post(f"/sessions/{sid}/tool_waiting", json={"token": token})
		assert waiting.json() == {"waiting": False}

		assert (await asyncio.wait_for(run, timeout=5)).json()["reason"] == "done"
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["content"] for row in entries if row["type"] == "tool_result"] == ["ready"]


def test_rewind_branches_the_conversation_over_http(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "first"})

	# a rewind can retract rows before a cursor, so the snapshot view refuses one
	assert c.get(f"/sessions/{sid}/entries", params={"since": 2}).status_code == 422
	assert c.get(f"/sessions/{sid}/entries", params={"since": 2, "path": "all"}).status_code == 200

	assert c.post(f"/sessions/{sid}/rewind", json={"target_seq": 1}).json() == {"status": "rewound"}

	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "second"})
	active = c.get(f"/sessions/{sid}/entries").json()["entries"]  # the conversation view is the default
	assert [r["content"] for r in active if r["type"] == "user_message"] == ["second"]
	everything = c.get(f"/sessions/{sid}/entries", params={"path": "all"}).json()["entries"]
	assert [r["content"] for r in everything if r["type"] == "user_message"] == ["first", "second"]
	assert "rewind" in [r["type"] for r in everything]  # the old branch is still there

	assert c.post(f"/sessions/{sid}/rewind", json={"target_seq": 999}).status_code == 409


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
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda name, **kw: mock)
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
	from flow_harness.model import discovery
	from flow_harness.model.catalog import PROVIDERS

	for provider in PROVIDERS:
		for name in provider.api_key_envs:
			monkeypatch.delenv(name, raising=False)

	async def fake_http_models(url, auth, client, *, provider_id=None):
		assert provider_id == "openai"
		return [("gpt-4o", None)]

	monkeypatch.setattr(discovery, "_http_models", fake_http_models)
	c = _client(tmp_path)
	assert c.get("/models").json() == {"models": [], "errors": []}

	monkeypatch.setenv("OPENAI_API_KEY", "k")
	assert c.get("/models").json() == {
		"models": [
			{"name": "openai/gpt-4o", "provider": "openai", "supports_images": True, "display_name": None}
		],
		"errors": [],
	}


def test_list_sessions_includes_cold_on_disk_sessions_which_keep_their_preset(tmp_path):
	c = _client(tmp_path)
	used = c.post(
		"/sessions",
		json={"model": "mock", "cwd": str(tmp_path / "a"), "preset": "review"},
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
			"workspace": None,
		}
		# `fresh` has no durable entries — nothing to resume, so the listing omits it
		assert fresh not in rows
		assert client.get(f"/sessions/{used}").json()["config"]["preset"] == "review"
