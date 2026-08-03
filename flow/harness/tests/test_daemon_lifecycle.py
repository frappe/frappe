"""Lifecycle tests for the daemons behind bare `flow` — real subprocesses, no TUI."""

import time

import httpx
import pytest

from flow.cli.daemon import bind_and_publish, spawn_private, teardown


@pytest.fixture
def daemon(tmp_path):
	d = spawn_private(str(tmp_path / "data"), timeout=15.0)
	yield d
	teardown(d)


def test_private_daemon_requires_its_token(daemon):
	with httpx.Client(base_url=daemon.base_url, timeout=5.0) as http:
		assert http.get("/healthz").json() == {"ok": True}
		assert http.get("/sessions").status_code == 401
		authed = http.get("/sessions", headers={"Authorization": f"Bearer {daemon.token}"})
		assert authed.status_code == 200
		assert "sessions" in authed.json()


def test_teardown_stops_the_daemon(tmp_path):
	d = spawn_private(str(tmp_path / "data"), timeout=15.0)
	teardown(d)
	assert d.process.poll() is not None
	with httpx.Client(timeout=1.0) as http, pytest.raises(httpx.TransportError):
		http.get(f"{d.base_url}/healthz")


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


def test_bind_and_publish_writes_resolved_port(tmp_path):
	port_file = tmp_path / "daemon.port"
	sock = bind_and_publish("127.0.0.1", 0, str(port_file))
	try:
		port = sock.getsockname()[1]
		assert port > 0
		assert int(port_file.read_text()) == port
	finally:
		sock.close()
