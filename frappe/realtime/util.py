# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Small helpers for the realtime connect path: header reads, hostnames, URLs,
and site resolution. Kept separate so auth.py stays focused on the pipeline."""

from urllib.parse import urlsplit

from frappe.realtime.config import RealtimeConfig


def read_header(environ: dict, name: str) -> str | None:
	"""Read an HTTP header from a WSGI environ (HTTP_FOO style)."""
	return environ.get("HTTP_" + name.upper().replace("-", "_"))


def get_hostname(url: str | None) -> str | None:
	"""hostname without scheme or port. Port of node_utils get_hostname."""
	if not url:
		return None
	if "://" in url:
		url = url.split("/")[2]
	return url.split(":")[0] if ":" in url else url


def resolve_site_name(environ: dict, config: RealtimeConfig) -> str | None:
	"""Resolve the site name. Port of authenticate.js get_site_name (order preserved)."""
	site_header = read_header(environ, "X-Frappe-Site-Name")
	host = read_header(environ, "Host")
	origin = read_header(environ, "Origin")

	if site_header:
		return get_hostname(site_header)
	if config.default_site and get_hostname(host) in ("localhost", "127.0.0.1"):
		return config.default_site
	if origin:
		return get_hostname(origin)
	return get_hostname(host)


def get_url(origin: str | None, path: str, config: RealtimeConfig) -> str:
	"""Build the web-process URL for a request. Port of realtime/utils.js get_url."""
	if config.webserver_host and config.webserver_port:
		base = config.webserver_host
		if "://" not in base:
			base = f"http://{base}"
		parts = urlsplit(base)
		if parts.port is None:
			base = f"{parts.scheme}://{parts.netloc}:{config.webserver_port}"
		else:
			base = f"{parts.scheme}://{parts.netloc}"
		return base + (path or "")
	url = origin or ""
	if config.developer_mode and config.webserver_port:
		parts = url.split(":")
		protocol = parts[0] if len(parts) > 0 else ""
		host = parts[1] if len(parts) > 1 else ""
		url = f"{protocol}:{host}:{config.webserver_port}"
	return url + (path or "")
