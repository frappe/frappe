import re
from collections import Counter
from itertools import chain, count

import click

import frappe
from frappe.desk.doctype.dock.dock import mounted_apps, resolve_app_dock, save_site_dock
from frappe.desk.doctype.sidebar.sidebar import (
	DEFAULT_HEADER_ICON,
	UNROUTABLE_IN_A_TITLE,
	build_sidebar,
	shell_holding_slug,
)
from frappe.patches.v16_0.sidebar_archive import (
	archive_exists,
	custom_module_of,
	is_custom,
	is_module,
	site_rows,
	write_base,
	written_as_of,
)
from frappe.permissions import ALL_USER_ROLE, GUEST_ROLE, SYSTEM_USER_ROLE
from frappe.utils.modules import get_module_placement


def execute():
	"""Each sidebar a site made becomes its own custom module, added to the end of its app's dock
	as the site's own dock edit. v16 showed such a sidebar only to the users its desktop icon
	showed to, so the module is blocked for everyone else."""
	if not archive_exists():
		return

	users = system_user_roles()
	blocked = False
	for row in site_rows():
		if not is_custom(row):
			continue

		module = custom_module_of(row.name)
		if not module:
			module = make_module(row)
			plan = build_sidebar(module, [row])
			plan.title = module
			write_base(module, plan, written_as_of([row]))
			click.secho(f"Sidebar '{row.name}': carried into custom module '{module}'", fg="green")

		add_to_site_dock(module)
		blocked = block_where_v16_hid(module, v16_icons(row.name), users) or blocked

	# each user's blocked modules are cached with their boot
	if blocked:
		frappe.clear_cache()


def add_to_site_dock(module: str) -> None:
	"""Add the module's sidebar to the end of its app's dock, saved like Manage Dock for everyone."""
	app = get_module_placement(module)
	sidebar = frappe.db.get_value("Sidebar", {"module": module}, ["name", "header_icon"], as_dict=True)
	if not app or not sidebar:
		return

	app = mounted_apps().get(app, app)
	rail = resolve_app_dock(app, upto="site", gated=False)
	if any(entry.get("link_type") == "Sidebar" and entry.get("link_to") == sidebar.name for entry in rail):
		return

	entry = {
		"link_type": "Sidebar",
		"link_to": sidebar.name,
		"icon": sidebar.header_icon or DEFAULT_HEADER_ICON,
		"title": sidebar.name,
	}
	save_site_dock(app, [*rail, entry])


def v16_icons(sidebar: str) -> list[frappe._dict]:
	"""The v16 desktop icons that opened `sidebar`, each with its roles and its parent."""
	icons = frappe.get_all(
		"Desktop Icon",
		filters={"link_type": "Workspace Sidebar", "link_to": sidebar},
		fields=["name", "owner", "standard", "parent_icon"],
	)
	for icon in icons:
		icon.roles = roles_of(icon.name)
		icon.parent = None
		if icon.parent_icon:
			# v16 matched a parent by label among the icons at the top level, a folder or an app
			icon.parent = next(
				iter(
					frappe.get_all(
						"Desktop Icon",
						filters={"label": icon.parent_icon, "parent_icon": ["is", "not set"]},
						fields=["name", "label", "owner", "standard", "icon_type", "app"],
						limit=1,
					)
				),
				None,
			)
			if icon.parent:
				icon.parent.roles = roles_of(icon.parent.name)
	return icons


def roles_of(icon: str) -> set[str]:
	return set(
		frappe.get_all("Has Role", filters={"parenttype": "Desktop Icon", "parent": icon}, pluck="role")
	)


def v16_showed(icons: list[frappe._dict], user: str, roles: set[str]) -> bool:
	"""Whether v16's `get_desktop_icons` showed `user` any of `icons`."""

	def passes(icon) -> bool:
		if not (icon.standard or icon.owner in ("Administrator", user)):
			return False
		if icon.roles and not icon.roles & roles:
			return False
		return icon.icon_type != "App" or app_permitted(icon, user)

	return any(
		passes(icon) and (not icon.parent_icon or (icon.parent and passes(icon.parent))) for icon in icons
	)


