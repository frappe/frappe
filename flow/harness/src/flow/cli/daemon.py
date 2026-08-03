"""Spawn, readiness, and teardown for the daemons behind bare `flow` and `flow serve`.

Bare `flow` runs a private daemon: loopback, ephemeral port, fresh auth token, gone
when the TUI exits. `flow serve --background` detaches a long-lived daemon on the
configured host and port. Both spawn a foreground `flow serve` as a subprocess, so
every mode runs the same server path and a daemon crash never takes the TUI down
with it.

POSIX-only for now (process groups, stdin-pipe watchdog).
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass

import httpx

_POLL_INTERVAL = 0.05
# -P keeps the cwd off sys.path: `python -m` would otherwise prepend it, and a cwd
# inside the package tree (e.g. src/flow/model) makes local modules shadow real
# packages (flow/model/litellm.py shadows litellm).
_SERVE_ARGV = [sys.executable, "-P", "-m", "flow.cli.main", "serve"]


class DaemonError(Exception):
	"""The daemon subprocess failed to start or become healthy."""


@dataclass
class PrivateDaemon:
	"""A running private daemon owned by one TUI process."""

	process: subprocess.Popen
	base_url: str
	token: str
	log_path: str


def spawn_private(data_dir: str, *, timeout: float = 5.0) -> PrivateDaemon:
	"""Start a private loopback daemon on an ephemeral port and wait until it is healthy.

	The child binds port 0 itself and reports the resolved port through a port file,
	so there is no bind race. Auth is always on (fresh token), even on loopback. The
	child holds our stdin pipe: EOF means this process died — any way, including
	SIGKILL — and the child exits, so orphaned private daemons cannot accumulate.
	"""
	token = secrets.token_urlsafe(32)
	log_path = _log_path(data_dir, "private")
	fd, port_file = tempfile.mkstemp(prefix="flow-daemon-", suffix=".port")
	os.close(fd)
	os.unlink(port_file)  # the child creates it; a pre-made empty file would race the poll
	with open(log_path, "ab") as log_file:
		process = subprocess.Popen(
			[
				*_SERVE_ARGV,
				*("--host", "127.0.0.1", "--port", "0", "--data-dir", data_dir),
				*("--port-file", port_file, "--parent-watch"),
			],
			env={**os.environ, "FLOW_AUTH_TOKEN": token},
			stdin=subprocess.PIPE,
			stdout=log_file,
			stderr=subprocess.STDOUT,
		)
	try:
		port = _wait_port_file(process, port_file, timeout, log_path)
		base_url = f"http://127.0.0.1:{port}"
		_wait_healthz(process, base_url, timeout, log_path)
	except DaemonError:
		_stop_process(process)
		raise
	finally:
		_unlink_quietly(port_file)
	return PrivateDaemon(process=process, base_url=base_url, token=token, log_path=log_path)


def spawn_background(host: str, port: int, data_dir: str, *, timeout: float = 5.0) -> str:
	"""`flow serve --background`: detach a daemon on the configured host/port; returns its base URL."""
	log_path = _log_path(data_dir, f"{host}-{port}")
	with open(log_path, "ab") as log_file:
		process = subprocess.Popen(
			[*_SERVE_ARGV, "--host", host, "--port", str(port), "--data-dir", data_dir],
			stdin=subprocess.DEVNULL,
			stdout=log_file,
			stderr=subprocess.STDOUT,
			start_new_session=True,  # survives this shell and its signals
		)
	probe_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
	_wait_healthz(process, f"http://{probe_host}:{port}", timeout, log_path)
	return f"http://{host}:{port}"


def teardown(daemon: PrivateDaemon, *, session_id: str | None = None, drain_timeout: float = 5.0) -> None:
	"""Stop a private daemon.

	Quit during an active run aborts and drains without a confirmation prompt (by
	design): abort, wait briefly for the run to end so the log gets a clean aborted
	terminus, then terminate → grace → kill.
	"""
	process = daemon.process
	if process.poll() is None and session_id is not None:
		try:
			with httpx.Client(
				base_url=daemon.base_url,
				headers={"Authorization": f"Bearer {daemon.token}"},
				timeout=2.0,
			) as http:
				if _session_state(http, session_id) == "running":
					http.post(f"/sessions/{session_id}/abort")
					deadline = time.monotonic() + drain_timeout
					while time.monotonic() < deadline and _session_state(http, session_id) == "running":
						time.sleep(_POLL_INTERVAL)
		except httpx.HTTPError:
			pass  # daemon already gone or wedged; process teardown below still runs
	_stop_process(process)
	if process.stdin is not None:
		process.stdin.close()


def watch_parent_stdin() -> None:
	"""`serve --parent-watch`: exit the daemon when stdin reaches EOF.

	The parent holds our stdin pipe and never writes to it, so a successful read
	cannot happen; EOF means the parent is dead and this daemon must not outlive it.
	"""

	def _watch() -> None:
		try:
			while os.read(0, 4096):
				pass
		except OSError:
			pass
		os._exit(0)

	threading.Thread(target=_watch, name="parent-watch", daemon=True).start()


def bind_and_publish(host: str, port: int, port_file: str) -> socket.socket:
	"""Bind the listening socket (port 0 = ephemeral) and write the resolved port to
	`port_file`. The write is atomic so a polling parent never reads a partial value."""
	sock = socket.create_server((host, port))
	resolved = sock.getsockname()[1]
	tmp_path = f"{port_file}.tmp"
	with open(tmp_path, "w", encoding="utf-8") as f:
		f.write(str(resolved))
	os.replace(tmp_path, port_file)
	return sock


def _wait_port_file(process: subprocess.Popen, port_file: str, timeout: float, log_path: str) -> int:
	deadline = time.monotonic() + timeout
	while time.monotonic() < deadline:
		if process.poll() is not None:
			raise DaemonError(
				f"flow daemon exited with code {process.returncode} during startup; log: {log_path}"
			)
		try:
			with open(port_file, encoding="utf-8") as f:
				return int(f.read())
		except (OSError, ValueError):
			time.sleep(_POLL_INTERVAL)
	raise DaemonError(f"flow daemon did not report a port within {timeout:g} s; log: {log_path}")


def _wait_healthz(process: subprocess.Popen, base_url: str, timeout: float, log_path: str) -> None:
	deadline = time.monotonic() + timeout
	with httpx.Client(timeout=2.0) as http:
		while time.monotonic() < deadline:
			if process.poll() is not None:
				raise DaemonError(
					f"flow daemon exited with code {process.returncode} during startup; log: {log_path}"
				)
			try:
				if http.get(f"{base_url}/healthz").json() == {"ok": True}:
					return
			except (httpx.HTTPError, ValueError):
				pass
			time.sleep(_POLL_INTERVAL)
	raise DaemonError(f"flow daemon was not healthy within {timeout:g} s; log: {log_path}")


def _session_state(http: httpx.Client, session_id: str) -> str | None:
	response = http.get(f"/sessions/{session_id}")
	if response.is_error:
		return None
	return response.json().get("state")


def _stop_process(process: subprocess.Popen) -> None:
	if process.poll() is not None:
		return
	process.terminate()
	try:
		process.wait(timeout=3.0)
	except subprocess.TimeoutExpired:
		process.kill()
		process.wait(timeout=3.0)


def _log_path(data_dir: str, tag: str) -> str:
	logs_dir = os.path.join(data_dir, "logs")
	os.makedirs(logs_dir, exist_ok=True)
	return os.path.join(logs_dir, f"daemon-{tag}-{os.getpid()}.log")


def _unlink_quietly(path: str) -> None:
	try:
		os.unlink(path)
	except OSError:
		pass
