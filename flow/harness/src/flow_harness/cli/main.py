"""flow command line entry point."""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from typing import TypedDict

from flow_harness import __version__, config, settings
from flow_harness.cli.daemon import DaemonError
from flow_harness.model.auth import AuthError
from flow_harness.model.credentials import CredentialStore, CredentialStoreError

GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"


def main() -> None:
	parser = argparse.ArgumentParser(prog="flow")
	parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
	sub = parser.add_subparsers(dest="cmd")

	p_tui = sub.add_parser("tui", help="start a private daemon and open the TUI")
	p_tui.add_argument(
		"-c",
		"--continue",
		dest="continue_",
		action="store_true",
		help="continue the most recent session for this directory",
	)
	p_tui.add_argument(
		"--append-system-prompt",
		metavar="TEXT",
		help="append TEXT to the end of the system prompt of new sessions",
	)
	_add_extension_options(p_tui)

	p_serve = sub.add_parser("serve", help="run the daemon")
	p_serve.add_argument("--host", default=config.HOST)
	p_serve.add_argument("--port", type=int, default=config.PORT)
	p_serve.add_argument("--data-dir", default=config.DATA_DIR)
	p_serve.add_argument(
		"--profile",
		default=config.PROFILE,
		help='server policy preset: "local" (default, everything on) or "deployed" '
		"(no shell or file-mutating tools, daemon-mutating routes off)",
	)
	p_serve.add_argument("--background", action="store_true", help="detach, print the address, and return")
	p_serve.add_argument(
		"--uds",
		help="serve on a unix socket at this path instead of host/port",
	)
	p_serve.add_argument(
		"--parent-watch",
		action="store_true",
		help="exit when stdin reaches EOF (private-daemon watchdog)",
	)
	_add_extension_options(p_serve)

	p_web = sub.add_parser(
		"web", help="run the daemon and serve the web UI, opening a browser (the default command)"
	)
	p_web.add_argument("--host", default=config.HOST)
	p_web.add_argument("--port", type=int, default=config.PORT)
	p_web.add_argument("--data-dir", default=config.DATA_DIR)
	p_web.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
	p_web.add_argument(
		"--append-system-prompt",
		metavar="TEXT",
		help="append TEXT to the end of the system prompt of every session the UI creates",
	)
	_add_extension_options(p_web)

	p_attach = sub.add_parser("attach", help="attach a TUI to a running daemon; starts nothing")
	p_attach.add_argument(
		"--url",
		default=f"http://{config.HOST}:{config.PORT}",
		help="daemon base URL (default: the configured host and port)",
	)
	p_attach.add_argument("--session", help="attach to this session id instead of creating a new one")
	p_attach.add_argument(
		"--append-system-prompt",
		metavar="TEXT",
		help="append TEXT to the end of the system prompt of new sessions",
	)

	p_login = sub.add_parser("login", help="save an API key or sign in with OAuth")
	p_login.add_argument("provider", nargs="?")
	p_login.add_argument(
		"--manual",
		action="store_true",
		help="print the OAuth URL and accept a pasted callback URL",
	)

	sub.add_parser("providers", help="show provider authentication status")

	p_logout = sub.add_parser("logout", help="remove a saved provider credential")
	p_logout.add_argument("provider")
	p_tools = sub.add_parser("extension-tools", help="list the tools the given extensions register, as JSON")
	p_tools.add_argument("path", nargs="+", metavar="PATH", help="an extension file or directory")

	args = parser.parse_args(_with_default_command(sys.argv[1:], set(sub.choices)))
	try:
		if args.cmd == "tui":
			_tui(args)
		elif args.cmd == "serve":
			_serve(args)
		elif args.cmd == "web":
			_web(args)
		elif args.cmd == "attach":
			_attach(args)
		elif args.cmd == "login":
			_login(args)
		elif args.cmd == "providers":
			_providers()
		elif args.cmd == "logout":
			_logout(args)
		elif args.cmd == "extension-tools":
			_extension_tools(args)
	except (AuthError, CredentialStoreError, DaemonError) as e:
		print(f"flow: {e}", file=sys.stderr)
		raise SystemExit(1) from None
	except (KeyboardInterrupt, EOFError):
		# Ctrl-C or Ctrl-D at a prompt is a deliberate cancellation, not a crash.
		raise SystemExit(130) from None


