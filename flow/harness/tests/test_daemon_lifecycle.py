"""Lifecycle tests for the daemons behind bare `flow` — real subprocesses, no TUI."""

import os
import socket
import stat
import time

import httpx
import pytest

from flow_harness.cli.daemon import bind_unix, spawn_private, teardown
from flow_harness.config import UDS_URL


def _client(d, **kw):
	return httpx.Client(base_url=UDS_URL, transport=httpx.HTTPTransport(uds=d.socket_path), **kw)


def test_private_daemon_requires_its_token_and_stops_on_teardown(tmp_path, monkeypatch):
	# A Frappe bench provides its own `flow`; the daemon must never import it,
	# including when its CLI launches a fresh Python process.
	package = tmp_path / "flow"
	package.mkdir()
	(package / "__init__.py").write_text('raise AssertionError("imported the other flow package")\n')
	pythonpath = os.pathsep.join(filter(None, (str(tmp_path), os.environ.get("PYTHONPATH"))))
	monkeypatch.setenv("PYTHONPATH", pythonpath)
	d = spawn_private(str(tmp_path / "data"), timeout=15.0)
	try:
		with _client(d, timeout=5.0) as http:
			assert http.get("/healthz").json() == {"ok": True}
			assert http.get("/sessions").status_code == 401
			response = http.get("/sessions", headers={"Authorization": f"Bearer {d.token}"})
			assert response.status_code == 200
			assert response.json() == {"sessions": []}
	finally:
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
