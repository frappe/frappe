# The v2 boot — a small payload of core plus the declaring app, not `frappe.sessions.get()`.

import frappe
from frappe import _
from frappe.boot import DEFAULT_APP_SEQUENCE_ID
from frappe.core.api.file import get_file_chunk_size, get_max_file_size
from frappe.core.doctype.installed_applications.installed_applications import (
	get_setup_wizard_completed_apps,
	get_setup_wizard_not_required_apps,
)
from frappe.integrations.frappe_providers.cloud_settings import is_cloud_settings_enabled
from frappe.sessions import get_session_info
from frappe.translate import get_translation_version
from frappe.utils import orjson_dumps

from . import SHELL_ROOT
from .doctypes import get_address_table, metadata_version
from .index_favourites import index_favourites
from .index_layer import arrange, write_layer
from .index_notices import index_notices
from .links import canonical_path
from .navigation import NO_HOST, resolve_navigation
from .permissions import has_app_permission
from .registry import get_prefix_registry, prefix_map, shell_base, split_shell_path
from .route_history import Visit, latest_visits
from .titles import app_screen, readable_titles

# Bytes one top-level boot key may reach before boot logs it.
KEY_BUDGET = 100_000

# One row per key per prefix per day; never keyed on the user.
_BUDGET_LOG_TTL = 24 * 60 * 60

# Fixed, so the rows group in the Error Log list.
BUDGET_LOG_TITLE = "Boot key over budget"

RECENT_LIMIT = 5

CLOUD_SETTINGS_ROUTE = "/desk?cloud_settings=1"