def _add_extension_options(parser: argparse.ArgumentParser) -> None:
	parser.add_argument(
		"-e",
		"--extension",
		action="append",
		default=[],
		metavar="PATH",
		help="load an extension file or directory (repeatable)",
	)
	parser.add_argument(
		"--no-extensions",
		action="store_true",
		help="disable extensions from ~/.flow/extensions (explicit -e paths still load)",
	)


def _extension_tools(args) -> None:
	"""What `flow serve -e PATH...` would load, for a client that builds its allowlist and
	tool picker before the daemon starts: one row per tool, load problems on stderr."""
	import contextlib
	import json
	from pathlib import Path

	from flow_harness.extensions import ExtensionRuntime

	runtime = ExtensionRuntime()
	with contextlib.redirect_stdout(sys.stderr):  # an extension's own prints must not break the JSON
		runtime.load(global_dir=None, extra_paths=[Path(p) for p in args.path], include_global_dir=False)
	_report_extension_diagnostics(runtime)
	rows = [
		{
			"name": name,
			"description": tool.prompt_snippet or tool.description,
			"extension": runtime.tool_sources[name],
		}
		for name, tool in runtime.tools.items()
	]
	print(json.dumps({"tools": rows}))


def _report_extension_diagnostics(runtime) -> None:
	"""Extension load problems are non-fatal; stderr is the only place a CLI user sees them."""
	for diagnostic in runtime.diagnostics:
		location = diagnostic.path or diagnostic.extension
		suffix = f" ({location})" if location else ""
		print(f"flow: extension {diagnostic.severity}: {diagnostic.message}{suffix}", file=sys.stderr)


def _with_default_command(argv: list[str], commands: set[str]) -> list[str]:
	"""Bare `flow` opens the web UI, so the common case needs no verb."""
	if argv and (argv[0] in commands or argv[0] in ("-h", "--help", "--version")):
		return argv
	return ["web", *argv]


def _tui(args) -> None:
	"""Bare `flow`: private daemon on a unix socket, TUI attached, daemon dies on quit."""
	from flow_harness.cli.daemon import spawn_private, teardown
	from flow_tui.app import run_app

	daemon = spawn_private(
		config.DATA_DIR,
		extension_paths=args.extension,
		extensions_enabled=not args.no_extensions,
	)
	session_id: str | None = None
	try:
		if args.continue_:
			session_id = _latest_session_for_cwd(daemon, os.getcwd())
		session_id = run_app(
			uds=daemon.socket_path,
			token=daemon.token,
			model=settings.resolve_startup_model(),
			session_id=session_id,
			append_system_prompt=args.append_system_prompt,
			fatal_check=lambda: _daemon_death_notice(daemon),
		)
	finally:
		teardown(daemon, session_id=session_id)


def _latest_session_for_cwd(daemon, cwd: str) -> str | None:
	"""`flow tui -c`: newest session whose cwd is this directory; None means start fresh."""
	import httpx

	with httpx.Client(
		base_url=config.UDS_URL,
		transport=httpx.HTTPTransport(uds=daemon.socket_path),
		headers={"Authorization": f"Bearer {daemon.token}"},
		timeout=5.0,
	) as http:
		sessions = http.get("/sessions").raise_for_status().json()["sessions"]
	target = os.path.realpath(cwd)
	for info in sessions:  # newest activity first
		if os.path.realpath(info["cwd"]) == target:
			return info["session_id"]
	return None


def _daemon_death_notice(daemon) -> str | None:
	if daemon.process.poll() is None:
		return None
	return (
		f"flow daemon exited unexpectedly (code {daemon.process.returncode}). "
		f"Sessions are durable — run `flow tui -c` to continue. Log: {daemon.log_path}"
	)


