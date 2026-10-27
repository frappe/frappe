# The index's notices: the site's setup nudge and what's new, for the managers who act on them.

import frappe
from frappe import _
from frappe.core.doctype.installed_applications.installed_applications import (
	get_setup_wizard_pending_apps,
)
from frappe.desk.page.setup_wizard.setup_wizard import get_setup_wizard_url
from frappe.utils import md_to_html, sha256_hash
from frappe.utils.change_log import get_change_log, update_last_known_versions

SETUP_ROLE = "System Manager"
WHATS_NEW_ROLES = {"System Manager", "Workspace Manager"}
WHATS_NEW_CACHE_PREFIX = "index_whats_new::"
WHATS_NEW_CACHE_SECONDS = 24 * 60 * 60


def index_notices() -> dict:
	"""The notices this person acts on; a person without a manager role gets none and pays nothing."""
	roles = set(frappe.get_roles())
	if not roles & ({SETUP_ROLE} | WHATS_NEW_ROLES):
		return {}

	# Request-cached: core boot has already read it.
	setup_complete = frappe.is_setup_complete()
	notices = {}

	if SETUP_ROLE in roles and not setup_complete:
		notices["setup"] = setup_nudge()

	if roles & WHATS_NEW_ROLES and setup_complete:
		notices["whats_new"] = whats_new()

	return {key: notice for key, notice in notices.items() if notice}


def setup_nudge() -> dict | None:
	"""One nudge for the site: the apps its wizard has yet to set up, and where the wizard is."""
	pending = get_setup_wizard_pending_apps(frappe.get_active_apps(_ensure_on_bench=True))
	if not pending:
		return None

	return {"apps": [app_title(app) for app in pending], "route": get_setup_wizard_url()}


def whats_new() -> list[dict]:
	"""Each app updated since this person last looked, as its title and new version."""
	if frappe.get_system_settings("disable_change_log_notification"):
		return []

	seen = frappe.db.get_value("User", frappe.session.user, "last_known_versions")
	if not seen:
		record_first_versions()
		return []

	seen_versions = frappe.parse_json(seen)
	current = {app: app_version(app) for app in frappe.get_active_apps(_ensure_on_bench=True)}
	if all(
		((seen_versions.get(app) or {}).get("version") or "0.0.1") == version
		for app, version in current.items()
	):
		return []

	# `get_change_log` runs git per app; a version with no notes would otherwise pay that on every load.
	key = f"{WHATS_NEW_CACHE_PREFIX}{frappe.session.user}::{sha256_hash(seen + frappe.as_json(current))}"
	updated = frappe.cache.get_value(key)
	if updated is None:
		updated = [{"title": entry["title"], "version": entry["version"]} for entry in get_change_log()]
		frappe.cache.set_value(key, updated, expires_in_sec=WHATS_NEW_CACHE_SECONDS)
	return [{"title": _(entry["title"]), "version": entry["version"]} for entry in updated]


def record_first_versions():
	"""A person with none recorded has nothing new yet; the boot is a GET, so the write must ask to commit."""
	if frappe.flags.read_only:
		return

	update_last_known_versions()
	frappe.local.flags.commit = True


@frappe.whitelist(methods=["POST"])
def read_whats_new() -> list[dict]:
	"""The release notes of each app updated since the session user last looked, then recorded as seen."""
	frappe.only_for(list(WHATS_NEW_ROLES))
	entries = [
		{
			"title": _(entry["title"]),
			"version": entry["version"],
			"notes": [
				{"version": version, "html": md_to_html(markdown) or ""}
				for version, markdown in entry["change_log"]
			],
		}
		for entry in get_change_log()
	]
	update_last_known_versions()
	return entries


def app_version(app: str) -> str:
	"""As `get_versions` reads it."""
	try:
		return frappe.get_attr(f"{app}.__version__")
	except AttributeError:
		return "0.0.1"


def app_title(app: str) -> str:
	return _((frappe.get_hooks("app_title", app_name=app) or [app])[0])
