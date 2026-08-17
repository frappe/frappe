import click

import frappe

# Where a workspace the site made goes when nothing says where it belongs. Both are custom
# modules the site owns rather than modules any app ships -- see `ensure_module`.
PRIVATE_MODULE = "Private"
CUSTOM_MODULE = "Custom Workspaces"


def execute():
	"""Give every module-less Workspace a module, so `Workspace.module` can become mandatory.

	The dock is module-shaped now, so a workspace with no module belongs nowhere: no dock tile
	carries it, and no module's sidebar lists it -- a sidebar is built from what its module
	contains, and a module-less workspace is contained by nothing.

	**No heuristic.** Every signal available here -- the workspace's old `app`, the module its
	links happen to point at, its parent's module -- answers a different question than the one
	being asked. `app` in particular records where the person was standing when they hit
	"Create Workspace" (the dialog made it mandatory and defaulted it to the current app), not
	what the page is about, so guessing from it files a page full of leave applications under
	Accounts and does it confidently. And a guess that lands is worth little either way: whoever
	made these workspaces is going to arrange them where they want them regardless. So they go
	somewhere honest and stay reachable, and moving them is the site's business.

	Two destinations, and `for_user` is the whole of the choice:

	  * `for_user` set -- one person's own page, so it goes to `Private`, which resolves per
	    reader (see below) and shows nobody anyone else's pages.
	  * everything else -- a shared page the site made, so it goes to `Custom Workspaces`, a
	    triage list a workspace manager redistributes from.

	`for_user` rather than `public`, because `public = 0` with no `for_user` is a third state
	and `frappe.desk.desktop.get_workspaces` reads it as *shared*, not private.

	`standard` does not come into the choice at all, and could not: a workspace an app ships is
	backed by a file under that app's module folder and carries the `module` its JSON declares,
	so nothing standard has any business reaching a patch that only ever reads module-less rows.
	A row here carrying `standard = 1` is carrying it wrongly -- which the old `set_standard_flag`
	produced, on develop benches only, that patch never having been in a release.

	Nothing has to run after it: a module's sidebar is computed from the module's contents on
	every read (`sidebar.get_computed_base`), so a workspace is listed the moment this patch
	gives it a module, with no second pass to store the result.
	"""
	workspaces = frappe.get_all(
		"Workspace",
		filters={"module": ["in", ["", None]]},
		fields=["name", "for_user"],
	)
	if not workspaces:
		return

	buckets = {
		PRIVATE_MODULE: [w.name for w in workspaces if w.for_user],
		CUSTOM_MODULE: [w.name for w in workspaces if not w.for_user],
	}

	for module, names in buckets.items():
		# Only ever created for workspaces that need it: a site with none of one kind should
		# not be given an empty module standing on its desktop.
		if not names:
			continue

		ensure_module(module)
		frappe.db.set_value("Workspace", {"name": ["in", names]}, "module", module, update_modified=False)
		click.secho(f"  {len(names)} workspace(s) -> {module}", fg="green")


def ensure_module(module: str) -> None:
	"""The destination module, as a module the *site* owns.

	`custom` is ownership: it keeps an app's uninstall from taking a module full of the site's
	workspaces with it (`frappe.installer.get_app_owned_modules` filters on exactly this), and
	it keeps `ModuleDef.on_update` from writing a folder and a `modules.txt` line for a module
	no app ships.

	`app_name` is placement, and it is deliberately left unset: no app has a claim on these, and
	an unplaced custom module is not stranded -- it stands on the desktop as its own tile
	(`frappe.boot.get_standalone_modules`), for the people whose sidebar for it resolves to
	anything. That is what makes `Private` work as one shared module: its rows are derived per
	reader from that reader's own pages (`sidebar.get_private_workspaces`), so the tile appears
	only for someone who has private workspaces, and only ever holds their own.
	"""
	if frappe.db.exists("Module Def", module):
		return

	frappe.get_doc({"doctype": "Module Def", "module_name": module, "custom": 1}).insert(
		ignore_permissions=True
	)