def app_permitted(icon: frappe._dict, user: str) -> bool:
	"""v16's `check_app_permission` for an App icon, asked as `user`."""
	for app in frappe.get_installed_apps():
		if app != icon.app and (frappe.get_hooks("app_title", app_name=app) or [None])[0] != icon.label:
			continue
		screen = frappe.get_hooks("add_to_apps_screen", app_name=app)
		method = screen and screen[0].get("has_permission")
		if not method:
			return True
		# the hook answers for the session user, so it is asked as each user in turn
		current = frappe.session.user
		frappe.set_user(user)  # nosemgrep
		try:
			return bool(frappe.get_attr(method)())
		finally:
			frappe.set_user(current)  # nosemgrep
	return False


def system_user_roles() -> dict[str, set[str]]:
	"""Every desk user's roles, read once."""
	users = {
		user: {GUEST_ROLE, ALL_USER_ROLE, SYSTEM_USER_ROLE}
		for user in frappe.get_all(
			"User",
			filters={"user_type": "System User", "name": ["not in", frappe.STANDARD_USERS]},
			pluck="name",
		)
	}
	for row in frappe.get_all("Has Role", filters={"parenttype": "User"}, fields=["parent", "role"]):
		if row.parent in users:
			users[row.parent].add(row.role)
	return users


def block_where_v16_hid(module: str, icons: list[frappe._dict], users: dict[str, set[str]]) -> bool:
	"""Block `module` for every user v16 showed none of `icons` to, in one insert."""
	if not icons:
		return False

	already = set(
		frappe.get_all("Block Module", filters={"parenttype": "User", "module": module}, pluck="parent")
	)
	hidden_from = [
		user for user, roles in users.items() if user not in already and not v16_showed(icons, user, roles)
	]
	if not hidden_from:
		return False

	rows = Counter(
		frappe.get_all(
			"Block Module", filters={"parenttype": "User", "parent": ["in", hidden_from]}, pluck="parent"
		)
	)
	now = frappe.utils.now()
	frappe.db.bulk_insert(
		"Block Module",
		fields=[
			"name",
			"creation",
			"modified",
			"owner",
			"modified_by",
			"parent",
			"parenttype",
			"parentfield",
			"idx",
			"module",
		],
		values=[
			(
				frappe.generate_hash(),
				now,
				now,
				"Administrator",
				"Administrator",
				user,
				"User",
				"block_modules",
				rows[user] + 1,
				module,
			)
			for user in hidden_from
		],
	)
	return True


def make_module(row) -> str:
	"""Create the custom module `row` becomes, placed in the app v16 filed it under."""
	name = module_name_for(row.name)
	if frappe.db.exists("Module Def", name):
		return name

	frappe.get_doc(
		{
			"doctype": "Module Def",
			"module_name": name,
			"custom": 1,
			"app_name": get_module_placement(row.module) if is_module(row.module) else None,
		}
	).insert(ignore_permissions=True)
	return name


# `Module Def.module_name` is a Data field
MODULE_NAME_LENGTH = 140


def module_name_for(title: str) -> str:
	"""The sidebar's title, made URL-safe, or the nearest free name: `Stock` becomes `Stock (Custom)`."""
	cleaned = " ".join(re.sub(f"[{re.escape(UNROUTABLE_IN_A_TITLE)}]", " ", title).split())
	cleaned = cleaned[: MODULE_NAME_LENGTH - len(" (Custom) 999")].strip() or "Custom Sidebar"
	candidates = chain((cleaned, f"{cleaned} (Custom)"), (f"{cleaned} (Custom) {n}" for n in count(2)))
	return next(candidate for candidate in candidates if is_free(candidate))


def is_free(name: str) -> bool:
	if frappe.db.exists("Module Def", name):
		return bool(frappe.db.get_value("Module Def", name, "custom")) and not frappe.db.exists(
			"Sidebar", {"module": name}
		)

	return not shell_holding_slug(name, module=name)
