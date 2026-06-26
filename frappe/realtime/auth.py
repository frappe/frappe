# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Literal, NoReturn

import redis
import requests
from socketio.exceptions import ConnectionRefusedError

from frappe.realtime.config import RealtimeConfig
from frappe.realtime.util import get_hostname, get_url, read_header, resolve_site_name

logger = logging.getLogger("frappe.realtime")

SOCKETIO_SECRET_KEY = "socketio_auth_secret"

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
WebRequest = Callable[..., dict]


@dataclass(frozen=True)
class Credentials:
	"""Client credential from the Socket.IO handshake."""

	sid: str | None = None
	authorization: str | None = None

	def headers(self) -> dict[str, str]:
		if self.authorization:
			return {"Authorization": self.authorization}
		if self.sid:
			return {"Cookie": f"sid={self.sid}"}
		return {}


@dataclass
class Session:
	"""Authenticated user session stored on the socket.

	Carries the identity plus an authenticated client toward the web process, so
	handlers (via Socket) can call back without rebuilding auth. ``data`` is a bag
	for transient per-socket state (e.g. presence tracking)."""

	site: str
	user: str
	user_type: str | None
	installed_apps: list[str]
	request: WebRequest  # authenticated client toward the web process
	data: dict = field(default_factory=dict)

	def get(self, path: str, params: dict | None = None) -> dict:
		return self.send_request(path, "GET", params=params)

	def post(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
		return self.send_request(path, "POST", params=params, body=body)

	def put(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
		return self.send_request(path, "PUT", params=params, body=body)

	def delete(self, path: str, params: dict | None = None) -> dict:
		return self.send_request(path, "DELETE", params=params)

	def send_request(
		self,
		path: str,
		method: HttpMethod = "GET",
		params: dict | None = None,
		body: dict | None = None,
	) -> dict:
		"""Authenticated request to the web process; returns the decoded JSON body.

		method: HTTP verb. params: query string. body: JSON body.
		Prefer get/post/put/delete for the common cases.
		"""
		return self.request(path, method=method, params=params, body=body)

	def has_permission(self, doctype: str, name: str | None = None, ptype: str = "read") -> bool:
		"""HTTP permission check against the web process (no DB in realtime)."""
		try:
			body = self.get(
				"/api/method/frappe.realtime.has_permission",
				params={"doctype": doctype, "name": name or "", "ptype": ptype},
			)
		except Exception:
			return False
		return bool(body.get("message"))


def authenticate(environ: dict, namespace: str, config: RealtimeConfig) -> Session:
	"""Authenticate a connection.

	Port of realtime/middlewares/authenticate.js. Auth is delegated to the web
	process over HTTP; the realtime process never resumes a session in-process.
	Runs the checks in order and refuses the connection as soon as one fails.
	"""
	site = _validate_site(environ, namespace, config)
	_validate_origin(environ)

	credentials = _read_credentials(environ)
	request = _make_request(environ, credentials, config, site)
	user_info = _get_user_info(request)

	return _make_session(site, user_info, request)


def _reject(reason: str, message: str) -> NoReturn:
	"""Log the reason and refuse the connection."""
	logger.info("connect reject: %s", reason)
	raise ConnectionRefusedError(message)


def _validate_site(environ: dict, namespace: str, config: RealtimeConfig) -> str:
	"""Resolve the site and require the client to connect to /{site}."""
	site = resolve_site_name(environ, config)
	if not site or namespace.lstrip("/") != site:
		_reject(f"namespace {namespace!r} != site {site!r}", "Invalid namespace")
	return site


def _validate_origin(environ: dict) -> None:
	"""Reject cross-site websocket hijacks."""
	host = read_header(environ, "Host")
	origin = read_header(environ, "Origin")
	if not host or not origin:
		_reject(f"missing host/origin header (host={host!r}, origin={origin!r})", "Invalid origin")
	if get_hostname(host) != get_hostname(origin):
		_reject(f"origin {origin!r} != host {host!r}", "Invalid origin")


def _read_credentials(environ: dict) -> Credentials:
	"""Read the client's sid cookie or Authorization header."""
	cookie_header = read_header(environ, "Cookie")
	authorization = read_header(environ, "Authorization")
	if not cookie_header and not authorization:
		_reject(
			"missing cookie and authorization header",
			"Missing cookie and authorization header. Either one needed.",
		)

	credentials = Credentials(sid=_read_sid(cookie_header), authorization=authorization)

	if not credentials.sid and not credentials.authorization:
		_reject(
			"no sid cookie or authorization header",
			"No authentication method used. Use cookie or authorization header.",
		)
	return credentials


def _read_sid(cookie_header: str | None) -> str | None:
	if not cookie_header:
		return None

	jar = SimpleCookie()
	jar.load(cookie_header)
	sid = jar.get("sid")
	return sid.value if sid else None


def _make_request(environ: dict, credentials: Credentials, config: RealtimeConfig, site: str) -> WebRequest:
	"""Build the authenticated request helper toward the web (socket.frappe_request port).

	Forwards the client's credential plus the shared socketio secret (get_user_info
	returns {} without it); returns the decoded JSON body, raises on non-2xx."""
	origin = read_header(environ, "Origin")
	secret = get_socketio_secret(config.redis_queue)

	def request(
		path: str,
		method: HttpMethod = "GET",
		params: dict | None = None,
		body: dict | None = None,
	) -> dict:
		headers = credentials.headers()
		# Carry the tenant so loopback requests route to the right site.
		headers["X-Frappe-Site-Name"] = site
		if secret:
			headers["X-Frappe-Socket-Secret"] = secret

		res = requests.request(
			method,
			get_url(origin, path, config),
			params=params or {},
			json=body,
			headers=headers,
			timeout=10,
		)
		res.raise_for_status()
		return res.json()

	return request


def _get_user_info(request: WebRequest) -> dict:
	"""Ask the web who the user is; reject on failure or an empty (unauthorized) result."""
	try:
		method = "/api/method/frappe.realtime.get_user_info"
		message = request(method).get("message") or {}
		# Non-Guest with empty installed_apps: retry once (matches Node).
		if message.get("user") and message.get("user") != "Guest" and not message.get("installed_apps"):
			message = request(method).get("message") or {}
	except Exception as e:
		_reject(f"auth failure ({e})", "Unauthorized")

	# get_user_info returns {} when the secret mismatches or the session is invalid.
	if not message.get("user"):
		_reject("unauthorized (empty get_user_info)", "Unauthorized")
	return message


def _make_session(site: str, user_info: dict, request: WebRequest) -> Session:
	return Session(
		site=site,
		user=user_info["user"],
		user_type=user_info.get("user_type"),
		installed_apps=user_info.get("installed_apps") or [],
		request=request,
	)


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
