# The install-time prefix guard.
#
# #42067 put this in `before_app_install` rather than `before_install`: a raise here
# leaves the site byte-identical, while `before_install`'s refusal path exits 0 and
# reports success. It fires 27 lines after `installer.py` has already refused any app
# missing from `apps.txt`, so it is lag-free by construction (#42105).
#
# Since the /apps redraw the surface is app-vs-app and nothing else. Legacy
# `website_route_rules`, `www/` files and the reserved-segment enumeration are no
# longer part of the check, because apps no longer claim top-level segments.

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

	# `get_installed_apps`, NOT `get_active_apps` — and this is deliberately the opposite
	# of what `build_prefix_registry` reads. A *disabled* app must stop serving its
	# prefix, so the registry skips it; but it can be re-enabled at any time, so its
	# claim must still block a new app from taking the prefix. Checking active apps only
	# would let disable-A / install-B / re-enable-A end with two claimants, which the
	# registry resolves by silently letting one win.
	#
	# `_ensure_on_bench=True` is kept for the reason it exists: an app left in
	# `installed_apps` but no longer on the bench would raise from `get_hooks(app_name=)`
	# in `declared_prefix` below, turning one missing directory into a failed install.
	for installed in frappe.get_installed_apps(_ensure_on_bench=True):
		if installed == app_name:
			continue
		if declared_prefix(installed) != prefix:
			continue

		# Name both claimants. The whole point of failing hard is that the operator
		# can act on the message without going and reading two hooks.py files.
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
