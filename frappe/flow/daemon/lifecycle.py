# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Keeps the flow server provisioned for every site and running.

Bench-wide state: <bench>/sites/flow-server/. Each site's sessions: <site>/private/flow/.
Extensions an admin adds by hand: <site>/private/flow/extensions/, loaded at start.
Runtime files: <bench>/flow-server/. Logs: the bench's logs directory.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import mkstemp
from urllib.parse import urlsplit

import click
import frappe
from frappe.installer import update_site_config
from frappe.utils import get_bench_path
from frappe.utils.synchronization import filelock

from flow.daemon.client import DaemonClient, DaemonError
from flow.flow.doctype.flow_tool.flow_tool import sync_server_tools

START_TIMEOUT = 30
EXTENSIONS_DIR = "extensions"
STOP_TIMEOUT = 5
LOCK = "flow_server"
# The daemon inherits only these names: no bench credentials or stray FLOW_* switches.
INHERITED_ENV = (
	"PATH",
	"HOME",
	"LANG",
	"LC_ALL",
	"TZ",
	"TMPDIR",
	"SSL_CERT_FILE",
	"REQUESTS_CA_BUNDLE",
	"HTTP_PROXY",
	"HTTPS_PROXY",
	"NO_PROXY",
	"http_proxy",
	"https_proxy",
	"no_proxy",
)


# --- hooks --------------------------------------------------------------


def after_install() -> None:
	provision_site()
	_run_or_warn(ensure_running)
	_run_or_warn(sync_server_tools)


def after_migrate() -> None:
	"""Restarts so `bench update` ships new daemon code, then mirrors its extension tools."""
	provision_site()
	_run_or_warn(restart)
	_run_or_warn(sync_server_tools)


def keep_alive() -> None:
	"""Scheduler: restart a daemon that died."""
	if not _flow_bin().exists():
		return
	ensure_running()


def _run_or_warn(step: Callable[[], object]) -> None:
	"""A daemon that cannot come up must not fail the install or migrate."""
	try:
		step()
	except (OSError, RuntimeError) as exc:
		click.secho(f"flow server not running: {exc}", fg="yellow")
		click.secho("Run `bench flow-server setup` to finish setting it up.", fg="yellow")


# --- per-site provisioning ----------------------------------------------


def provision_site() -> None:
	"""Give this site its secret and tenants entry, then tell the daemon."""
	if not frappe.conf.flow_server_secret:
		update_site_config("flow_server_secret", frappe.generate_hash(length=48))
	entry = {
		"token": frappe.conf.flow_server_secret,
		"allowed_roots": [str(root) for root in allowed_roots()],
		"ignore_hidden_files": True,
		"callback_hosts": [callback_host()],
		"data_dir": str(site_data_dir()),
	}
	_edit_tenants(lambda tenants: tenants.__setitem__(frappe.local.site, entry))
	reload_tenants(frappe.conf.flow_server_secret)


def remove_site() -> None:
	"""before_uninstall: drop the tenants entry and everything the daemon kept for the site."""
	site = frappe.local.site
	remaining = _edit_tenants(lambda tenants: tenants.pop(site, None))
	if remaining:
		if not reload_tenants(frappe.conf.flow_server_secret):
			restart()
	else:
		stop()
	shutil.rmtree(site_data_dir(), ignore_errors=True)


def reload_tenants(token: str) -> bool:
	"""Ask a running daemon to re-read the tenants file; a stopped one reads it at start."""
	if not healthy():
		return False
	try:
		with DaemonClient(str(socket_path()), token) as client:
			client.reload_tenants()
	except DaemonError as exc:
		click.secho(f"flow server did not reload its tenants: {exc.detail}", fg="yellow")
		return False
	return True


def session_root() -> Path:
	"""The site's public files folder, which sessions use as their cwd."""
	return Path(frappe.get_site_path("public", "files")).resolve()


def site_extensions_dir() -> Path:
	"""Extensions an admin adds over SSH; the daemon loads the folder at start."""
	return site_data_dir() / EXTENSIONS_DIR


def site_data_dir() -> Path:
	"""The daemon's sessions for this site, kept inside the site so a deploy moves them too."""
	return Path(frappe.get_site_path("private", "flow")).resolve()


