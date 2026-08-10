# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Where a link item's URL leads, and so whether it should open in a new tab."""

from urllib.parse import urlparse


def default_new_tab(url: str, site_url: str) -> int:
	"""Whether `url` opens in a new tab when nobody said."""
	origin = origin_of(url)
	return 1 if origin and origin != origin_of(site_url) else 0


def origin_of(url: str) -> str:
	"""A URL's scheme and host, or `""` when it names neither."""
	parsed = urlparse(url or "")
	if not parsed.scheme or not parsed.netloc:
		return ""
	return f"{parsed.scheme}://{parsed.netloc}"