def _serve(args) -> None:
	from flow_harness.server.policy import resolve_policy
	from flow_harness.server.tenants import load_tenants

	try:
		policy = resolve_policy(args.profile, callback_hosts=config.CALLBACK_HOSTS, overrides=config.POLICY)
	except ValueError as e:
		raise DaemonError(str(e)) from None
	auth_token = _resolve_auth_token()
	tenants = None
	if config.TENANTS:
		if auth_token:
			raise DaemonError("set either FLOW_AUTH_TOKEN(_FILE) or FLOW_TENANTS, not both")
		try:
			tenants = load_tenants(config.TENANTS)
		except ValueError as e:
			raise DaemonError(f"cannot load FLOW_TENANTS: {e}") from None
	if policy.require_auth and not auth_token and tenants is None:
		raise AuthError(
			f"the {policy.profile!r} profile requires auth: set FLOW_AUTH_TOKEN, "
			"FLOW_AUTH_TOKEN_FILE, or FLOW_TENANTS."
		)
	if not args.uds and not _is_loopback(args.host) and not auth_token and tenants is None:
		raise AuthError(
			"Refusing to expose an unauthenticated daemon. Set FLOW_AUTH_TOKEN or bind to a loopback host."
		)
	if args.background:
		from flow_harness.cli.daemon import spawn_background

		base_url = spawn_background(
			args.host,
			args.port,
			args.data_dir,
			extension_paths=args.extension,
			extensions_enabled=not args.no_extensions,
			profile=policy.profile,
		)
		print(f"{GREEN}flow daemon{RESET} on {base_url}  {DIM}(data: {args.data_dir}){RESET}")
		return

	_warm_litellm()

	from flow_harness.server import create_app
	from flow_harness.server.logs import setup_terminal_logging
	from flow_harness.session.store import SessionStore

	setup_terminal_logging()
	sink = _redis_sink()
	store = SessionStore(
		args.data_dir,
		event_sink=sink,
		extension_paths=args.extension,
		# deployed skips ~/.flow/extensions; explicit -e paths are an operator opt-in
		extensions_enabled=policy.extensions and not args.no_extensions,
		tool_allowlist=policy.tool_allowlist,
		callback_hosts=policy.callback_hosts,
	)
	_report_extension_diagnostics(store.extension_runtime)
	app = create_app(
		store,
		auth_token=auth_token,
		tenants=tenants,
		policy=policy,
		lifespan=sink.lifespan if sink else None,
	)
	if args.parent_watch:
		from flow_harness.cli.daemon import watch_parent_stdin

		watch_parent_stdin()
	rinfo = " · redis" if sink else ""
	ainfo = " · auth: per site" if tenants else (" · auth: bearer" if auth_token else "")
	pinfo = f" · profile: {policy.profile}" if policy.profile != "local" else ""

	def banner(address: str) -> None:
		print(
			f"{GREEN}flow daemon{RESET} on {address}  "
			f"{DIM}(data: {args.data_dir}{rinfo}{ainfo}{pinfo}){RESET}"
		)

	if args.uds:
		from flow_harness.cli.daemon import bind_unix

		sock = bind_unix(args.uds)
		banner(args.uds)
		_run_server(app, store, sockets=[sock])
	else:
		banner(f"http://{args.host}:{args.port}")
		_run_server(app, store, host=args.host, port=args.port)


def _web(args) -> None:
	"""Bare `flow` (or `flow web`): the daemon with the built web UI mounted same-origin (no CORS
	needed), plus a browser tab pointed at it."""
	auth_token = _resolve_auth_token()
	if not _is_loopback(args.host) and not auth_token:
		raise AuthError(
			"Refusing to expose an unauthenticated daemon. Set FLOW_AUTH_TOKEN or bind to a loopback host."
		)
	webui = _webui_dist()
	if webui is None:
		raise DaemonError(
			"web UI assets not found — build them first: cd ui && npm install && npm run build -w app"
		)
	_warm_litellm()

	import threading
	import webbrowser

	from flow_harness.server import create_app
	from flow_harness.server.logs import setup_terminal_logging
	from flow_harness.session.store import SessionStore

	setup_terminal_logging()
	sink = _redis_sink()
	store = SessionStore(
		args.data_dir,
		event_sink=sink,
		extension_paths=args.extension,
		extensions_enabled=not args.no_extensions,
	)
	_report_extension_diagnostics(store.extension_runtime)
	app = create_app(
		store,
		auth_token=auth_token,
		webui_dir=webui,
		system_append=args.append_system_prompt,
		lifespan=sink.lifespan if sink else None,
	)
	# 0.0.0.0 binds every interface but isn't itself browsable
	browse_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
	url = f"http://{browse_host}:{args.port}"
	print(f"{GREEN}flow web{RESET} on {url}  {DIM}(data: {args.data_dir}){RESET}")
	if not args.no_browser:
		timer = threading.Timer(0.8, webbrowser.open, [url])
		timer.daemon = True  # a Ctrl-C before it fires must not hold the process
		timer.start()
	_run_server(app, store, host=args.host, port=args.port, timeout_graceful_shutdown=1)


