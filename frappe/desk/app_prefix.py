# APP PREFIX — the one path segment an app is addressed by: `desk`, or `whatsapp` for `frappe_whatsapp`.

import re

import frappe

#: One bare path segment; the value reaches a URL and a directory name.
PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def default_prefix(app: str) -> str:
	"""The prefix an app gets when it declares nothing: `frappe_whatsapp` becomes `whatsapp`."""
	prefix = app.removeprefix("frappe_")
	# An app named exactly `frappe_` would strip to the empty prefix, which would swallow all of /apps.
	return prefix or app


def declared_prefix(app: str) -> str:
	"""This app's prefix, declared or derived."""
	# `app_name=` is a plain importlib read: it works before install and with no site.
	declared = frappe.get_hooks("app_prefix", app_name=app)
	# A scalar hook comes back as a one-element list.
	return declared[0] if declared else default_prefix(app)
