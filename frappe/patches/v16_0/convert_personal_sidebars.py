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
	"""Turn every v16 fork into a `Custom Sidebar` for the person who made it.

	Runs after the site's sidebars are converted, since a fork is laid over the one it was copied
	from. The old rows are left untouched, so this is safe to re-run.
	"""
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
	"""Every convertible fork, grouped by the person and module it belongs to.

	One group per `(user, module)`: v16 forked per workspace sidebar, so one person can hold
	several arrangements that now have a single layer to become. They are merged, not made to compete.
	"""
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
	"""Return the sidebar this fork was copied from. v16 named a fork `<sidebar>-<user>`.

	It is worth recovering, because it is the list the user was looking at when they rearranged
	it.
	"""
	title = fork.title or fork.name
	source = title.removesuffix(f"-{fork.for_user}")
	if source == title:
		return None

	return source if frappe.db.exists(ARCHIVE_DOCTYPE, source) else None


def arrangement_below(module: str) -> list:
	"""The module's base sidebar, which a person's layer is laid over.

	Read after the site's sidebars are converted, so items that exist in both are stored as
	references and stay live.

	`get_module_base` rather than indexing `get_sidebar_bases` by the module: that dict is keyed by
	shell, and a converted `Sidebar` is named after the v16 title it was converted from, which is
	only the module's name when several sidebars were merged. One sidebar called anything else --
	"Invoicing" under `Accounts`, say -- means no key under the module, and a `KeyError` here takes
	down the migrate of any site where such a module also has a fork.
	"""
	return get_module_base(module).rows


def dropped_keys(forks: list[frappe._dict], items: list[dict]) -> set[str]:
	"""Return what this user removed, as opposed to what they were never offered.

	Only items the source sidebar showed them count as removed. Anything the module gained since
	is new to them rather than something they hid.
	"""
	kept = {item_key(item) for item in items}
	offered = {item_key(row) for fork in forks if fork.source for row in archive_items(fork.source)}
	return offered - kept
