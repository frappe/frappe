# The index's notices: the site's setup nudge and what's new, for the managers who act on them.

import frappe
from frappe import _
from frappe.core.doctype.installed_applications.installed_applications import (
	get_setup_wizard_pending_apps,
)
from frappe.desk.page.setup_wizard.setup_wizard import get_setup_wizard_url
from frappe.utils import md_to_html
from frappe.utils.change_log import get_change_log

SETUP_ROLE = "System Manager"
WHATS_NEW_ROLES = {"System Manager", "Workspace Manager"}


def index_notices(setup_complete: bool) -> dict:
	"""The notices this person acts on; a person without a manager role gets none and pays nothing."""
	roles = set(frappe.get_roles())
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
	"""Each app updated since this person last looked, with its release notes as HTML."""
	if frappe.get_system_settings("disable_change_log_notification"):
		return []

	return [
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


def app_title(app: str) -> str:
	return _((frappe.get_hooks("app_title", app_name=app) or [app])[0])
