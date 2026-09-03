# The v2 boot — a small payload of core plus the declaring app, not `frappe.sessions.get()`.

import frappe
from frappe import _
from frappe.translate import get_translation_version
from frappe.utils import get_system_timezone, orjson_dumps

from . import SHELL_ROOT
from .doctypes import metadata_version
from .navigation import resolve_navigation
from .permissions import has_app_permission
from .registry import get_prefix_registry, prefix_map, shell_base, split_shell_path

# Bytes one top-level boot key may reach before boot logs it.
KEY_BUDGET = 100_000

# One row per key per prefix per day; never keyed on the user.
_BUDGET_LOG_TTL = 24 * 60 * 60

# Fixed, so the rows group in the Error Log list.
BUDGET_LOG_TITLE = "Boot key over budget"


def core_boot() -> dict:
	"""The keys every prefix gets, regardless of which app it belongs to."""
	user = frappe.get_cached_doc("User", frappe.session.user)
	return {
		"frappe_version": frappe.__version__,
		"site_name": frappe.local.site,
		"socketio_port": frappe.conf.socketio_port,
		"read_only_mode": frappe.flags.read_only,
		"csrf_token": frappe.sessions.get_csrf_token(),
		"setup_complete": bool(frappe.is_setup_complete()),
		"sysdefaults": frappe.defaults.get_defaults(),
		"timezone": get_system_timezone(),
		"user": {
			"name": user.name,
			"full_name": user.full_name,
			"user_image": user.user_image,
		},
		"lang": frappe.local.lang or "en",
		# Fetched separately and keyed on this, so translations stay cacheable for a year.
		"translations_version": get_translation_version(),
		# Active, not installed, so a disabled app is neither ordered nor served. Not named
		# `installed_apps`: client-side that is a permission-filtered list.
		"app_order": frappe.get_active_apps(_ensure_on_bench=True),
		# The address table is fetched, not booted; this is the key that invalidates it.
		"metadata_version": metadata_version(),
		# Every active app, so a link to a foreign app's doctype knows that app's shape.
		"prefixes": prefix_map(),
	}


def app_boot(app: str) -> dict:
	"""The declaring app's contribution, merged under core; a contributor that raises is dropped."""
	handler = frappe.get_hooks("app_boot", app_name=app)
	if not handler:
		return {}

	try:
		return frappe.get_attr(handler[0])() or {}
	except Exception:
		frappe.log_error(title=f"app_boot failed for {app}")
		return {}


def index_boot() -> dict:
	"""Boot for `/apps` itself, the index, which belongs to no app; the app list lives only here."""
	# `@frappe.whitelist()` only excludes Guest; a Website User must not read core boot.
	if not has_app_permission("frappe"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	registry = get_prefix_registry()
	apps = []

	for prefix, app in registry.items():
		if not has_app_permission(app):
			# A tile that 403s on click is worse than one that is absent.
			continue

		# `add_to_apps_screen` is read for presentation only, never membership.
		screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [{}])[0]
		apps.append(
			{
				"app": app,
				"prefix": prefix,
				"title": screen.get("title") or app.replace("_", " ").title(),
				"logo": screen.get("logo"),
				"route": shell_base(prefix),
			}
		)

	order = frappe.get_active_apps(_ensure_on_bench=True)
	apps.sort(key=lambda entry: order.index(entry["app"]) if entry["app"] in order else len(order))

	return {**core_boot(), "shell_base": f"/{SHELL_ROOT}", "app": None, "apps": apps}


def report_oversized_keys(boot: dict, prefix: str | None) -> None:
	"""Weigh every top-level boot key and log the ones past `KEY_BUDGET`, shipping it whole."""
	try:
		# `orjson_dumps` serialises the response, so these are the bytes on the wire.
		sizes = {key: len(orjson_dumps(value, default=str, decode=False)) for key, value in boot.items()}
		total = sum(sizes.values())

		for key, size in sorted(sizes.items()):
			if size <= KEY_BUDGET:
				continue

			# An atomic `SET NX`, so two workers claim the day's row once between them; `make_key`
			# applies the site prefix `set_value` would.
			claim = frappe.cache.make_key(f"boot_budget:{key}:{prefix or SHELL_ROOT}")
			# nosemgrep: frappe-cache-breaks-multitenancy
			if not frappe.cache.set(name=claim, value=1, ex=_BUDGET_LOG_TTL, nx=True):
				continue

			where = f"prefix {prefix}" if prefix else f"the /{SHELL_ROOT} index"
			# Deferred because boot is a GET, which is rolled back; Postgres would discard the row.
			frappe.log_error(
				title=BUDGET_LOG_TITLE,
				message=(
					f"{key} is {size:,} B for {frappe.session.user} at {where}, "
					f"over the {KEY_BUDGET:,} B key budget; boot total {total:,} B."
				),
				defer_insert=True,
			)
	except Exception:
		# A size check that can blank the shell is worse than none.
		pass


@frappe.whitelist()
def get_boot(path: str | None = None) -> dict:
	"""Boot for the prefix this request arrived at; the path is the client's only input."""
	# frappe accepts JSON bodies, so a list or dict can arrive here and reach `.strip()`.
	if not isinstance(path, str):
		path = None
	path = path or (frappe.local.request.path if frappe.local.request else "")
	split = split_shell_path(path)
	prefix = split[0] if split else None

	if not prefix:
		boot = index_boot()
	else:
		app = get_prefix_registry().get(prefix)
		if not app:
			frappe.throw(
				_("No app is installed at {0}").format(f"/{SHELL_ROOT}/{prefix}"), frappe.DoesNotExistError
			)

		# The document gate is a courtesy; a whitelisted endpoint is callable whatever the page did.
		if not has_app_permission(app):
			frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

		# Core LAST, so a contributed key cannot overwrite `csrf_token`, `user` or `shell_base`.
		boot = {
			**app_boot(app),
			**core_boot(),
			"shell_base": shell_base(prefix),
			"app": app,
			# A framework key, not an `app_boot` contribution: apps shape navigation through the rows
			# they ship. It rides boot because boot is already a blocking pre-mount fetch.
			"navigation": resolve_navigation(app),
		}

	# One exit, so the index payload is weighed on the same call site as a prefix's.
	report_oversized_keys(boot, prefix)

	return boot
