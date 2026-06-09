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
import datetime
import io
import json
import pickle
import time
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

import redis
import requests

from frappe.socketio_server import bench_conf, find_bench_root, redis_url

SOCKETIO_SECRET_KEY = "socketio_auth_secret"
CALLBACK_TIMEOUT = 10

# Session fast path: sessions whose remaining validity is smaller than this
# slack fall back to the HTTP callback instead of being judged locally.
# frappe.utils.now() writes last_updated in the *site's* timezone (a DB
# setting this server can't read), so local freshness math can be off by up
# to the largest possible tz offset — only trust it when the session would
# be fresh under any timezone interpretation.
TZ_SLACK_SECONDS = 26 * 3600
INSTALLED_APPS_TTL = 600

_site_db_names: dict[str, str | None] = {}
_installed_apps_cache: dict[str, tuple[list[str], float]] = {}


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


# --- Session fast path --------------------------------------------------------
# Resolve sid cookies straight from the redis session cache (the same hash
# frappe.sessions.Session writes), skipping the HTTP callback. Strictly
# conservative: any miss, parse failure, staleness ambiguity, or unknown
# installed_apps falls back to the canonical HTTP path.


class _session_dict(dict):
	"""Stand-in for frappe._dict when unpickling session data — a plain dict
	subclass so pickle's BUILD opcode (which sets instance state) works."""


class _SessionUnpickler(pickle.Unpickler):
	"""Unpickle frappe's cached session without importing the framework, and
	refuse to construct anything beyond the types session data contains."""

	def find_class(self, module, name):
		if module in ("frappe", "frappe.types.frappedict") and name == "_dict":
			return _session_dict
		if module == "datetime" and name in ("datetime", "date", "time", "timedelta"):
			return getattr(datetime, name)
		raise pickle.UnpicklingError(f"refusing to unpickle {module}.{name} from session cache")


def _site_db_name(site: str) -> str | None:
	"""Sessions are cached under "{db_name}|session" — db_name comes from the
	site's site_config.json (filesystem only, never changes for a site)."""
	if site not in _site_db_names:
		db_name = None
		config_path = find_bench_root() / "sites" / site / "site_config.json"
		try:
			db_name = json.loads(config_path.read_text()).get("db_name")
		except (OSError, json.JSONDecodeError):
			pass
		_site_db_names[site] = db_name
	return _site_db_names[site]


def _session_comfortably_fresh(session_data: dict) -> bool:
	"""Would this session be unexpired under ANY timezone interpretation of
	last_updated? Mirrors Session.get_session_data_from_cache validation,
	minus the site-timezone knowledge we don't have (see TZ_SLACK_SECONDS)."""
	if session_data.get("session_end"):
		# bounded sessions are rare — let the web server judge them
		return False
	last_updated = session_data.get("last_updated")
	expiry = session_data.get("session_expiry")
	if not last_updated or not expiry:
		return False
	try:
		last = datetime.datetime.fromisoformat(str(last_updated))
		parts = [int(p) for p in str(expiry).split(":")]
		expiry_seconds = parts[0] * 3600 + parts[1] * 60 + (parts[2] if len(parts) > 2 else 0)
	except ValueError:
		return False
	age = (datetime.datetime.now() - last).total_seconds()
	return age + TZ_SLACK_SECONDS < expiry_seconds


def _cached_installed_apps(site: str) -> list[str] | None:
	entry = _installed_apps_cache.get(site)
	if entry and time.monotonic() - entry[1] < INSTALLED_APPS_TTL:
		return entry[0]
	return None


def _remember_installed_apps(site: str, apps: list[str]):
	_installed_apps_cache[site] = (apps, time.monotonic())


def _resolve_session_fast(site: str, sid: str) -> dict | None:
	"""sid → user info straight from the redis session cache. Returns the
	get_user_info shape, or None to fall back to the HTTP callback.

	installed_apps lives only in the site DB, so the fast path requires a
	cached value from an earlier HTTP callback — the first connect per site
	(per process) always goes over HTTP and primes it.
	"""
	apps = _cached_installed_apps(site)
	if apps is None:
		return None
	db_name = _site_db_name(site)
	if not db_name:
		return None

	conf = bench_conf()
	client = redis.Redis.from_url(conf.get("redis_cache") or "redis://127.0.0.1:13000")
	try:
		raw = client.hget(f"{db_name}|session", sid)
	except redis.RedisError:
		return None
	finally:
		client.close()
	if not raw:
		return None

	try:
		data = _SessionUnpickler(io.BytesIO(raw)).load()
	except Exception:
		return None

	session_data = data.get("data") or {}
	if not _session_comfortably_fresh(session_data):
		return None
	user, user_type = session_data.get("user"), session_data.get("user_type")
	if not user or not user_type:
		return None
	return {"user": user, "user_type": user_type, "installed_apps": apps}


# --- HTTP callback path ---------------------------------------------------------
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
	user_info = None
	if sid:
		user_info = await asyncio.to_thread(_resolve_session_fast, site, sid)
	if user_info is None:
		user_info = await _get_user_info(base_url, sid, authorization_header)
		if user_info.get("user"):
			_remember_installed_apps(site, user_info.get("installed_apps") or [])
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
