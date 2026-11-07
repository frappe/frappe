"""Spawn, readiness, and teardown for the daemons behind bare `flow` and `flow serve`.

Bare `flow` runs a private daemon: a unix socket under the data dir, fresh auth
token, gone when the TUI exits. `flow serve --background` detaches a long-lived
daemon on the configured host and port. Both spawn a foreground `flow serve` as a
subprocess, so every mode runs the same server path and a daemon crash never takes
the TUI down with it.

POSIX-only for now (unix sockets, stdin-pipe watchdog).
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

import httpx

from flow_harness.config import UDS_URL

_POLL_INTERVAL = 0.05
# -P keeps the cwd off sys.path: `python -m` would otherwise prepend it, and a cwd
# inside the package tree (e.g. src/flow_harness/model) makes local modules shadow real
# packages (flow_harness/model/litellm.py shadows litellm).
_SERVE_ARGV = [sys.executable, "-P", "-m", "flow_harness.cli.main", "serve"]


class DaemonError(Exception):
	"""The daemon subprocess failed to start or become healthy."""


@dataclass
class PrivateDaemon:
	"""A running private daemon owned by one TUI process."""

	process: subprocess.Popen
	socket_path: str
	token: str
	log_path: str


def spawn_private(
	data_dir: str,
	*,
	timeout: float = 15.0,
	extension_paths: list[str] | None = None,
	extensions_enabled: bool = True,
) -> PrivateDaemon:
	"""Start a private daemon on a unix socket under the data dir and wait until healthy.

	The socket path is chosen up front (per-pid, so concurrent TUIs never collide), so
	there is nothing to discover — readiness is just healthz over the socket. Auth is
	always on (fresh token), even though the socket is local. The child holds our stdin
	pipe: EOF means this process died — any way, including SIGKILL — and the child
	exits, so orphaned private daemons cannot accumulate.
	"""
	token = secrets.token_urlsafe(32)
	log_path = _log_path(data_dir, "private")
	socket_path = os.path.join(data_dir, f"daemon-{os.getpid()}.sock")
	with open(log_path, "ab") as log_file:
		process = subprocess.Popen(
			[
				*_SERVE_ARGV,
				*("--uds", socket_path, "--data-dir", data_dir),
				"--parent-watch",
				# always local: a FLOW_PROFILE in the env must not harden the TUI's own daemon
				*("--profile", "local"),
				*([] if extensions_enabled else ["--no-extensions"]),
				*[argument for path in (extension_paths or []) for argument in ("--extension", path)],
			],
			# no FLOW_POLICY/FLOW_TENANTS: stray env vars must not reconfigure the TUI's own daemon
			env={k: v for k, v in os.environ.items() if k not in ("FLOW_POLICY", "FLOW_TENANTS")}
			| {"FLOW_AUTH_TOKEN": token},
			stdin=subprocess.PIPE,
			stdout=log_file,
			stderr=subprocess.STDOUT,
		)
	try:
		_wait_healthz(process, UDS_URL, timeout, log_path, uds=socket_path)
	except DaemonError:
		_stop_process(process)
		_unlink_quietly(socket_path)
		raise
	return PrivateDaemon(process=process, socket_path=socket_path, token=token, log_path=log_path)


def spawn_background(
	host: str,
	port: int,
	data_dir: str,
	*,
	timeout: float = 15.0,
	extension_paths: list[str] | None = None,
	extensions_enabled: bool = True,
	profile: str = "local",
) -> str:
	"""`flow serve --background`: detach a daemon on the configured host/port; returns its base URL."""
	log_path = _log_path(data_dir, f"{host}-{port}")
	with open(log_path, "ab") as log_file:
		process = subprocess.Popen(
			[
				*_SERVE_ARGV,
				"--host",
				host,
				"--port",
				str(port),
				"--data-dir",
				data_dir,
				*("--profile", profile),
				*([] if extensions_enabled else ["--no-extensions"]),
				*[argument for path in (extension_paths or []) for argument in ("--extension", path)],
			],
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
				base_url=UDS_URL,
				transport=httpx.HTTPTransport(uds=daemon.socket_path),
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
	_unlink_quietly(daemon.socket_path)  # a killed child cannot remove its own socket file


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


def bind_unix(socket_path: str) -> socket.socket:
	"""Bind and listen on a unix socket, replacing any stale file at the path.

	A leftover file is expected after a crash or SIGKILL — nothing unlinks it then —
	so replace it instead of failing. The socket is chmod 0600: auth tokens travel
	over it, so other local users must not connect at all.
	"""
	_unlink_quietly(socket_path)
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	sock.bind(socket_path)
	os.chmod(socket_path, 0o600)
	sock.listen(128)
	return sock


def _wait_healthz(
	process: subprocess.Popen, base_url: str, timeout: float, log_path: str, *, uds: str | None = None
) -> None:
	deadline = time.monotonic() + timeout
	transport = httpx.HTTPTransport(uds=uds) if uds else None
	with httpx.Client(timeout=2.0, transport=transport) as http:
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
