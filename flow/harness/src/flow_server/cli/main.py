"""flow_server CLI. `flowd serve` runs the daemon. (The `chat` terminal client and
`login` for native-provider OAuth arrive in Phase 7.)"""

from __future__ import annotations

import argparse

from flow_server import config

GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"


def main() -> None:
	parser = argparse.ArgumentParser(prog="flowd")
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_serve = sub.add_parser("serve", help="run the daemon")
	p_serve.add_argument("--host", default=config.HOST)
	p_serve.add_argument("--port", type=int, default=config.PORT)
	p_serve.add_argument("--data-dir", default=config.DATA_DIR)

	args = parser.parse_args()
	if args.cmd == "serve":
		_serve(args)


def _serve(args) -> None:
	import uvicorn

	from flow_server.server import create_app
	from flow_server.session.store import SessionStore

	sink = _redis_sink()
	app = create_app(SessionStore(args.data_dir, event_sink=sink))
	rinfo = f" · redis: {config.REDIS_URL}" if sink else ""
	print(
		f"{GREEN}flow_server daemon{RESET} on http://{args.host}:{args.port}  "
		f"{DIM}(data: {args.data_dir}{rinfo}){RESET}"
	)
	uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


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
