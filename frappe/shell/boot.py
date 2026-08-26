# The v2 boot — a NEW small payload, deliberately not `frappe.sessions.get()`.
#
# #42070 measured the existing boot at 147,711 bytes, ~120 KB of it desk v1 workspace
# furniture (`workspace_sidebar_item` alone is 41,701). That is why CRM and Gameplan
# each rebuilt the generic keys by hand. v1's boot is left untouched and retires with
# v1; this one starts small and is composed of core plus the *declaring app* only.

import frappe
from frappe import _
from frappe.translate import get_translation_version
from frappe.utils import get_system_timezone

from . import SHELL_ROOT
from .doctypes import slugs_for_app
from .permissions import has_app_permission
from .registry import get_prefix_registry, shell_base, split_shell_path


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
		# Translations are fetched separately and keyed on this, so they stay cacheable
		# — `get_boot_translations` carries `@http_cache(max_age=31536000)`, a full
		# year, which only works because the version busts it. Merging them into boot
		# would forfeit that, and that is exactly the regression CRM shipped while desk
		# v1 never had it (#42070).
		"translations_version": get_translation_version(),
		# #42113: a plain ordered array, and deliberately `app_order` rather than
		# `installed_apps` — that name is already taken client-side for a
		# permission-filtered list, and only *ordering* fails silently.
		# Active, not merely installed: a disabled app must not be ordered, listed or
		# served. `_ensure_on_bench` also drops an app that is in `installed_apps` but
		# no longer on the bench — reading its hooks would raise, and every request
		# under /apps would 500 with it.
		"app_order": frappe.get_active_apps(_ensure_on_bench=True),
	}


def app_boot(app: str) -> dict:
	"""The declaring app's contribution, merged under core.

	A contributor that raises is caught, logged and dropped. Losing an app's boot keys
	degrades its pages; letting the exception out would blank the shell for a bug in
	one app (#42070).
	"""
	handler = frappe.get_hooks("app_boot", app_name=app)
	if not handler:
		return {}

	try:
		return frappe.get_attr(handler[0])() or {}
	except Exception:
		frappe.log_error(title=f"app_boot failed for {app}")
		return {}


def index_boot() -> dict:
	"""Boot for `/apps` itself — the index, which belongs to no app (#42124).

	The app list lives here and *only* here. Putting it in core boot would be
	furniture for pages that never render it, which is the mistake that made v1's
	boot 147 KB.
	"""
	# The index is a document like any other and needs the same front door. Without
	# this, any Website User could call the endpoint directly and read core boot —
	# site defaults, the installed-app list — which desk v1 never exposed below System
	# User. `@frappe.whitelist()` only excludes Guest.
	if not has_app_permission("frappe"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	registry = get_prefix_registry()
	apps = []

	for prefix, app in registry.items():
		if not has_app_permission(app):
			# Called once per app because a tile that 403s on click is worse than a
			# tile that is simply absent.
			continue

		# `add_to_apps_screen` is read for presentation only. #42124 demoted it from a
		# membership hook precisely so an app appears here without editing hooks.py.
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


@frappe.whitelist()
def get_boot(path: str | None = None) -> dict:
	"""Boot for the prefix this request arrived at.

	Composition is prefix-dependent, so the client's path is the input. It is the only
	input the client has — the document carries no per-request content at all (#42072).
	"""
	# Annotated `str | None`, but frappe accepts JSON bodies, so a list or dict can
	# arrive here and reach `.strip()`. Validate the type at the trust boundary.
	if not isinstance(path, str):
		path = None
	path = path or (frappe.local.request.path if frappe.local.request else "")
	split = split_shell_path(path)

	if not split:
		return index_boot()

	prefix, _rest = split
	app = get_prefix_registry().get(prefix)
	if not app:
		frappe.throw(
			_("No app is installed at {0}").format(f"/{SHELL_ROOT}/{prefix}"), frappe.DoesNotExistError
		)

	# The document gate is a courtesy; this re-check is the mandatory one, because a
	# whitelisted endpoint is directly callable whatever the page did (#42112).
	if not has_app_permission(app):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	# Core LAST, so a contributed key cannot overwrite `csrf_token`, `user` or
	# `shell_base`. "Merged under core" is what #42070 decided and what `app_boot`'s
	# docstring says; spreading it last would have made an app able to break every save
	# at its own prefix with a bare 400, by accident.
	return {
		**app_boot(app),
		**core_boot(),
		"shell_base": shell_base(prefix),
		"app": app,
		# Prefix-scoped, so the router can de-slug without a round trip. #42068 put
		# this table in the build; it cannot live there, because `bench build` runs
		# with no site (#42105) and a site's doctypes include its custom ones. Boot is
		# the nearest tier that knows them, and the property that mattered —
		# permission-independence — is unaffected. See the amendment on #42073.
		"doctype_slugs": slugs_for_app(app),
	}
