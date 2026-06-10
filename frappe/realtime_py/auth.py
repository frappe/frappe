# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Connect-time authentication.

Port of realtime/middlewares/authenticate.js. Auth is delegated to the web
process over HTTP: the realtime process never resumes a session in-process.

On connect, ALL of the following must pass or the connection is refused:

1. resolve site name (see resolve_site_name)
2. namespace must equal the resolved site name
3. hostname(Host) must equal hostname(Origin)  (cross-site websocket-hijack defense)
4. a sid cookie OR an Authorization header must be present
5. GET frappe.realtime.get_user_info with the X-Frappe-Socket-Secret returns a user

The returned session dict carries the authenticated identity plus a bound
frappe_request helper used later by Socket.has_permission.
"""

import logging
from http.cookies import SimpleCookie

import redis
import requests
from socketio.exceptions import ConnectionRefusedError

logger = logging.getLogger("frappe.realtime")

SOCKETIO_SECRET_KEY = "socketio_auth_secret"

_secret_client = None


def get_socketio_secret(redis_url: str) -> str | None:
	"""Read socketio_auth_secret from the no-auth queue redis (same key the web sets)."""
	global _secret_client
	if _secret_client is None:
		_secret_client = redis.from_url(redis_url)
	value = _secret_client.get(SOCKETIO_SECRET_KEY)
	if value is None:
		return None
	return value.decode() if isinstance(value, bytes) else value


def get_hostname(url: str | None) -> str | None:
	"""hostname without scheme or port. Port of node_utils get_hostname."""
	if not url:
		return None
	if "://" in url:
		url = url.split("/")[2]
	return url.split(":")[0] if ":" in url else url


def _header(environ: dict, name: str) -> str | None:
	"""Read an HTTP header from a WSGI environ (HTTP_FOO style)."""
	return environ.get("HTTP_" + name.upper().replace("-", "_"))


def resolve_site_name(environ: dict, config) -> str:
	"""Resolve the site name. Port of authenticate.js get_site_name (order preserved)."""
	site_header = _header(environ, "X-Frappe-Site-Name")
	host = _header(environ, "Host")
	origin = _header(environ, "Origin")

	if site_header:
		return get_hostname(site_header)
	if config.default_site and get_hostname(host) in ("localhost", "127.0.0.1"):
		return config.default_site
	if origin:
		return get_hostname(origin)
	return get_hostname(host)


def get_url(origin: str | None, path: str, config) -> str:
	"""Build the web-process URL for a request. Port of realtime/utils.js get_url."""
	url = origin or ""
	if config.developer_mode and config.webserver_port:
		parts = url.split(":")
		protocol = parts[0] if len(parts) > 0 else ""
		host = parts[1] if len(parts) > 1 else ""
		url = f"{protocol}:{host}:{config.webserver_port}"
	return url + (path or "")


def _build_frappe_request(environ: dict, sid: str | None, authorization: str | None, secret: str | None, config):
	"""Return an authenticated GET helper toward the web process.

	Mirrors the socket.frappe_request closure in authenticate.js. Returns the
	decoded JSON body as a dict; raises on transport / non-2xx errors."""
	origin = _header(environ, "Origin")

	def frappe_request(path: str, args: dict | None = None) -> dict:
		headers = {}
		if authorization:
			headers["Authorization"] = authorization
		elif sid:
			headers["Cookie"] = f"sid={sid}"
		if secret:
			headers["X-Frappe-Socket-Secret"] = secret

		res = requests.get(get_url(origin, path, config), params=args or {}, headers=headers, timeout=10)
		res.raise_for_status()
		return res.json()

	return frappe_request


def authenticate(environ: dict, namespace: str, config) -> dict:
	"""Authenticate a connection. Return the session dict or raise ConnectionRefusedError."""
	site = resolve_site_name(environ, config)

	if namespace.lstrip("/") != site:
		logger.info("connect reject: namespace %r != site %r", namespace, site)
		raise ConnectionRefusedError("Invalid namespace")

	host = _header(environ, "Host")
	origin = _header(environ, "Origin")
	if get_hostname(host) != get_hostname(origin):
		logger.info("connect reject: origin %r != host %r", origin, host)
		raise ConnectionRefusedError("Invalid origin")

	cookie_header = _header(environ, "Cookie")
	authorization = _header(environ, "Authorization")
	if not cookie_header and not authorization:
		logger.info("connect reject: missing cookie and authorization header")
		raise ConnectionRefusedError("Missing cookie and authorization header. Either one needed.")

	sid = None
	if cookie_header:
		jar = SimpleCookie()
		jar.load(cookie_header)
		sid = jar["sid"].value if "sid" in jar else None

	if not sid and not authorization:
		logger.info("connect reject: no sid cookie or authorization header")
		raise ConnectionRefusedError("No authentication method used. Use cookie or authorization header.")

	secret = get_socketio_secret(config.redis_queue)
	frappe_request = _build_frappe_request(environ, sid, authorization, secret, config)

	try:
		message = frappe_request("/api/method/frappe.realtime.get_user_info").get("message") or {}
		# Non-Guest with empty installed_apps: retry once (matches Node).
		if message.get("user") and message.get("user") != "Guest" and not message.get("installed_apps"):
			message = frappe_request("/api/method/frappe.realtime.get_user_info").get("message") or {}
	except Exception as e:
		logger.info("connect reject: auth failure (%s)", e)
		raise ConnectionRefusedError(f"Unauthorized: {e}")

	if not message.get("user"):
		# get_user_info returns {} when the secret mismatches or the session is invalid.
		logger.info("connect reject: unauthorized (empty get_user_info)")
		raise ConnectionRefusedError("Unauthorized")

	return {
		"site": site,
		"user": message["user"],
		"user_type": message.get("user_type"),
		"installed_apps": message.get("installed_apps") or [],
		"sid": sid,
		"_frappe_request": frappe_request,
	}
