"""
PROTOTYPE: connect-time authentication for the python-socketio server.

Direct port of realtime/middlewares/authenticate.js. Two important caveats:

1. The JS version makes an HTTP callback to Frappe for session/user info.
   The right Python equivalent is NOT `frappe.init/connect/destroy` per
   connect — that's blocking, cwd-dependent, and slow. The real impl needs
   either (a) a session-resolver subprocess we talk to via redis/UDS, or
   (b) running the auth path in a thread executor with a properly-bound
   site context, or (c) keeping the HTTP callback for now.

2. To unblock smoke-testing of the dynamic-namespace mechanism, this module
   honours FRAPPE_SOCKETIO_DEBUG_SKIP_AUTH=1 — when set, it accepts any
   connection as Guest with installed_apps=["frappe"].
"""

import os
from http.cookies import SimpleCookie
from urllib.parse import urlparse

from frappe.socketio_server import bench_conf


def _hostname(url_or_host: str | None) -> str | None:
	if not url_or_host:
		return None
	if "://" in url_or_host:
		url_or_host = urlparse(url_or_host).netloc
	return url_or_host.split(":")[0]


def _site_from_environ(environ: dict, conf: dict) -> str | None:
	explicit = environ.get("HTTP_X_FRAPPE_SITE_NAME")
	if explicit:
		return _hostname(explicit)

	host = _hostname(environ.get("HTTP_HOST"))
	if conf.get("default_site") and host in ("localhost", "127.0.0.1"):
		return conf["default_site"]

	return _hostname(environ.get("HTTP_ORIGIN")) or host


async def authenticate(environ: dict, namespace: str) -> tuple[bool, dict | str]:
	"""Returns (ok, ctx_or_error_message).

	ctx on success: {"site", "user", "user_type", "installed_apps"}
	"""
	conf = bench_conf()
	site = _site_from_environ(environ, conf)
	ns_site = namespace.lstrip("/")

	# DEV escape hatch: bypass session resolution to exercise dynamic-namespace
	# registration and event fan-out without a real cookie.
	if os.environ.get("FRAPPE_SOCKETIO_DEBUG_SKIP_AUTH") == "1":
		return True, {
			"site": ns_site or site or "debug",
			"user": "Guest",
			"user_type": "Guest",
			"installed_apps": ["frappe"],
		}

	if ns_site != site:
		return False, f"Invalid namespace: {ns_site!r} != site {site!r}"

	host = _hostname(environ.get("HTTP_HOST"))
	origin = _hostname(environ.get("HTTP_ORIGIN"))
	if host != origin:
		return False, "Invalid origin"

	cookie_header = environ.get("HTTP_COOKIE", "")
	auth_header = environ.get("HTTP_AUTHORIZATION")
	if not cookie_header and not auth_header:
		return False, "Missing cookie and authorization header"

	sid = None
	if cookie_header:
		jar = SimpleCookie()
		jar.load(cookie_header)
		sid = jar["sid"].value if "sid" in jar else None
	if not sid and not auth_header:
		return False, "No authentication method used"

	# Resolve session — placeholder. See module docstring.
	return await _resolve_session(site, sid, auth_header)


async def _resolve_session(site, sid, auth_header):
	"""TODO: real session resolution. Options:
	  a) HTTP callback (like the JS version)
	  b) thread-pool wrapper around frappe.sessions.Session(sid=...)
	  c) dedicated session-resolver daemon

	For now this is a stub so the smoke test fails clearly rather than
	silently letting Guest through.
	"""
	return False, "Session resolution not yet implemented (set FRAPPE_SOCKETIO_DEBUG_SKIP_AUTH=1)"