def _run_server(app, store, *, sockets=None, **options) -> None:
	"""uvicorn, with the event streams ended first on shutdown: they would otherwise
	hold the graceful wait open (forever without a timeout), so one Ctrl-C is enough."""
	import uvicorn

	class Server(uvicorn.Server):
		async def shutdown(self, sockets=None) -> None:
			store.closing.set()
			await super().shutdown(sockets)

	server = Server(uvicorn.Config(app, log_config=None, **options))
	server.run(sockets=sockets)
	if not server.started:
		raise DaemonError("the daemon could not start (see the error above)")


def _webui_dist() -> str | None:
	"""The built web UI shipped inside the package (ui/app builds into it)."""
	import flow_harness.server

	path = os.path.join(os.path.dirname(flow_harness.server.__file__), "webui")
	return path if os.path.isfile(os.path.join(path, "index.html")) else None


def _warm_litellm() -> None:
	"""Import litellm before serving so the first model call doesn't block the event loop."""
	# not in a thread: litellm 1.104+ breaks when another thread logs during its import
	try:
		import litellm

		# silence the "Provider List / Give Feedback" lines litellm prints on errors
		litellm.suppress_debug_info = True
	except Exception:
		pass  # the request path imports it again and reports the real error


def _is_loopback(host: str) -> bool:
	if host.lower() == "localhost":
		return True
	try:
		return ipaddress.ip_address(host).is_loopback
	except ValueError:
		return False


def _attach(args) -> None:
	# lazy: the server package must run without textual installed
	from flow_tui.app import run_app

	run_app(
		args.url,
		token=_resolve_auth_token(),
		model=settings.resolve_startup_model(),
		session_id=args.session,
		append_system_prompt=args.append_system_prompt,
	)


def _resolve_auth_token() -> str | None:
	"""The daemon bearer: FLOW_AUTH_TOKEN, else the contents of FLOW_AUTH_TOKEN_FILE."""
	if config.AUTH_TOKEN:
		return config.AUTH_TOKEN
	if not config.AUTH_TOKEN_FILE:
		return None
	# a broken file must fail loudly, not fall back to an unprotected daemon
	try:
		with open(config.AUTH_TOKEN_FILE, encoding="utf-8") as file:
			token = file.read().strip()
	except OSError as e:
		raise DaemonError(f"cannot read FLOW_AUTH_TOKEN_FILE: {e}") from None
	if not token:
		raise DaemonError(f"FLOW_AUTH_TOKEN_FILE is empty: {config.AUTH_TOKEN_FILE}")
	return token


def _login(args) -> None:
	from flow_harness.cli.login import login

	login(CredentialStore(config.CREDENTIALS_PATH), args.provider, manual=args.manual)


def _providers() -> None:
	from flow_harness.cli.login import show_providers

	show_providers(CredentialStore(config.CREDENTIALS_PATH))


def _logout(args) -> None:
	from flow_harness.cli.login import logout

	logout(CredentialStore(config.CREDENTIALS_PATH), args.provider)


class _RedisQueueLimits(TypedDict, total=False):
	max_pending: int
	max_pending_per_site: int


def _redis_sink():
	"""Create the configured Redis event sink."""
	if not config.REDIS_URL:
		return None
	from flow_harness.server.redis_sink import RedisEventSink

	limits: _RedisQueueLimits = {}
	for name in ("max_pending", "max_pending_per_site"):
		setting = f"REDIS_{name.upper()}"
		raw = getattr(config, setting)
		if raw is None:
			continue
		try:
			value = int(raw)
		except ValueError:
			raise DaemonError(f"FLOW_{setting} must be a positive integer") from None
		if value < 1:
			raise DaemonError(f"FLOW_{setting} must be a positive integer")
		limits[name] = value
	try:
		return RedisEventSink(config.REDIS_URL, **limits)
	except ValueError:
		raise DaemonError("invalid FLOW_REDIS_URL") from None


if __name__ == "__main__":
	main()
