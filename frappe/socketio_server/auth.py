"""Connect-time authentication for the python-socketio realtime server.

Port of realtime/middlewares/authenticate.js. Session resolution works the
same way as the Node implementation: an HTTP callback to the Frappe web
server (`frappe.realtime.get_user_info`), authenticated by forwarding the
client's `sid` cookie or Authorization header plus the shared
`socketio_auth_secret` that web workers store in redis_queue.

The callback is synchronous (requests) and runs in a worker thread via
asyncio.to_thread — one call per connect, same cost profile as the Node
implementation's fetch().
"""

import asyncio
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

import redis
import requests

from frappe.socketio_server import bench_conf, redis_url

SOCKETIO_SECRET_KEY = "socketio_auth_secret"
CALLBACK_TIMEOUT = 10


def _hostname(url_or_host: str | None) -> str | None:
	if not url_or_host:
		return None
	if "://" in url_or_host:
		url_or_host = urlsplit(url_or_host).netloc
	return url_or_host.split(":")[0]


def _site_from_environ(environ: dict, conf: dict) -> str | None:
	explicit = environ.get("HTTP_X_FRAPPE_SITE_NAME")
	if explicit:
		return _hostname(explicit)

	host = _hostname(environ.get("HTTP_HOST"))
	if conf.get("default_site") and host in ("localhost", "127.0.0.1"):
		return conf["default_site"]

	return _hostname(environ.get("HTTP_ORIGIN")) or host


def _base_url(environ: dict, conf: dict) -> str:
	"""URL of the Frappe web server to make auth callbacks against.

	Mirrors realtime/utils.js get_url: use the request origin; in
	developer_mode rewrite the port to webserver_port because the browser
	origin points at the dev asset server, not the gunicorn worker.
	"""
	origin = environ.get("HTTP_ORIGIN") or f"http://{environ.get('HTTP_HOST', 'localhost')}"
	if conf.get("developer_mode") and conf.get("webserver_port"):
		parts = urlsplit(origin)
		origin = f"{parts.scheme}://{parts.hostname}:{conf['webserver_port']}"
	return origin


def _get_socket_secret() -> str | None:
	"""The shared secret get_user_info requires — generated and stored in
	redis_queue by the web worker (frappe.realtime.get_socketio_secret)."""
	client = redis.Redis.from_url(redis_url())
	try:
		secret = client.get(SOCKETIO_SECRET_KEY)
	finally:
		client.close()
	return secret.decode() if secret else None


def _frappe_request(
	base_url: str,
	path: str,
	*,
	sid: str | None = None,
	authorization_header: str | None = None,
	params: dict | None = None,
) -> dict:
	"""Synchronous HTTP callback to the Frappe web server (run via
	asyncio.to_thread). Returns the decoded JSON body, or {} on any failure —
	callers treat a missing "message" key as denial."""
	headers = {"Accept": "application/json"}
	if authorization_header:
		headers["Authorization"] = authorization_header
	elif sid:
		headers["Cookie"] = f"sid={sid}"
	if secret := _get_socket_secret():
		headers["X-Frappe-Socket-Secret"] = secret
	try:
		response = requests.get(
			f"{base_url}{path}", params=params or {}, headers=headers, timeout=CALLBACK_TIMEOUT
		)
		if response.ok:
			return response.json()
	except (requests.RequestException, ValueError):
		pass
	return {}


async def authenticate(environ: dict, namespace: str) -> tuple[bool, dict | str]:
	"""Validate a connection attempt against the namespace's site.

	Returns (True, ctx) on success where ctx becomes the socket session:
	{"site", "user", "user_type", "installed_apps", "sid",
	 "authorization_header", "base_url", "open_docs"},
	or (False, error_message) on rejection.
	"""
	conf = bench_conf()
	site = _site_from_environ(environ, conf)
	ns_site = namespace.lstrip("/")

	if ns_site != site:
		return False, f"Invalid namespace {ns_site!r} for site {site!r}"

	host = _hostname(environ.get("HTTP_HOST"))
	origin = _hostname(environ.get("HTTP_ORIGIN"))
	if host != origin:
		return False, "Invalid origin"

	cookie_header = environ.get("HTTP_COOKIE", "")
	authorization_header = environ.get("HTTP_AUTHORIZATION")
	if not cookie_header and not authorization_header:
		return False, "Missing cookie and authorization header. Either one needed for authentication."

	sid = None
	if cookie_header:
		jar = SimpleCookie()
		jar.load(cookie_header)
		if "sid" in jar:
			sid = jar["sid"].value
	if not sid and not authorization_header:
		return False, "No authentication method used. Use cookie or authorization header."

	base_url = _base_url(environ, conf)
	user_info = await _get_user_info(base_url, sid, authorization_header)
	if not user_info.get("user"):
		return False, "Unauthorized: could not resolve session"

	return True, {
		"site": site,
		"user": user_info["user"],
		"user_type": user_info.get("user_type"),
		"installed_apps": user_info.get("installed_apps") or [],
		"sid": sid,
		"authorization_header": authorization_header,
		"base_url": base_url,
		"open_docs": [],
	}


async def _get_user_info(base_url: str, sid: str | None, authorization_header: str | None) -> dict:
	async def call() -> dict:
		response = await asyncio.to_thread(
			_frappe_request,
			base_url,
			"/api/method/frappe.realtime.get_user_info",
			sid=sid,
			authorization_header=authorization_header,
		)
		return response.get("message") or {}

	message = await call()
	# get_user_info returns {} until a web worker has generated the shared
	# secret (the first call itself generates it) — retry once, like the
	# Node implementation.
	if not message.get("installed_apps"):
		message = await call() or message
	return message


async def check_permission(ctx: dict, doctype: str, docname: str | None = None) -> bool:
	"""frappe.realtime.has_permission HTTP callback using the connection's
	stored credentials. Deny on any failure."""
	response = await asyncio.to_thread(
		_frappe_request,
		ctx["base_url"],
		"/api/method/frappe.realtime.has_permission",
		sid=ctx.get("sid"),
		authorization_header=ctx.get("authorization_header"),
		params={"doctype": doctype, "name": docname or ""},
	)
	return bool(response.get("message"))
