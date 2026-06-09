"""Connect-time authentication — port of realtime/middlewares/authenticate.js.

Sessions are resolved from the redis session cache when possible, falling
back to an HTTP callback to frappe.realtime.get_user_info (the Node way).
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

# last_updated is written in the site's timezone (a DB setting we can't
# read), so only trust sessions fresh under any timezone interpretation
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
	"""Web server URL for auth callbacks. In developer_mode the browser origin
	points at the dev asset server, so rewrite the port to webserver_port."""
	origin = environ.get("HTTP_ORIGIN") or f"http://{environ.get('HTTP_HOST', 'localhost')}"
	if conf.get("developer_mode") and conf.get("webserver_port"):
		parts = urlsplit(origin)
		origin = f"{parts.scheme}://{parts.hostname}:{conf['webserver_port']}"
	return origin


# --- Session fast path --------------------------------------------------------
# Read sid sessions straight from the redis session cache; anything uncertain
# falls back to the HTTP callback.


class _session_dict(dict):
	"""Stand-in for frappe._dict (a subclass, so pickle's BUILD opcode works)."""


class _SessionUnpickler(pickle.Unpickler):
	"""Only constructs dicts and datetime values — never arbitrary classes."""

	def find_class(self, module, name):
		if module in ("frappe", "frappe.types.frappedict") and name == "_dict":
			return _session_dict
		if module == "datetime" and name in ("datetime", "date", "time", "timedelta"):
			return getattr(datetime, name)
		raise pickle.UnpicklingError(f"refusing to unpickle {module}.{name} from session cache")


def _site_db_name(site: str) -> str | None:
	"""Sessions are cached under "{db_name}|session"; db_name never changes."""
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
	"""Unexpired under any timezone interpretation of last_updated?"""
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
	"""sid → user info from the redis session cache, or None to fall back."""
	# installed_apps lives only in the site DB — the first connect per site
	# goes over HTTP and primes it
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
	"""Shared secret that get_user_info requires; web workers store it in redis."""
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
	"""HTTP callback to the Frappe web server. Returns {} on any failure."""
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
	"""Validate a connection attempt. Returns (True, session ctx) or
	(False, error message)."""
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
	# the first call generates the shared secret — retry once, like Node
	if not message.get("installed_apps"):
		message = await call() or message
	return message


async def check_permission(ctx: dict, doctype: str, docname: str | None = None) -> bool:
	"""Check frappe.realtime.has_permission with the connection's credentials."""
	response = await asyncio.to_thread(
		_frappe_request,
		ctx["base_url"],
		"/api/method/frappe.realtime.has_permission",
		sid=ctx.get("sid"),
		authorization_header=ctx.get("authorization_header"),
		params={"doctype": doctype, "name": docname or ""},
	)
	return bool(response.get("message"))
