# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from http.cookies import SimpleCookie
from typing import Literal, NoReturn

import httpx
from redis import asyncio as aioredis
from socketio.exceptions import ConnectionRefusedError

from frappe.realtime.config import RealtimeConfig
from frappe.realtime.util import get_hostname, get_url, read_header, resolve_site_name

logger = logging.getLogger("frappe.realtime")

SOCKETIO_SECRET_KEY = "socketio_auth_secret"

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
WebRequest = Callable[..., Awaitable[dict]]


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
	for transient per-socket state (e.g. presence tracking).

	The calls are coroutines, so a permission check never occupies a worker
	thread. Plain handlers reach them without await, through SyncSocket."""

	site: str
	user: str
	user_type: str | None
	installed_apps: list[str]
	request: WebRequest  # authenticated client toward the web process
	data: dict = field(default_factory=dict)

	async def get(self, path: str, params: dict | None = None) -> dict:
		return await self.send_request(path, "GET", params=params)

	async def post(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
		return await self.send_request(path, "POST", params=params, body=body)

	async def put(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
		return await self.send_request(path, "PUT", params=params, body=body)

	async def delete(self, path: str, params: dict | None = None) -> dict:
		return await self.send_request(path, "DELETE", params=params)

	async def send_request(
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
		return await self.request(path, method=method, params=params, body=body)

	async def has_permission(self, doctype: str, name: str | None = None, ptype: str = "read") -> bool:
		"""HTTP permission check against the web process (no DB in realtime)."""
		try:
			body = await self.get(
				"/api/method/frappe.realtime.has_permission",
				params={"doctype": doctype, "name": name or "", "ptype": ptype},
			)
		except Exception:
			return False
		return bool(body.get("message"))


async def authenticate(environ: dict, namespace: str, config: RealtimeConfig) -> Session:
	"""Authenticate a connection. Port of realtime/middlewares/authenticate.js.

	Auth is delegated to the web process over HTTP (async here, so it never
	blocks the loop). Refuses the connection as soon as one check fails.
	"""
	site = _validate_site(environ, namespace, config)
	_validate_origin(environ)

	credentials = _read_credentials(environ)
	secret = await get_socketio_secret(config.redis_queue)
	request = _make_request(environ, credentials, config, site, secret)
	user_info = await _get_user_info(request)

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
	if not host:
		_reject("missing host header", "Invalid origin")
	if origin and get_hostname(host) != get_hostname(origin):
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


def _make_request(
	environ: dict, credentials: Credentials, config: RealtimeConfig, site: str, secret: str | None
) -> WebRequest:
	"""Build the authenticated request helper toward the web (socket.frappe_request port).

	Connect auth and every later permission check share this one coroutine, so
	their timeout / redirect / cookie handling cannot drift apart."""
	origin = read_header(environ, "Origin")

	headers = _auth_headers(credentials, site, secret)
	if config.embedded:
		return _make_local_request(headers | {"Origin": origin} if origin else headers)

	async def request(
		path: str,
		method: HttpMethod = "GET",
		params: dict | None = None,
		body: dict | None = None,
	) -> dict:
		res = await get_http_client().request(
			method,
			get_url(origin, path, config),
			params=params or {},
			json=body,
			headers=headers,
		)
		res.raise_for_status()
		return res.json()

	return request


def _get_local_client():
	"""One client for the whole process, built on first use.

	use_cookies=False leaves the client with no per-request state, so every
	connection and worker thread can share one — and a jar would otherwise
	overwrite our Cookie header and replay one user's sid onto the next connect."""
	global _local_client
	if _local_client is None:
		from werkzeug.test import Client

		from frappe.app import application

		_local_client = Client(application, use_cookies=False)
	return _local_client


def _make_local_request(headers: dict[str, str]) -> WebRequest:
	"""Same request, in this process. Embedded, loopback HTTP re-enters our own
	process, so a saturated WSGI pool would stall every connect behind it.

	Runs the real WSGI app, keeping session validation, permissions and the socket
	secret on the code path the HTTP transport uses."""
	client = _get_local_client()

	def call(path: str, method: HttpMethod, params: dict | None, body: dict | None) -> dict:
		# json=None is not the same as omitting it: werkzeug would send a "null" body.
		response = client.open(
			path,
			method=method,
			query_string=params or {},
			headers=headers,
			follow_redirects=True,
			**({"json": body} if body is not None else {}),
		)
		if response.status_code >= 400:
			raise ValueError(f"{method} {path} returned {response.status_code}")
		return json.loads(response.get_data(as_text=True) or "{}")

	async def request(
		path: str,
		method: HttpMethod = "GET",
		params: dict | None = None,
		body: dict | None = None,
	) -> dict:
		return await asyncio.to_thread(call, path, method, params, body)

	return request


def _auth_headers(credentials: Credentials, site: str, secret: str | None) -> dict[str, str]:
	"""Web-process request headers: client credential + tenant + shared secret."""
	headers = credentials.headers()
	# Carry the tenant so loopback requests route to the right site.
	headers["X-Frappe-Site-Name"] = site
	if secret:
		headers["X-Frappe-Socket-Secret"] = secret
	return headers


async def _get_user_info(request: WebRequest) -> dict:
	"""Ask the web who the user is; reject on failure or an empty result."""
	method = "/api/method/frappe.realtime.get_user_info"
	try:
		message = (await request(method)).get("message") or {}
		# Non-Guest with empty installed_apps: retry once (matches Node).
		if message.get("user") and message.get("user") != "Guest" and not message.get("installed_apps"):
			message = (await request(method)).get("message") or {}
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


_secret_client: aioredis.Redis | None = None
_http_client: httpx.AsyncClient | None = None
_local_client = None


async def get_socketio_secret(redis_url: str) -> str | None:
	"""Read socketio_auth_secret from the no-auth queue redis (same key the web sets)."""
	global _secret_client
	if _secret_client is None:
		_secret_client = aioredis.from_url(redis_url)
	value = await _secret_client.get(SOCKETIO_SECRET_KEY)
	if value is None:
		return None
	return value.decode() if isinstance(value, bytes) else value


class DiscardingCookieJar(CookieJar):
	"""Cookie jar that drops every Set-Cookie.

	The client is shared by every connection, so a real jar would replay one
	user's ``sid`` onto the next connect and authenticate it as that user."""

	def extract_cookies(self, response, request) -> None:
		pass


def get_http_client() -> httpx.AsyncClient:
	"""Shared process-wide AsyncClient (lazy init, one pool).

	Redirects are followed: httpx otherwise returns the 30x, which
	raise_for_status turns into a refused connect."""
	global _http_client
	if _http_client is None or _http_client.is_closed:
		_http_client = httpx.AsyncClient(timeout=10, follow_redirects=True, cookies=DiscardingCookieJar())
	return _http_client


async def close_clients() -> None:
	"""Release the shared HTTP and redis clients.

	Both are bound to the loop that created them, so a restart must rebuild them."""
	global _http_client, _secret_client
	if _http_client is not None:
		await _http_client.aclose()
		_http_client = None
	if _secret_client is not None:
		await _secret_client.aclose()
		_secret_client = None
