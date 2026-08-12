"""The one-time invitation to try the module-first navigation.

A site upgrading from the icon-grid release keeps its grid -- that is the promise, and
changing someone's desktop underneath them would break it. But a customer who is never told
the new navigation exists never finds it, so they are asked exactly once.

**Temporary by construction, and here is its end.** It exists only for sites that arrive on
the grid; a fresh install is already on Apps, so the condition is false and no patch is needed
to make it so. It goes with the icon-grid batch -- this module, the boot key in
`frappe.sessions`, and the JS -- on one of the two triggers written down in
`frappe/desk/RETIRING.md`. Until then, declining costs nothing: a customer who declines is
asked again in a later release, which clears the flag, rather than expiring on a date.

Modelled verbatim on `legacy_gravatar_cleanup`, which is the flow this codebase already has
for "ask a system manager once": a `frappe.defaults` flag and a boot flag, so **no schema
change anywhere**. One difference, in our favour: that action is destructive and
irreversible, and this one is reversible from Desktop Settings at any moment -- so it can
honestly be phrased as *try it* rather than as a migration in disguise.
"""

from enum import Enum

import frappe
from frappe import _
from frappe.desk.doctype.desktop_settings.desktop_settings import (
	APPS,
	DesktopSettings,
	is_desktop_icons_page,
)
from frappe.utils import cint

SKIP_NEW_NAVIGATION_PROMPT = "skip_new_navigation_prompt"

# The one deliberate exception to "the site layer is Workspace Manager's". Which desktop
# *screen* a site shows is a system setting, not navigation content -- and Workspace Manager
# is granted to nobody by default, so gating on it alone would show the invitation to nobody
# on almost every site.
INVITED_ROLES = ("System Manager", "Workspace Manager")


class Action(Enum):
	TRY_NEW_NAVIGATION = "try_new_navigation"
	KEEP_ICON_GRID = "keep_icon_grid"


def should_show_new_navigation_prompt() -> bool:
	"""Three conditions, all of which a fresh install fails on the first one."""
	if not is_desktop_icons_page():
		return False

	if cint(frappe.defaults.get_global_default(SKIP_NEW_NAVIGATION_PROMPT)):
		return False

	return bool(set(INVITED_ROLES) & set(frappe.get_roles()))


@frappe.whitelist(methods=["POST"])
def submit_new_navigation_prompt(action: str) -> str:
	"""Either answer is terminal: the flag is set both ways, so nobody is asked twice.

	Accepting deletes nothing -- the icon rows and every user's arrangement stay exactly as
	they are, which is what makes "try it" true. Switching back from Desktop Settings restores
	the grid as it was.
	"""
	if not set(INVITED_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if action == Action.KEEP_ICON_GRID.value:
		skip_new_navigation_prompt()
		return "kept"

	if action == Action.TRY_NEW_NAVIGATION.value:
		settings = frappe.get_single(DesktopSettings._DOCTYPE_NAME)
		settings.desktop_page = APPS
		settings.save(ignore_permissions=True)
		skip_new_navigation_prompt()
		return "switched"

	frappe.throw(_("Invalid action"))


def skip_new_navigation_prompt() -> None:
	frappe.defaults.set_global_default(SKIP_NEW_NAVIGATION_PROMPT, 1)
