from collections import defaultdict

import click

import frappe
from frappe.desk.doctype.sidebar.sidebar import (
	LINKED_IDENTITY_FIELDS,
	SIDEBAR_ITEM_FIELDS,
	build_sidebar,
	get_sidebar_bases,
	is_linked,
	item_key,
	majority_module_of,
)

# The v16 sidebar store, an inert archive here: nothing reads it at runtime and nothing writes a
# row to it. This patch is the one reader it has left, and it only ever reads.
ARCHIVE_DOCTYPE = "Workspace Sidebar"
ARCHIVE_ITEM_DOCTYPE = "Workspace Sidebar Item"

# v16 gave a user's *private* workspaces a sidebar of their own to hang off, titled "My
# Workspaces". Nothing in it was authored -- every row was a link to a page that user owns -- and
# those links are derived on read now (`sidebar.get_private_workspaces`), so the container is
# passed over rather than converted. Matched on the title because that is all it ever had.
PRIVATE_CONTAINER_TITLE = "my workspaces"


def execute():
	"""Carry every sidebar a v16 site holds into the documents that hold one now.

	The archive has three populations and each converts differently:

	- a **site-level row** -- one per public workspace, whether v16 generated it from that
	  workspace's shortcuts or an app shipped it as `<app>/workspace_sidebar/*.json`. Merged per
	  module and written as the module's **`Sidebar`**, which is the base the desk reads. Not a
	  `Custom Sidebar`: a layer means *this site disagrees with the base*, and this content is
	  not a disagreement -- it is the base, recovered from where the previous version kept it.
	- a **fork** -- v16 copied a whole sidebar to `<title>-<user>` on any edit a non-developer
	  made, so a fork is one person's own arrangement, which is a disagreement. That becomes a
	  `Custom Sidebar` for that user, laid over the base written above.
	- the **private container**, which holds nothing that is not derived now. Passed over.

	**Writing the base is what makes an app's next release take over by itself.** A `Sidebar` is
	named by its title, so where the app titles its sidebar what the site's was called -- which
	is every module the conversion titled after itself -- the file the author ships lands on this
	very row and `modules.import_file` overwrites it: newest writer wins, the rule every other
	piece of app content already follows, and `written_as_of` is what keeps it honest.

	Where the two titles differ -- a module with one v16 sidebar keeps that workspace's label, so
	`Loan Management` reads "Lending" -- the app's arrives as a second sidebar under the module
	rather than on top of this row, and the **naming rule** hands the module over instead: the
	sidebar called after the module is the one the module answers with. Either way the author's
	navigation is what the desk shows, and the converted row stops being read.

	Standard is deliberately 0. The flag means *a file in an app backs this row*, and no file
	does: the fixture it came from stops being imported with this release. It also keeps orphan
	removal away, which reaps standard rows whose file has gone.

	A module that already has a `Sidebar` is skipped outright -- the app has re-exported, or a
	previous run of this patch already wrote one, and either way the current statement stands.

	Runs post_model_sync, under `in_patch` -- which is what lets it write app content on a site
	that is not in developer mode (`Sidebar.validate_app_content`).

	Non-destructive and re-runnable: every archive row is left exactly as it was. Undo is
	deleting the rows it created.
	"""
	if not frappe.db.exists("DocType", ARCHIVE_DOCTYPE):
		return

	converted = convert_site_sidebars()
	forks = convert_forks()

	if converted or forks:
		click.secho(
			f"Sidebars: {len(converted)} module(s) carried over, {len(forks)} personal arrangement(s) kept.",
			fg="green",
		)


# ---------------------------------------------------------------------------------------
# The base -- what this site showed everybody
# ---------------------------------------------------------------------------------------


def convert_site_sidebars() -> list[str]:
	"""Every module's site-level rows, merged into one `Sidebar` each."""
	converted = []
	for module, sources in sorted(site_sources().items()):
		# The whole precedence rule: a document already there is the current statement about
		# this module, whoever made it. Asked of the module rather than of the name, because a
		# sidebar is named by its title now and the module's own may be called anything.
		if frappe.db.exists("Sidebar", {"module": module}):
			continue

		plan = build_sidebar(module, sources)
		write_base(module, plan, written_as_of(sources))
		converted.append(module)

		if plan["secondaries"]:
			click.secho(
				f"Module '{module}': merged {plan['primary']} <- {', '.join(plan['secondaries'])}",
				fg="yellow",
			)

	return converted


