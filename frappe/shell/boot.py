# The v2 boot — a small payload of core plus the declaring app, not `frappe.sessions.get()`.

from html import unescape

import frappe
from frappe import _
from frappe.boot import DEFAULT_APP_SEQUENCE_ID
from frappe.core.api.file import get_file_chunk_size, get_max_file_size
from frappe.core.doctype.installed_applications.installed_applications import (
	get_setup_wizard_completed_apps,
	get_setup_wizard_not_required_apps,
)
from frappe.desk.link_title import get_link_titles
from frappe.sessions import get_session_info
from frappe.translate import get_translation_version
from frappe.utils import cstr, orjson_dumps, strip_html

from . import SHELL_ROOT
from .doctypes import get_address_table, get_doctype_owners, metadata_version
from .links import canonical_path
from .navigation import NO_HOST, resolve_navigation
from .permissions import has_app_permission
from .registry import get_prefix_registry, prefix_map, shell_base, split_shell_path
from .route_history import Visit, latest_visits

# Bytes one top-level boot key may reach before boot logs it.
KEY_BUDGET = 100_000

# One row per key per prefix per day; never keyed on the user.
_BUDGET_LOG_TTL = 24 * 60 * 60

# Fixed, so the rows group in the Error Log list.
BUDGET_LOG_TITLE = "Boot key over budget"

FAVOURITES_LIMIT = 8
RECENT_LIMIT = 5


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


def app_screen(app: str, screen: dict | None = None) -> dict:
	"""The app's title and logo, from its `add_to_apps_screen` entry."""
	if screen is None:
		screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [{}])[0]
	return {
		"title": _(screen.get("title") or app.replace("_", " ").title()),
		"logo": screen.get("logo"),
	}


def index_boot() -> dict:
	"""Boot for `/apps` itself, the index, which belongs to no app; the app list lives only here."""
	# `@frappe.whitelist()` only excludes Guest; a Website User must not read core boot.
	if not has_app_permission("frappe"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return {
		**core_boot(),
		"shell_base": f"/{SHELL_ROOT}",
		"app": None,
		"apps": index_tiles(),
		"favourites": index_favourites(),
		"recent": index_recent(),
	}


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


def index_favourites() -> list[dict]:
	"""The person's latest favourites, newest first, less those whose record they can no longer open."""
	rows = frappe.get_all(
		"Favourite",
		filters={"user": frappe.session.user},
		fields=["reference_doctype", "reference_name"],
		order_by="creation desc",
		limit=FAVOURITES_LIMIT,
	)
	owners = get_doctype_owners()
	names_by_doctype: dict[str, list[str]] = {}
	for row in rows:
		names_by_doctype.setdefault(row.reference_doctype, []).append(row.reference_name)

	titles = {
		doctype: readable_titles(doctype, names)
		for doctype, names in names_by_doctype.items()
		if doctype in owners and has_app_permission(owners[doctype])
	}

	favourites = []
	for row in rows:
		doctype, name = row.reference_doctype, row.reference_name
		title = titles.get(doctype, {}).get(name)
		if title is None:
			continue

		screen = app_screen(owners[doctype])
		favourites.append(
			{
				"doctype": doctype,
				"name": name,
				"title": title,
				"route": canonical_path(doctype, name),
				"app": owners[doctype],
				"app_title": screen["title"],
				"app_logo": screen["logo"],
			}
		)

	return favourites


def index_recent() -> list[dict]:
	"""The person's last distinct list and record addresses, newest first, less those they can no longer open."""
	visits = [visit for visit in latest_visits(RECENT_LIMIT) if has_app_permission(visit.app)]
	names_by_doctype: dict[str, list[str]] = {}
	for visit in visits:
		if visit.name is not None:
			names_by_doctype.setdefault(visit.doctype, []).append(visit.name)

	titles = {doctype: readable_titles(doctype, names) for doctype, names in names_by_doctype.items()}
	recent = []
	for visit in visits:
		heading = visit_heading(visit, titles)
		if heading is None:
			continue

		screen = app_screen(visit.app)
		recent.append(
			{
				"route": visit.route,
				"title": heading[0],
				"kind": heading[1],
				"visited": visit.visited,
				"app": visit.app,
				"app_title": screen["title"],
				"app_logo": screen["logo"],
			}
		)

	return recent


def visit_heading(visit: Visit, titles: dict[str, dict[str, str]]) -> tuple[str, str | None] | None:
	"""A visit's title and kind: the record's title and doctype, or the doctype and "List"; None if unreadable."""
	if visit.name is None:
		return (_(visit.doctype), _("List")) if frappe.has_permission(visit.doctype, "read") else None

	title = titles[visit.doctype].get(visit.name)
	if title is None:
		return None
	return title, None if visit.doctype in get_address_table()["singles"] else _(visit.doctype)


def readable_titles(doctype: str, names: list[str]) -> dict[str, str]:
	"""`{name: title}` for the records of `names` this person may read; a raising doctype lists none."""
	meta = frappe.get_meta(doctype)
	if meta.is_virtual or not frappe.has_permission(doctype, "read"):
		return {}

	if meta.issingle:
		return {doctype: _(doctype)} if doctype in names else {}

	try:
		titles = get_link_titles(doctype, meta.title_field or "name", set(names))
	except Exception:
		frappe.log_error(title=f"Index favourites failed for {doctype}")
		return {}

	return {name: plain_text(title) or name for name, title in titles.items()}


def plain_text(value) -> str:
	"""A title field may be a Text Editor; a chip draws text."""
	return unescape(strip_html(cstr(value))).strip()


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
