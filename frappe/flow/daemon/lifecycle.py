# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Gives each site its flow server secret and keeps the server running.

Bench-wide state: <bench>/sites/flow-server/. Each site's secret: <site>/site_config.json.
Each site's sessions: <site>/private/flow/.
Extensions an admin adds by hand: <site>/private/flow/extensions/, loaded for that site at start.
Runtime files: <bench>/flow-server/. Logs: the bench's logs directory.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import click

import frappe
from frappe.flow.daemon.client import DaemonClient, DaemonError
from frappe.flow.doctype.flow_tool.flow_tool import sync_server_tools
from frappe.installer import update_site_config
from frappe.utils import get_bench_path
from frappe.utils.synchronization import filelock

START_TIMEOUT = 30
EXTENSIONS_DIR = "extensions"
STOP_TIMEOUT = 5
UMASK = 0o077  # session transcripts and the socket are the bench user's alone
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
	_run_or_warn(_restart_if_needed)
	_run_or_warn(sync_server_tools)


def _restart_if_needed() -> None:
	"""Supervised benches restart the program after updates."""
	if not supervised() or site_extensions_dir().is_dir():  # extension tools are allowed only at start
		restart()


def keep_alive() -> None:
	"""Scheduler: restart a daemon that died, unless supervisor runs it."""
	if not _flow_bin().exists() or supervised():
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
	"""Give this site its flow server secret."""
	if not frappe.conf.flow_server_secret:
		update_site_config("flow_server_secret", frappe.generate_hash(length=48))


def session_root() -> Path:
	"""The site's public files folder, which sessions use as their cwd."""
	return Path(frappe.get_site_path("public", "files")).resolve()


def site_extensions_dir() -> Path:
	"""Extensions an admin adds over SSH; the daemon loads the folder for this site at start."""
	return site_data_dir() / EXTENSIONS_DIR


def site_data_dir() -> Path:
	"""The daemon's sessions for this site, kept inside the site so a deploy moves them too."""
	return Path(frappe.get_site_path("private", "flow")).resolve()


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


def callback_url() -> str:
	"""The bench's web server on loopback, or flow_server_url from common_site_config.json."""
	return f"{_callback_base()}/api/method/frappe.flow.daemon.callback.callback"


def _callback_base() -> str:
	conf = frappe.get_common_site_config()
	local = f"http://127.0.0.1:{conf.get('webserver_port') or 8000}"
	return (conf.get("flow_server_url") or local).rstrip("/")


# --- daemon lifecycle ---------------------------------------------------


def ensure_running() -> bool:
	"""Start a daemon that is not answering; True when this call started it."""
	if supervised():
		_wait_for_supervisor()
		return False
	with filelock(LOCK, is_global=True):
		if healthy():
			return False
		_restart()
		return True


def restart() -> None:
	if supervised():  # stop it; supervisor starts it, we wait
		stop()
		_wait_for_supervisor()
		return
	with filelock(LOCK, is_global=True):
		_restart()


def start() -> None:
	"""Launch the daemon detached and wait until it answers on the socket."""
	if supervised():
		_wait_for_supervisor()
		return
	with filelock(LOCK, is_global=True):
		_start()


def serve() -> None:
	"""Run the daemon in the foreground, for supervisor. It replaces one Flow started itself.

	A process manager that sets FLOW_SERVER_MANAGER, as Pilot does from pyproject.toml,
	records the ownership for the whole bench, so no other process starts a daemon."""
	if not supervised():
		if os.environ.get("FLOW_SERVER_MANAGER") != "supervisor":
			raise RuntimeError(
				"set flow_server_manager to supervisor in common_site_config.json before serving"
			)
		update_site_config(
			"flow_server_manager",
			"supervisor",
			site_config_path=str(_sites_dir() / "common_site_config.json"),
		)
	runtime_dir().mkdir(parents=True, exist_ok=True)
	with filelock(LOCK, is_global=True):
		_stop()
		command, env = _prepare()
		pid_file().write_text(str(os.getpid()))
	os.chdir(runtime_dir())
	os.umask(UMASK)
	os.execve(command[0], command, env)


def stop() -> None:
	with filelock(LOCK, is_global=True):
		_stop()


def _restart() -> None:
	_stop()
	_start()


def _start() -> None:
	command, env = _prepare()
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
			umask=UMASK,
		)
	try:
		pid_file().write_text(str(process.pid))
		if _wait_until_healthy(process):
			return
		raise RuntimeError(f"flow server did not start, see {log}:\n{_log_tail(log)}")
	except BaseException:
		try:
			_terminate_process(process)
		finally:
			pid_file().unlink(missing_ok=True)
			socket_path().unlink(missing_ok=True)
		raise


