from collections import defaultdict

import click

import frappe
from frappe.desk.doctype.sidebar.sidebar import build_sidebar, get_module_base, item_key, majority_module_of
from frappe.patches.v16_0.sidebar_archive import (
	ARCHIVE_DOCTYPE,
	archive_exists,
	archive_items,
	is_module,
	is_private_container,
	layer_rows,
	module_holding,
	write_user_layer,
)


def execute():
	"""A user's personal copy becomes their `Custom Sidebar`, laid over the sidebar it was copied
	from."""
	if not archive_exists():
		return

	from frappe.desk.doctype.custom_sidebar.custom_sidebar import get_customization

	converted = 0
	for (user, module), forks in sorted(forks_by_owner().items()):
		if get_customization(module, user):
			continue

		plan = build_sidebar(module, forks)
		write_user_layer(
			module,
			user,
			layer_rows(plan["items"], arrangement_below(module), dropped_keys(forks, plan["items"])),
		)
		converted += 1

		click.secho(
			f"Module '{module}': kept {user}'s own arrangement from {', '.join(f.name for f in forks)}",
			fg="green",
		)

	if converted:
		click.secho(f"Sidebars: {converted} personal arrangement(s) kept.", fg="green")


def forks_by_owner() -> dict[tuple[str, str], list[frappe._dict]]:
	"""Every convertible personal copy, grouped by user and module, since they merge into one layer."""
	forks = frappe.get_all(
		ARCHIVE_DOCTYPE,
		filters={"for_user": ["is", "set"]},
		fields=["name", "title", "module", "header_icon as icon", "for_user", "creation"],
		order_by="creation asc",
	)

	by_owner = defaultdict(list)
	for fork in forks:
		if is_private_container(fork):
			continue

		fork.source = source_of(fork)
		# spacers are named after the sidebar the fork was copied from, so they match its rows
		fork.rows = archive_items(fork.name, spacer_scope=fork.source)
		fork.sequence_id = 0
		fork.title = fork.source or fork.title

		# laid over the sidebar it was copied from, wherever that lives now: a custom sidebar has
		# a module of its own, and an app may have moved its sidebar out of the v16 module
		module = (fork.source and module_holding(fork.source)) or fork.module or majority_module_of(fork.rows)
		# a fork with no owner, no module or no rows has no layer to become; left in the archive
		if not fork.rows or not is_module(module):
			continue
		if not frappe.db.exists("User", fork.for_user):
			continue

		by_owner[(fork.for_user, module)].append(fork)

	return by_owner


def source_of(fork) -> str | None:
	"""The sidebar this copy was made from. v16 named a copy `<sidebar>-<user>`."""
	title = fork.title or fork.name
	source = title.removesuffix(f"-{fork.for_user}")
	if source == title:
		return None

	return source if frappe.db.exists(ARCHIVE_DOCTYPE, source) else None


def arrangement_below(module: str) -> list:
	"""The module's base sidebar. `get_sidebar_bases` is keyed by sidebar name, not module, so
	indexing it by module fails for a sidebar like "Invoicing" under `Accounts`."""
	return get_module_base(module).rows


def dropped_keys(forks: list[frappe._dict], items: list[dict]) -> set[str]:
	"""What this user removed from the sidebar they copied, not what was added since."""
	kept = {item_key(item) for item in items}
	offered = {item_key(row) for fork in forks if fork.source for row in archive_items(fork.source)}
	return offered - kept
