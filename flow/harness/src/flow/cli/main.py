"""flow command line entry point."""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys

from flow import config
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

	p_serve = sub.add_parser("serve", help="run the daemon")
	p_serve.add_argument("--host", default=config.HOST)
	p_serve.add_argument("--port", type=int, default=config.PORT)
	p_serve.add_argument("--data-dir", default=config.DATA_DIR)
	p_serve.add_argument("--background", action="store_true", help="detach, print the address, and return")
	p_serve.add_argument(
		"--port-file",
		help="bind before serving and write the resolved port here (with --port 0: ephemeral port)",
	)
	p_serve.add_argument(
		"--parent-watch",
		action="store_true",
		help="exit when stdin reaches EOF (private-daemon watchdog)",
	)

	p_attach = sub.add_parser("attach", help="attach a TUI to a running daemon; starts nothing")
	p_attach.add_argument(
		"--url",
		default=f"http://{config.HOST}:{config.PORT}",
		help="daemon base URL (default: the configured host and port)",
	)
	p_attach.add_argument("--session", help="attach to this session id instead of creating a new one")

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


def _with_default_command(argv: list[str], commands: set[str]) -> list[str]:
	"""Bare `flow` (and `flow -c`) opens the TUI, so the common case needs no verb."""
	if argv and (argv[0] in commands or argv[0] in ("-h", "--help")):
		return argv
	return ["tui", *argv]


def _tui(args) -> None:
	"""Bare `flow`: private daemon on an ephemeral port, TUI attached, daemon dies on quit."""
	from flow.cli.daemon import spawn_private, teardown
	from flow_tui.app import run_app

	daemon = spawn_private(config.DATA_DIR)
	session_id: str | None = None
	try:
		if args.continue_:
			session_id = _latest_session_for_cwd(daemon, os.getcwd())
		session_id = run_app(
			daemon.base_url,
			token=daemon.token,
			model=config.DEFAULT_MODEL,
			session_id=session_id,
			fatal_check=lambda: _daemon_death_notice(daemon),
		)
	finally:
		teardown(daemon, session_id=session_id)


def _latest_session_for_cwd(daemon, cwd: str) -> str | None:
	"""`flow -c`: newest session whose cwd is this directory; None means start fresh."""
	import httpx

	with httpx.Client(
		base_url=daemon.base_url,
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
	if not _is_loopback(args.host) and not config.AUTH_TOKEN:
		raise AuthError(
			"Refusing to expose an unauthenticated daemon. Set FLOW_AUTH_TOKEN or bind to a loopback host."
		)
	if args.background:
		from flow.cli.daemon import spawn_background

		base_url = spawn_background(args.host, args.port, args.data_dir)
		print(f"{GREEN}flow daemon{RESET} on {base_url}  {DIM}(data: {args.data_dir}){RESET}")
		return

	import uvicorn

	from flow.server import create_app
	from flow.session.store import SessionStore

	sink = _redis_sink()
	app = create_app(
		SessionStore(args.data_dir, event_sink=sink),
		auth_token=config.AUTH_TOKEN,
	)
	if args.parent_watch:
		from flow.cli.daemon import watch_parent_stdin

		watch_parent_stdin()
	rinfo = f" · redis: {config.REDIS_URL}" if sink else ""
	ainfo = " · auth: bearer" if config.AUTH_TOKEN else ""

	def banner(port: int) -> None:
		print(
			f"{GREEN}flow daemon{RESET} on http://{args.host}:{port}  "
			f"{DIM}(data: {args.data_dir}{rinfo}{ainfo}){RESET}"
		)

	if args.port_file:
		from flow.cli.daemon import bind_and_publish

		sock = bind_and_publish(args.host, args.port, args.port_file)
		banner(sock.getsockname()[1])
		uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
	else:
		banner(args.port)
		uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


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

	run_app(args.url, token=config.AUTH_TOKEN, model=config.DEFAULT_MODEL, session_id=args.session)


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
