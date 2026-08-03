"""flow command line entry point."""

from __future__ import annotations

import argparse
import ipaddress
import sys

from flow import config
from flow.model.auth import AuthError
from flow.model.credentials import CredentialStore, CredentialStoreError

GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"


def main() -> None:
	parser = argparse.ArgumentParser(prog="flow")
	sub = parser.add_subparsers(dest="cmd")

	p_serve = sub.add_parser("serve", help="run the daemon")
	p_serve.add_argument("--host", default=config.HOST)
	p_serve.add_argument("--port", type=int, default=config.PORT)
	p_serve.add_argument("--data-dir", default=config.DATA_DIR)

	p_attach = sub.add_parser("attach", help="attach a TUI to a running daemon")
	p_attach.add_argument("--url", required=True, help="daemon base URL, e.g. http://127.0.0.1:8787")

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
		if args.cmd == "serve":
			_serve(args)
		elif args.cmd == "attach":
			_attach(args)
		elif args.cmd == "login":
			_login(args)
		elif args.cmd == "providers":
			_providers()
		elif args.cmd == "logout":
			_logout(args)
	except (AuthError, CredentialStoreError) as e:
		print(f"flow: {e}", file=sys.stderr)
		raise SystemExit(1) from None
	except (KeyboardInterrupt, EOFError):
		# Ctrl-C or Ctrl-D at a prompt is a deliberate cancellation, not a crash.
		raise SystemExit(130) from None


def _with_default_command(argv: list[str], commands: set[str]) -> list[str]:
	"""`flow` and `flow --port 9000` mean `flow serve ...`, so the common case needs no verb."""
	if argv and (argv[0] in commands or argv[0] in ("-h", "--help")):
		return argv
	return ["serve", *argv]


def _serve(args) -> None:
	import uvicorn

	from flow.server import create_app
	from flow.session.store import SessionStore

	sink = _redis_sink()
	if not _is_loopback(args.host) and not config.AUTH_TOKEN:
		raise AuthError(
			"Refusing to expose an unauthenticated daemon. Set FLOW_AUTH_TOKEN or bind to a loopback host."
		)
	app = create_app(
		SessionStore(args.data_dir, event_sink=sink),
		auth_token=config.AUTH_TOKEN,
	)
	rinfo = f" · redis: {config.REDIS_URL}" if sink else ""
	ainfo = " · auth: bearer" if config.AUTH_TOKEN else ""
	print(
		f"{GREEN}flow daemon{RESET} on http://{args.host}:{args.port}  "
		f"{DIM}(data: {args.data_dir}{rinfo}{ainfo}){RESET}"
	)
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
	from flow_tui.app import attach

	attach(args.url, token=config.AUTH_TOKEN, model=config.DEFAULT_MODEL)


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
