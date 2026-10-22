import frappe

from flow.permissions import FLOW_USER_ROLE, ensure_flow_role

FLOW_USER_ROLE_PROFILE = "Frappe Flow User"


def execute():
	"""Every logged-in user could use Flow before the role. Keep enabled System Managers and
	eligible trigger accounts on it. Unsafe legacy triggers are disabled for explicit remediation."""
	ensure_flow_role()
	managers = frappe.get_all(
		"Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent", distinct=True
	)
	accounts = set(
		frappe.get_all(
			"User", filters={"name": ("in", managers), "enabled": 1, "user_type": "System User"}, pluck="name"
		)
	)
	for trigger in frappe.get_all("Flow Trigger", filters={"enabled": 1}, fields=["name", "run_as", "owner"]):
		account = trigger.run_as or trigger.owner
		if account == "Administrator":
			continue
		if _is_enabled_system_user(account):
			accounts.add(account)
		else:
			_disable_trigger(trigger.name, account)
	accounts.discard("Administrator")
	for name in sorted(accounts):
		_grant(frappe.get_doc("User", name))


def _grant(user):
	"""Profile-managed users receive an app-owned profile; shared profiles stay untouched."""
	if not user.role_profiles:
		user.add_roles(FLOW_USER_ROLE)
		return
	if FLOW_USER_ROLE_PROFILE in {row.role_profile for row in user.role_profiles}:
		return
	_ensure_flow_user_profile()
	user.append("role_profiles", {"role_profile": FLOW_USER_ROLE_PROFILE})
	user.save(ignore_permissions=True)


def _ensure_flow_user_profile() -> None:
	if frappe.db.exists("Role Profile", FLOW_USER_ROLE_PROFILE):
		roles = set(
			frappe.get_all(
				"Has Role",
				filters={"parent": FLOW_USER_ROLE_PROFILE, "parenttype": "Role Profile"},
				pluck="role",
			)
		)
		if roles != {FLOW_USER_ROLE}:
			frappe.throw(
				f"Role Profile {FLOW_USER_ROLE_PROFILE!r} already exists with unexpected roles; "
				"rename it before migrating Flow."
			)
		return
	frappe.get_doc(
		{
			"doctype": "Role Profile",
			"role_profile": FLOW_USER_ROLE_PROFILE,
			"roles": [{"role": FLOW_USER_ROLE}],
		}
	).insert(ignore_permissions=True)


def _is_enabled_system_user(name: str) -> bool:
	return bool(frappe.db.exists("User", {"name": name, "enabled": 1, "user_type": "System User"}))


def _disable_trigger(name: str, account: str) -> None:
	frappe.db.set_value("Flow Trigger", name, "enabled", 0, update_modified=False)
	frappe.log_error(
		title="Flow Trigger disabled during Flow User migration",
		message=(
			f"Disabled Flow Trigger {name!r}: its run account {account!r} is not an enabled System User. "
			"Choose an eligible account and enable the trigger again."
		),
	)