def _prepare() -> tuple[list[str], dict[str, str]]:
	"""The daemon's command line and scrubbed environment, once no other daemon answers."""
	if not _flow_bin().exists():
		raise RuntimeError("flow server is missing from the bench environment; reinstall the Flow app")
	if healthy():
		raise RuntimeError(f"a flow server already answers on {socket_path()}; stop it by hand")
	runtime_dir().mkdir(parents=True, exist_ok=True)
	env = {name: os.environ[name] for name in INHERITED_ENV if name in os.environ}
	env["FLOW_TENANTS"] = json.dumps(tenant_template())
	allowed = ["read", "grep", "subagent", "suggest_replies"]
	for folder in _extension_folders():
		for row in extension_tools([folder]):
			if row["name"] not in allowed:
				allowed.append(row["name"])
	env["FLOW_POLICY"] = json.dumps({"tool_allowlist": allowed})
	if redis_url := _redis_url():
		env["FLOW_REDIS_URL"] = redis_url
	command = [
		str(_flow_bin()),
		"serve",
		*("--uds", str(socket_path())),
		*("--data-dir", str(state_dir() / "data")),
		*("--profile", "deployed"),
	]
	return command, env


def tenant_template() -> dict:
	"""The daemon's settings for every site; {site} stands for the site name."""
	site = _sites_dir() / "{site}"
	return {
		"token_file": str(site / "site_config.json"),
		"token_key": "flow_server_secret",
		"allowed_roots": [str(site / "public" / "files"), str(Path(get_bench_path()).resolve() / "apps")],
		"ignore_hidden_files": True,
		"callback_hosts": [urlsplit(_callback_base()).netloc],
		# Frappe serves the site this header names
		"callback_headers": {"X-Frappe-Site-Name": "{site}"},
		"data_dir": str(site / "private" / "flow"),
		"extensions": [str(site / "private" / "flow" / EXTENSIONS_DIR)],
	}


def _wait_for_supervisor() -> None:
	if not _wait_until_healthy():
		raise RuntimeError("flow server did not become ready under supervisor; check its status and log")


def _wait_until_healthy(process: subprocess.Popen | None = None) -> bool:
	"""True once the daemon answers; False after START_TIMEOUT or once `process` exits."""
	deadline = time.monotonic() + START_TIMEOUT
	while time.monotonic() < deadline and (process is None or process.poll() is None):
		if healthy():
			return True
		time.sleep(0.2)
	return False


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
	sites = ", ".join(flow_sites()) or "none"
	return f"flow server {state} · sites: {sites}"


def flow_sites() -> list[str]:
	"""Sites on this bench with a flow server secret."""
	sites = []
	for config in sorted(_sites_dir().glob("*/site_config.json")):
		try:
			if json.loads(config.read_text(encoding="utf-8")).get("flow_server_secret"):
				sites.append(config.parent.name)
		except (OSError, ValueError):
			continue
	return sites


def healthy() -> bool:
	try:
		with DaemonClient(str(socket_path())) as client:
			client.healthz()
	except DaemonError:
		return False
	return True


# --- helpers and paths --------------------------------------------------


def supervised() -> bool:
	"""Deployment ownership is bench-wide, independent of whether the daemon is alive."""
	manager = frappe.get_common_site_config().get("flow_server_manager", "local")
	if manager not in ("local", "supervisor"):
		raise RuntimeError("flow_server_manager must be local or supervisor in common_site_config.json")
	return manager == "supervisor"


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
		[str(_flow_bin()), "extension-tools", *(str(folder) for folder in folders)],
		capture_output=True,
		text=True,
	)
	if proc.stderr.strip():
		click.secho(proc.stderr.strip(), fg="yellow")
	if proc.returncode != 0:
		raise RuntimeError("flow extension-tools failed; see the messages above")
	return json.loads(proc.stdout)["tools"]


def _extension_folders() -> list[Path]:
	"""Every site's extensions folder that exists."""
	return sorted(path for path in _sites_dir().glob(f"*/private/flow/{EXTENSIONS_DIR}") if path.is_dir())


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


def _sites_dir() -> Path:
	return Path(get_bench_path(), "sites").resolve()


def _flow_bin() -> Path:
	"""The harness CLI, installed next to this interpreter in the bench env."""
	return Path(sys.executable).parent / "flow"


def state_dir() -> Path:
	return Path(get_bench_path()) / "sites" / "flow-server"


def runtime_dir() -> Path:
	return Path(get_bench_path()) / "flow-server"
