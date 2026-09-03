# The install-time prefix guard: refuse an app whose prefix is malformed or already claimed.
# Hooked on `before_app_install`, not `before_install`: a raise there exits 0 and reports success.

import frappe
from frappe import _

from . import SHELL_ROOT
from .registry import PREFIX_PATTERN, declared_prefix


class PrefixCollisionError(frappe.ValidationError):
	pass


def before_app_install(app_name: str):
	"""Refuse the install if `app_name`'s prefix is malformed or already claimed."""
	prefix = declared_prefix(app_name)

	if not PREFIX_PATTERN.match(prefix):
		frappe.throw(
			_(
				"App {0} declares the route prefix {1}, which is not a valid path segment. "
				"A prefix must start with a lowercase letter and contain only lowercase "
				"letters, digits, hyphens and underscores."
			).format(frappe.bold(app_name), frappe.bold(prefix)),
			exc=PrefixCollisionError,
			title=_("Invalid Route Prefix"),
		)

	# Installed apps, not active: a disabled app can be re-enabled, so its claim still blocks.
	# `_ensure_on_bench=True`: an app missing from the bench would raise from `get_hooks` below.
	for installed in frappe.get_installed_apps(_ensure_on_bench=True):
		if installed == app_name:
			continue
		if declared_prefix(installed) != prefix:
			continue

		frappe.throw(
			_(
				"App {0} claims the route prefix {1}, which is already claimed by the "
				"installed app {2}. Both would serve {3}. Set a different "
				"<code>app_prefix</code> in one of their hooks.py and try again."
			).format(
				frappe.bold(app_name),
				frappe.bold(prefix),
				frappe.bold(installed),
				frappe.bold(f"/{SHELL_ROOT}/{prefix}"),
			),
			exc=PrefixCollisionError,
			title=_("Route Prefix Already Claimed"),
		)
