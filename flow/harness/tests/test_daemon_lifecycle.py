"""Lifecycle tests for the daemons behind bare `flow` — real subprocesses, no TUI."""

import os
import socket
import stat
import time

import httpx
import pytest

from flow.cli.daemon import bind_unix, spawn_private, teardown
from flow.config import UDS_URL


@pytest.fixture
def daemon(tmp_path):
	d = spawn_private(str(tmp_path / "data"), timeout=15.0)
	yield d
	teardown(d)


def _client(d, **kw):
	return httpx.Client(base_url=UDS_URL, transport=httpx.HTTPTransport(uds=d.socket_path), **kw)


def test_private_daemon_requires_its_token(daemon):
	with _client(daemon, timeout=5.0) as http:
		assert http.get("/healthz").json() == {"ok": True}
		assert http.get("/sessions").status_code == 401
		authed = http.get("/sessions", headers={"Authorization": f"Bearer {daemon.token}"})
		assert authed.status_code == 200
		assert "sessions" in authed.json()


def test_teardown_stops_the_daemon(tmp_path):
	d = spawn_private(str(tmp_path / "data"), timeout=15.0)
	teardown(d)
	assert d.process.poll() is not None
	assert not os.path.exists(d.socket_path)
	with _client(d, timeout=1.0) as http, pytest.raises(httpx.TransportError):
		http.get("/healthz")


def test_orphaned_daemon_exits_on_parent_death(tmp_path):
	d = spawn_private(str(tmp_path / "data"), timeout=15.0)
	try:
		# the parent dying — even by SIGKILL — closes its end of the stdin pipe
		assert d.process.stdin is not None
		d.process.stdin.close()
		deadline = time.monotonic() + 2.0
		while time.monotonic() < deadline and d.process.poll() is None:
			time.sleep(0.05)
		assert d.process.poll() is not None
	finally:
		teardown(d)


def test_bind_unix_listens_and_replaces_stale_file(tmp_path):
	path = str(tmp_path / "daemon.sock")
	(tmp_path / "daemon.sock").write_text("stale")
	sock = bind_unix(path)
	try:
		mode = os.stat(path).st_mode
		assert stat.S_ISSOCK(mode)
		assert stat.S_IMODE(mode) == 0o600
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
			probe.connect(path)
	finally:
		sock.close()