def allowed_roots() -> tuple[Path, Path]:
	"""The site's files plus bench's apps folder."""
	return (session_root(), Path(get_bench_path()).resolve() / "apps")


def app_source_prompt(tools: list[str]) -> str:
	if not tools:
		return ""
	sources = app_sources()
	if not sources:
		return ""
	paths = "\n".join(f"- {app}: {root}" for app, root in sources)
	available = ", ".join(tools)
	return f"\n\nAPP SOURCE CODE\nUse {available} to inspect these installed apps:\n{paths}"


def app_sources() -> list[tuple[str, Path]]:
	"""Outer source directories for the apps installed on this site."""
	return [
		(app, Path(frappe.get_app_path(app)).resolve().parent)
		for app in frappe.get_installed_apps(_ensure_on_bench=True)
	]


def callback_host() -> str:
	return urlsplit(callback_url()).netloc


def callback_url() -> str:
	"""The site's own web server on loopback, or flow_server_url from site config."""
	local = f"http://127.0.0.1:{frappe.conf.webserver_port or 8000}"
	base = (frappe.conf.flow_server_url or local).rstrip("/")
	return f"{base}/api/method/flow.daemon.callback.callback"


def callback_headers() -> dict[str, str]:
	"""Frappe serves the site this header names, whatever host the request came to."""
	return {"X-Frappe-Site-Name": frappe.local.site}


def _edit_tenants(change: Callable[[dict], object]) -> dict:
	"""Apply `change` to the tenants mapping under the bench-wide lock; the file is
	written atomically and stays 0600 because it holds every site's token."""
	state_dir().mkdir(parents=True, exist_ok=True)
	with filelock(LOCK, is_global=True):
		tenants = _read_tenants()
		change(tenants)
		fd, tmp = mkstemp(prefix=".tenants.", dir=state_dir())
		try:
			with os.fdopen(fd, "w", encoding="utf-8") as file:
				file.write(json.dumps(tenants, indent=1, sort_keys=True))
			os.chmod(tmp, 0o600)
			os.replace(tmp, tenants_file())
		except BaseException:
			os.unlink(tmp)
			raise
	return tenants


# --- daemon lifecycle ---------------------------------------------------


def ensure_running() -> bool:
	"""Start a daemon that is not answering; True when this call started it."""
	with filelock(LOCK, is_global=True):
		if healthy():
			return False
		_restart()
		return True


def restart() -> None:
	with filelock(LOCK, is_global=True):
		_restart()


def start() -> None:
	"""Launch the daemon detached and wait until it answers on the socket."""
	with filelock(LOCK, is_global=True):
		_start()


def stop() -> None:
	with filelock(LOCK, is_global=True):
		_stop()


def _restart() -> None:
	_stop()
	_start()


def _start() -> None:
	if not _flow_bin().exists():
		raise RuntimeError("flow server is missing from the bench environment; reinstall the Flow app")
	tenants = _read_tenants()
	if not tenants:
		raise RuntimeError("no site is provisioned yet; run `bench flow-server setup`")
	if healthy():
		raise RuntimeError(f"a flow server already answers on {socket_path()}; stop it by hand")
	env = {name: os.environ[name] for name in INHERITED_ENV if name in os.environ}
	env["FLOW_TENANTS_FILE"] = str(tenants_file())
	folders = _extension_folders(tenants)
	allowed = ["read_file", "grep", *(row["name"] for row in extension_tools(folders))]
	env["FLOW_POLICY"] = json.dumps({"tool_allowlist": allowed})
	if redis_url := _redis_url():
		env["FLOW_REDIS_URL"] = redis_url
	command = [
		str(_flow_bin()),
		"serve",
		*("--uds", str(socket_path())),
		*("--data-dir", str(state_dir() / "data")),
		*("--profile", "deployed"),
		*(arg for folder in folders for arg in ("--extension", str(folder))),
	]
	runtime_dir().mkdir(parents=True, exist_ok=True)
	log = log_path()
	with log.open("ab") as out:
		process = subprocess.Popen(
			command,
			stdin=subprocess.DEVNULL,
			stdout=out,
			stderr=out,
			cwd=runtime_dir(),
			env=env,
			start_new_session=True,
			umask=0o077,  # session transcripts and the socket are the bench user's alone
		)
	try:
		pid_file().write_text(str(process.pid))
		deadline = time.monotonic() + START_TIMEOUT
		while time.monotonic() < deadline and process.poll() is None:
			if healthy():
				return
			time.sleep(0.2)
		raise RuntimeError(f"flow server did not start, see {log}:\n{_log_tail(log)}")
	except BaseException:
		try:
			_terminate_process(process)
		finally:
			pid_file().unlink(missing_ok=True)
			socket_path().unlink(missing_ok=True)
		raise


