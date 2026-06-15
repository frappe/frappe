import frappe
from frappe.utils import now


def execute():
	"""Prefill `Workspace.allowed_users` from the legacy module-blocking visibility.

	Workspace visibility used to be controlled implicitly through `block_modules`: a
	workspace was hidden from a user when its `module` was in that user's blocked
	modules (set directly or inherited from a Module Profile). Workspace filtering now
	uses the explicit `allowed_users` child table instead, so this patch translates the
	old implicit rules into explicit ones to preserve existing visibility.

	For each workspace with a `module`:
	  * If no enabled user blocks that module, `allowed_users` is left empty -- empty
	    means "visible to all", matching the previous behaviour.
	  * Otherwise `allowed_users` is set to the complement: every enabled user who does
	    *not* block the module, preserving "blocked users can't see it".

	Caveats:
	  * Scale -- the complement list can be large on sites with many users, so only
	    workspaces with at least one blocking user are populated.
	  * Mixed role + module workspaces -- the old behaviour was "has role AND not
	    blocked"; the new model is "has role OR in allowed_users" (more permissive).
	    Such workspaces are rare and are not special-cased here.
	"""

	# block_modules rows are synced onto the User from any Module Profile on save, so
	# the child table already reflects direct + profile-derived blocks.
	enabled_users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
	if not enabled_users:
		return
	enabled_user_set = set(enabled_users)

	# module -> set(enabled users who block it)
	module_blockers: dict[str, set[str]] = {}
	for row in frappe.get_all(
		"Block Module",
		filters={"parenttype": "User", "parent": ["in", enabled_users]},
		fields=["parent", "module"],
	):
		if row.module:
			module_blockers.setdefault(row.module, set()).add(row.parent)

	if not module_blockers:
		return

	workspaces = frappe.get_all(
		"Workspace",
		filters={"module": ["in", list(module_blockers.keys())]},
		fields=["name", "module"],
	)

	timestamp = now()
	columns = [
		"name",
		"creation",
		"modified",
		"modified_by",
		"owner",
		"docstatus",
		"idx",
		"parent",
		"parentfield",
		"parenttype",
		"user",
	]
	rows = []
	for ws in workspaces:
		blockers = module_blockers.get(ws.module)
		if not blockers:
			continue

		allowed = sorted(enabled_user_set - blockers)
		for idx, user in enumerate(allowed, start=1):
			rows.append(
				(
					frappe.generate_hash(length=10),
					timestamp,
					timestamp,
					"Administrator",
					"Administrator",
					0,
					idx,
					ws.name,
					"allowed_users",
					"Workspace",
					user,
				)
			)

		# commit periodically to keep memory/transaction size bounded on large sites
		if len(rows) >= 5000:
			frappe.db.bulk_insert("Workspace Allowed Users", fields=columns, values=rows)
			frappe.db.commit()
			rows = []

	if rows:
		frappe.db.bulk_insert("Workspace Allowed Users", fields=columns, values=rows)
		frappe.db.commit()