def write_base(module: str, plan, as_of) -> None:
	"""The merged list, as the module's base."""
	doc = frappe.new_doc("Sidebar")
	doc.module = module
	# The site's own name for the module, which is what v16 showed everyone: an unmerged module
	# keeps its workspace's title, so `Loan Management` still reads "Lending". A merge takes the
	# module name -- the union of four sidebars is not any one of them.
	doc.title = plan["title"]
	doc.header_icon = plan["header_icon"]
	doc.standard = 0
	doc.merged_from = plan["merged_from"]
	# no `app`: nothing here came from an app's file, and placement falls back to the module's
	for item in plan["items"]:
		doc.append("items", {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS})
	doc.insert(ignore_permissions=True)

	# Stamped with what it was converted from, not with today. `import_file` skips a file older
	# than the row it would overwrite, so a row stamped `now` would silently outrank an export
	# the author made last month -- and the app would never take its own sidebar back.
	frappe.db.set_value("Sidebar", doc.name, "modified", as_of, update_modified=False)


def written_as_of(sources: list[frappe._dict]):
	"""When this content was last true, which is when v16 last wrote any of it."""
	return max(source.modified for source in sources)


def site_sources() -> dict[str, list[frappe._dict]]:
	"""The archive's site-level rows, grouped by the module each belongs to.

	`standard` is deliberately not part of the grouping. It says an app shipped the row, which
	decides who may edit a `Sidebar` -- but here both kinds are the same thing: a list this site
	was showing, whose file (if it ever had one) stops being imported with this release.
	"""
	rows = frappe.get_all(
		ARCHIVE_DOCTYPE,
		filters={"for_user": ["is", "not set"]},
		fields=["name", "title", "module", "header_icon as icon", "creation", "modified"],
		order_by="creation asc",
	)

	by_module = defaultdict(list)
	for row in rows:
		if is_private_container(row):
			continue

		row.rows = archive_items(row.name)
		# `sequence_id` is only a tie-break in `pick_primary`, and the archive has none; the
		# `creation` order these are read in stands in for it.
		row.sequence_id = 0
		module = row.module or majority_module_of(row.rows)
		if not row.rows or not is_module(module):
			continue

		by_module[module].append(row)

	return by_module


# ---------------------------------------------------------------------------------------
# User layers -- what one person did to what everybody was shown
# ---------------------------------------------------------------------------------------


def convert_forks() -> list[tuple[str, str]]:
	"""Every convertible fork, as its owner's own layer."""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import get_customization

	converted = []
	for (user, module), forks in sorted(forks_by_owner().items()):
		if get_customization(module, user):
			continue

		plan = build_sidebar(module, forks)
		write_user_layer(
			module,
			user,
			layer_rows(plan["items"], arrangement_below(module), dropped_keys(forks, plan["items"])),
		)
		converted.append((user, module))

		click.secho(
			f"Module '{module}': kept {user}'s own arrangement from {', '.join(f.name for f in forks)}",
			fg="green",
		)

	return converted


