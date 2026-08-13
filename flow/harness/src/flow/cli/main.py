"""flow command line entry point."""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys

from flow import config, settings
from flow.cli.daemon import DaemonError
from flow.model.auth import AuthError
from flow.model.credentials import CredentialStore, CredentialStoreError

GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"


def main() -> None:
	parser = argparse.ArgumentParser(prog="flow")
	sub = parser.add_subparsers(dest="cmd")

	p_tui = sub.add_parser("tui", help="start a private daemon and open the TUI (the default command)")
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

	p_web = sub.add_parser("web", help="run the daemon and serve the web UI, opening a browser")
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


def _with_default_command(argv: list[str], commands: set[str]) -> list[str]:
	"""Bare `flow` (and `flow -c`) opens the TUI, so the common case needs no verb."""
	if argv and (argv[0] in commands or argv[0] in ("-h", "--help")):
		return argv
	return ["tui", *argv]


def _tui(args) -> None:
	"""Bare `flow`: private daemon on a unix socket, TUI attached, daemon dies on quit."""
	from flow.cli.daemon import spawn_private, teardown
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
	"""`flow -c`: newest session whose cwd is this directory; None means start fresh."""
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
		f"Sessions are durable — run `flow -c` to continue. Log: {daemon.log_path}"
	)


def _serve(args) -> None:
	if not args.uds and not _is_loopback(args.host) and not config.AUTH_TOKEN:
		raise AuthError(
			"Refusing to expose an unauthenticated daemon. Set FLOW_AUTH_TOKEN or bind to a loopback host."
		)
	if args.background:
		from flow.cli.daemon import spawn_background

		base_url = spawn_background(
			args.host,
			args.port,
			args.data_dir,
			extension_paths=args.extension,
			extensions_enabled=not args.no_extensions,
		)
		print(f"{GREEN}flow daemon{RESET} on {base_url}  {DIM}(data: {args.data_dir}){RESET}")
		return

	_warm_litellm()

	import uvicorn

	from flow.server import create_app
	from flow.session.store import SessionStore

	sink = _redis_sink()
	app = create_app(
		SessionStore(
			args.data_dir,
			event_sink=sink,
			extension_paths=args.extension,
			extensions_enabled=not args.no_extensions,
		),
		auth_token=config.AUTH_TOKEN,
	)
	if args.parent_watch:
		from flow.cli.daemon import watch_parent_stdin

		watch_parent_stdin()
	rinfo = f" · redis: {config.REDIS_URL}" if sink else ""
	ainfo = " · auth: bearer" if config.AUTH_TOKEN else ""

	def banner(address: str) -> None:
		print(f"{GREEN}flow daemon{RESET} on {address}  {DIM}(data: {args.data_dir}{rinfo}{ainfo}){RESET}")

	if args.uds:
		from flow.cli.daemon import bind_unix

		sock = bind_unix(args.uds)
		banner(args.uds)
		uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
	else:
		banner(f"http://{args.host}:{args.port}")
		uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def _web(args) -> None:
	"""`flow web`: the daemon with the built web UI mounted same-origin (no CORS
	needed), plus a browser tab pointed at it."""
	if not _is_loopback(args.host) and not config.AUTH_TOKEN:
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

	import uvicorn

	from flow.server import create_app
	from flow.session.store import SessionStore

	sink = _redis_sink()
	app = create_app(
		SessionStore(
			args.data_dir,
			event_sink=sink,
			extension_paths=args.extension,
			extensions_enabled=not args.no_extensions,
		),
		auth_token=config.AUTH_TOKEN,
		webui_dir=webui,
		system_append=args.append_system_prompt,
	)
	# 0.0.0.0 binds every interface but isn't itself browsable
	browse_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
	url = f"http://{browse_host}:{args.port}"
	print(f"{GREEN}flow web{RESET} on {url}  {DIM}(data: {args.data_dir}){RESET}")
	if not args.no_browser:
		timer = threading.Timer(0.8, webbrowser.open, [url])
		timer.daemon = True  # a Ctrl-C before it fires must not hold the process
		timer.start()
	uvicorn.run(app, host=args.host, port=args.port, log_level="warning", timeout_graceful_shutdown=1)


def _webui_dist() -> str | None:
	"""The built web UI shipped inside the package (ui/app builds into it)."""
	import flow.server

	path = os.path.join(os.path.dirname(flow.server.__file__), "webui")
	return path if os.path.isfile(os.path.join(path, "index.html")) else None


def _warm_litellm() -> None:
	"""Import litellm off the event loop before it serves requests.

	The first model call imports litellm lazily, ~2 s of CPU that would block the
	event loop and hold back SSE delivery of the run's first events. Warming it in a
	thread overlaps the cost with server startup instead.
	"""
	import threading

	def _import() -> None:
		try:
			import litellm  # noqa: F401
		except Exception:
			pass  # the request path imports it again and reports the real error

	threading.Thread(target=_import, name="litellm-warmup", daemon=True).start()


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
		token=config.AUTH_TOKEN,
		model=settings.resolve_startup_model(),
		session_id=args.session,
		append_system_prompt=args.append_system_prompt,
	)


def _login(args) -> None:
	from flow.cli.login import login

	login(CredentialStore(config.CREDENTIALS_PATH), args.provider, manual=args.manual)


def _providers() -> None:
	from flow.cli.login import show_providers

	show_providers(CredentialStore(config.CREDENTIALS_PATH))


def _logout(args) -> None:
	from flow.cli.login import logout

	logout(CredentialStore(config.CREDENTIALS_PATH), args.provider)


def _redis_sink():
	"""Publish every event to Redis channel `harness:<sid>` (the wire contract shared with
	Flow's bridge, kept as `harness:`) so an external relay can fan out to browsers."""
	if not config.REDIS_URL:
		return None
	import json

	import redis

	client = redis.from_url(config.REDIS_URL)

	def sink(session_id: str, event: dict) -> None:
		client.publish(f"harness:{session_id}", json.dumps({"session_id": session_id, **event}))

	return sink


if __name__ == "__main__":
	main()