def core_boot() -> dict:
	"""The keys every prefix gets, regardless of which app it belongs to."""
	return {
		"frappe_version": frappe.__version__,
		"site_name": frappe.local.site,
		"socketio_port": frappe.conf.socketio_port,
		"dev_server": bool(frappe._dev_server),
		"read_only_mode": frappe.flags.read_only,
		"csrf_token": frappe.sessions.get_csrf_token(),
		"setup_complete": bool(frappe.is_setup_complete()),
		"session": get_session_info(),
		"max_file_size": get_max_file_size(),
		"file_chunk_size": get_file_chunk_size(),
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
	tiles = gated_index_tiles()
	return {
		**core_boot(),
		"shell_base": f"/{SHELL_ROOT}",
		"app": None,
		"apps": arrange(tiles),
		**index_favourites(),
		"recent": index_recent(),
		"more_apps": CLOUD_SETTINGS_ROUTE if is_cloud_settings_enabled() else None,
		"notices": index_notices(),
	}


@frappe.whitelist(methods=["POST"])
def save_index_layer(order: list[str], hidden: list[str]) -> list[dict]:
	"""Store the session user's order and hidden apps on the index; two empty lists reset it. Returns the tiles."""
	tiles = gated_index_tiles()
	write_layer(order, hidden, tiles)
	return arrange(tiles)


def gated_index_tiles() -> list[dict]:
	"""The app layer's tiles, behind the index boot's own gate."""
	# `@frappe.whitelist()` only excludes Guest; a Website User has no index.
	if not has_app_permission("frappe"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return index_tiles()


def index_tiles() -> list[dict]:
	"""One tile per app with an `add_to_apps_screen` hook that this user may open, by `sequence_id`."""
	active = frappe.get_active_apps(_ensure_on_bench=True)
	rails = frappe.get_all("Rail", filters={"standard": 1}, fields=["app", "extends"])
	v2_apps = {"frappe"} | {rail.app for rail in rails if rail.extends == NO_HOST}
	# Mounted on an active host, as v1's docked apps; an app with a rail of its own is no companion.
	companions = {rail.app for rail in rails if rail.extends in active} - v2_apps
	pending = setup_pending_apps()
	prefixes = {app: prefix for prefix, app in get_prefix_registry().items()}
	tiles = []

	for app in active:
		screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [None])[0]
		if not screen or app in companions or app in pending:
			continue

		target = tile_target(app, screen, prefixes[app] if app in v2_apps else None)
		if target:
			sequence = screen.get("sequence_id") or DEFAULT_APP_SEQUENCE_ID
			tiles.append((sequence, {"app": app, **app_screen(app, screen), **target}))

	# Stable, so apps with the same `sequence_id` keep their install order.
	tiles.sort(key=lambda pair: pair[0])
	return [tile for _sequence, tile in tiles]


def setup_pending_apps() -> set[str]:
	"""Active apps whose setup wizard is not done, which only a System Manager sees on the index."""
	if "System Manager" in frappe.get_roles():
		return set()

	ready = {*get_setup_wizard_completed_apps(), *get_setup_wizard_not_required_apps()}
	return {app for app in frappe.get_active_apps(_ensure_on_bench=True) if app not in ready}


def tile_target(app: str, screen: dict, prefix: str | None) -> dict | None:
	"""Where a tile opens: a v2 app's prefix when `prefix` is given, else the hook's route."""
	if prefix:
		return {"kind": "prefix", "route": shell_base(prefix)} if has_app_permission(app) else None

	if may_link_out(app, screen):
		# A hook with no route opens desk v1.
		return {"kind": "link", "route": screen.get("route") or "/desk"}

	return None


def may_link_out(app: str, screen: dict) -> bool:
	"""The hook's own `has_permission`, which guards the app's own UI; a raising check hides the tile."""
	check = screen.get("has_permission")
	if not check:
		return True

	try:
		return bool(frappe.get_attr(check)())
	except Exception:
		frappe.log_error(title=f"add_to_apps_screen has_permission failed for {app}")
		return False


def index_recent() -> list[dict]:
	"""The person's last distinct list and record addresses, newest first, less those they can no longer open."""
	recent = []
	for visit, title, subtitle in titled_visits(RECENT_LIMIT):
		screen = app_screen(visit.app)
		recent.append(
			{
				"route": visit.route,
				"title": title,
				"kind": subtitle,
				"visited": visit.visited,
				"app": visit.app,
				"app_title": screen["title"],
				"app_logo": screen["logo"],
			}
		)

	return recent


def titled_visits(limit: int) -> list[tuple[Visit, str, str | None]]:
	"""Of the person's last `limit` distinct visits, those they can still open, each with its title and subtitle."""
	visits = [visit for visit in latest_visits(limit) if has_app_permission(visit.app)]
	names_by_doctype: dict[str, list[str]] = {}
	for visit in visits:
		if visit.name is not None:
			names_by_doctype.setdefault(visit.doctype, []).append(visit.name)

	titles = {doctype: readable_titles(doctype, names) for doctype, names in names_by_doctype.items()}
	return [(visit, *heading) for visit in visits if (heading := visit_heading(visit, titles))]


def visit_heading(visit: Visit, titles: dict[str, dict[str, str]]) -> tuple[str, str | None] | None:
	"""A visit's title and kind: the record's title and doctype, or the doctype and "List"; None if unreadable."""
	if visit.name is None:
		return (_(visit.doctype), _("List")) if frappe.has_permission(visit.doctype, "read") else None

	title = titles[visit.doctype].get(visit.name)
	if title is None:
		return None
	return title, None if visit.doctype in get_address_table()["singles"] else _(visit.doctype)


def report_oversized_keys(boot: dict, prefix: str | None, reply: str | None = None) -> None:
	"""Weigh every top-level key of a boot, or of the named `reply`, and log the ones past `KEY_BUDGET`."""
	if reply:
		where = f"the {reply} reply"
	elif prefix:
		where = f"prefix {prefix}"
	else:
		where = f"the /{SHELL_ROOT} index"

	try:
		# `orjson_dumps` serialises the response, so these are the bytes on the wire.
		sizes = {key: len(orjson_dumps(value, default=str, decode=False)) for key, value in boot.items()}
		total = sum(sizes.values())

		for key, size in sorted(sizes.items()):
			if size <= KEY_BUDGET:
				continue

			# An atomic `SET NX`, so two workers claim the day's row once between them; `make_key`
			# applies the site prefix `set_value` would.
			claim = frappe.cache.make_key(f"boot_budget:{key}:{where if reply else prefix or SHELL_ROOT}")
			# nosemgrep: frappe-cache-breaks-multitenancy
			if not frappe.cache.set(name=claim, value=1, ex=_BUDGET_LOG_TTL, nx=True):
				continue

			# Deferred because boot is a GET, which is rolled back; Postgres would discard the row.
			frappe.log_error(
				title=BUDGET_LOG_TITLE,
				message=(
					f"{key} is {size:,} B for {frappe.session.user} at {where}, "
					f"over the {KEY_BUDGET:,} B key budget; total {total:,} B."
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

		screen = app_screen(app)
		# Core LAST, so a contributed key cannot overwrite `csrf_token`, `session` or `shell_base`.
		boot = {
			**app_boot(app),
			**core_boot(),
			"shell_base": shell_base(prefix),
			"app": app,
			# The rail's app tile; the index has these per app under `apps`.
			"app_title": screen["title"],
			"app_logo": screen["logo"],
			# A framework key, not an `app_boot` contribution: apps shape navigation through the rows
			# they ship. It rides boot because boot is already a blocking pre-mount fetch.
			"navigation": resolve_navigation(app),
		}

	# One exit, so the index payload is weighed on the same call site as a prefix's.
	report_oversized_keys(boot, prefix)

	return boot