def forks_by_owner() -> dict[tuple[str, str], list[frappe._dict]]:
	"""Every convertible fork in the archive, grouped by the person and module it belongs to.

	One group per `(user, module)`, not per fork: v16 forked *per workspace sidebar*, and a
	module had as many of those as it had workspaces, so one person can hold several arrangements
	that now have a single layer to become. They are merged rather than made to compete.
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

		fork.rows = archive_items(fork.name)
		fork.sequence_id = 0
		fork.source = source_of(fork)
		fork.title = fork.source or fork.title

		module = fork.module or majority_module_of(fork.rows)
		# A fork whose owner is gone has nobody to be a preference for, one whose module is not
		# on this site has no layer to be, and an empty one is not an arrangement. Left in the
		# archive in every case, so nothing is destroyed and a reinstall brings it back.
		if not fork.rows or not is_module(module):
			continue
		if not frappe.db.exists("User", fork.for_user):
			continue

		by_owner[(fork.for_user, module)].append(fork)

	return by_owner


def source_of(fork) -> str | None:
	"""The sidebar this fork was a copy of, which v16 named it after.

	`add_sidebar_items` titled a fork `<sidebar>-<user>` and `Workspace Sidebar` is named by its
	title, so the parent's name falls straight out of the fork's own -- no column had to record
	it. Worth recovering twice over: it is the *unforked* list, which is what says which of
	today's items this person actually decided against (`dropped_keys`), and its title is the
	human one, where the fork's carries an email address.
	"""
	title = fork.title or fork.name
	source = title.removesuffix(f"-{fork.for_user}")
	if source == title:
		return None

	return source if frappe.db.exists(ARCHIVE_DOCTYPE, source) else None


def arrangement_below(module: str) -> list:
	"""What a person's own layer is laid over -- the module's base, whichever route it arrived by.

	Read *after* the pass above, deliberately: what that pass wrote is the base, so a fork item
	that also appeared in the site's own list is stored here as a reference and keeps taking its
	label and link from below. Read before it, every one of those would have been carried whole
	and frozen in one person's layer.
	"""
	return get_sidebar_bases([module])[module].rows


def dropped_keys(forks: list[frappe._dict], items: list[dict]) -> set[str]:
	"""What this person took *out*, as opposed to what they were simply never offered.

	The distinction is the whole of the fidelity here. A fork is the full list as it stood in
	v16, so an item missing from it is missing for one of two unrelated reasons: the person
	removed it, or it is something the module has now and v16 never showed them -- a doctype the
	computed base lists, a row an app has since shipped. Hiding both would leave a v16 customer
	with a permanently smaller sidebar than the colleague who never touched theirs, and no way to
	find out what they were missing.

	So only the *source* sidebar's own items can be dropped: it is exactly what the person was
	looking at when they rearranged it. A fork whose source is gone drops nothing, which errs
	toward showing too much rather than hiding something nobody chose to hide.
	"""
	kept = {item_key(item) for item in items}
	offered = {item_key(row) for fork in forks if fork.source for row in archive_items(fork.source)}
	return offered - kept


# ---------------------------------------------------------------------------------------
# Reading the archive, and writing what comes out of it
# ---------------------------------------------------------------------------------------


def is_private_container(sidebar) -> bool:
	return PRIVATE_CONTAINER_TITLE in (sidebar.title or sidebar.name or "").lower()


def is_module(module: str | None) -> bool:
	"""Whether this site still has the module a source names.

	A sidebar outlives the app that authored it: the archive keeps the module column of an app
	that has since been uninstalled, and a v16 row can carry a module the site never had at all.
	A layer is anchored to a module, so there is nothing for such a source to convert into -- it
	is left in place instead, and reinstalling the app is what brings it back.
	"""
	return bool(module) and bool(frappe.db.exists("Module Def", module))


def archive_items(sidebar: str) -> list[frappe._dict]:
	return frappe.get_all(
		ARCHIVE_ITEM_DOCTYPE,
		filters={"parenttype": ARCHIVE_DOCTYPE, "parentfield": "items", "parent": sidebar},
		# no `key`: only `Sidebar Item` carries one. A pin can therefore only come from an
		# app-shipped Sidebar JSON, never from an archived row.
		fields=["name", "idx", *SIDEBAR_ITEM_FIELDS],
		order_by="idx asc",
	)


def write_user_layer(module: str, user: str, rows: list[dict]) -> None:
	"""Store one person's arrangement of `module`'s sidebar, over whatever its base is.

	No label and no icon, unlike the base. Those name the module for whoever resolves it, and
	the only names a fork carries are v16's own -- a workspace title, or `<title>-<user>`. A
	preference about arrangement should not quietly become a preference about what the module
	is called.
	"""
	doc = frappe.new_doc("Custom Sidebar")
	doc.module = module
	doc.user = user
	for row in rows:
		doc.append("sidebar_items", row)
	doc.insert(ignore_permissions=True)


def layer_rows(items: list[dict], below: list, dropped: set[str] | None = None) -> list[dict]:
	"""A merged list, expressed as an arrangement of what sits below it.

	An item already down there becomes a **reference**: the row says where it sits and nothing
	else, so the label, icon and link keep coming from below -- which is the difference between
	an arrangement that stays maintained and one frozen on the day it was converted. An item
	nothing below accounts for is carried **whole**, because there is nothing to refer to.

	`dropped` is named last and hidden: in a fork -- the whole list, as the person left it --
	an absence means *removed*, and saying so is the only way a delta can carry a removal.
	"""
	below_keys = {item_key(row) for row in below}
	kept = {item_key(item) for item in items}

	rows = []
	for item in items:
		key = item_key(item)
		added = key not in below_keys
		row = {field: item.get(field) for field in (SIDEBAR_ITEM_FIELDS if added else LINKED_IDENTITY_FIELDS)}
		# an unlinked row has no columns to be named by, so it is named by its key; a linked one's
		# columns *are* its identity, and a key stored beside them would survive a rename still
		# naming what the row used to point at
		row["key"] = None if is_linked(item) else key
		row["added"] = int(added)
		rows.append(row)

	for item in below:
		key = item_key(item)
		if key in kept or key not in (dropped or ()):
			continue
		row = {field: item.get(field) for field in LINKED_IDENTITY_FIELDS}
		row["key"] = None if is_linked(item) else key
		row["hidden"] = 1
		rows.append(row)

	return rows