def _stop() -> None:
	pid = pid_file()
	try:
		process_id = int(pid.read_text())
	except (OSError, ValueError):
		return
	if _is_daemon(process_id):
		os.kill(process_id, signal.SIGTERM)
		deadline = time.monotonic() + STOP_TIMEOUT
		while _alive(process_id) and time.monotonic() < deadline:
			time.sleep(0.1)
		if _alive(process_id):
			os.kill(process_id, signal.SIGKILL)
	pid.unlink(missing_ok=True)


def _terminate_process(process: subprocess.Popen) -> None:
	"""Stop and reap a child that did not complete startup."""
	if process.poll() is not None:
		return
	process.terminate()
	try:
		process.wait(timeout=STOP_TIMEOUT)
	except subprocess.TimeoutExpired:
		process.kill()
		process.wait(timeout=STOP_TIMEOUT)


def status() -> str:
	state = f"running on {socket_path()}" if healthy() else "not running"
	sites = ", ".join(_read_tenants()) or "none"
	return f"flow server {state} · sites: {sites}"


def healthy() -> bool:
	try:
		with DaemonClient(str(socket_path())) as client:
			client.healthz()
	except DaemonError:
		return False
	return True


# --- helpers and paths --------------------------------------------------


def _redis_url() -> str | None:
	"""Where the daemon publishes session events: the bench queue Redis, which Frappe's
	socketio process also reads, so one bus serves every site's relay."""
	conf = frappe.get_common_site_config()
	return conf.flow_redis_url or conf.redis_queue


def extension_tools(folders: list[Path]) -> list[dict]:
	"""The tools the daemon would load from `folders`, listed by the harness without serving."""
	if not folders:
		return []
	proc = subprocess.run(
		[str(_flow_bin()), "extension-tools", *map(str, folders)], capture_output=True, text=True
	)
	if proc.stderr.strip():
		click.secho(proc.stderr.strip(), fg="yellow")
	if proc.returncode != 0:
		raise RuntimeError("flow extension-tools failed; see the messages above")
	return json.loads(proc.stdout)["tools"]


def _extension_folders(tenants: dict) -> list[Path]:
	"""Every site's extensions folder that exists."""
	folders = (
		Path(entry["data_dir"]) / EXTENSIONS_DIR for entry in tenants.values() if entry.get("data_dir")
	)
	return [folder for folder in folders if folder.is_dir()]


def _read_tenants() -> dict:
	try:
		return json.loads(tenants_file().read_text(encoding="utf-8"))
	except FileNotFoundError:
		return {}


def _is_daemon(pid: int) -> bool:
	"""A stale pid file must never signal a reused pid: only our own daemon counts."""
	result = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True)
	return str(_flow_bin()) in result.stdout


def _alive(pid: int) -> bool:
	try:
		os.waitpid(pid, os.WNOHANG)  # reaps a daemon this very process started
	except ChildProcessError:
		pass
	try:
		os.kill(pid, 0)
	except ProcessLookupError:
		return False
	return True


def _log_tail(log: Path, chars: int = 2000) -> str:
	try:
		return log.read_text()[-chars:]
	except OSError:
		return ""


def socket_path() -> Path:
	return runtime_dir() / "flow.sock"


def pid_file() -> Path:
	return runtime_dir() / "daemon.pid"


def log_path() -> Path:
	return Path(get_bench_path()) / "logs" / "flow-server.log"


def tenants_file() -> Path:
	return state_dir() / "tenants.json"


def _flow_bin() -> Path:
	"""The harness CLI, installed next to this interpreter in the bench env."""
	return Path(sys.executable).parent / "flow"


def state_dir() -> Path:
	return Path(get_bench_path()) / "sites" / "flow-server"


def runtime_dir() -> Path:
	return Path(get_bench_path()) / "flow-server"
