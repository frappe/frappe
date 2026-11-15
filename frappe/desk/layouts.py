# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Workspace layouts: changes to a workspace's default, each with a condition.

Every layout whose condition holds for the user applies, weakest first: other apps (by app name),
the workspace's own app, the site, then the user's own. A stronger layout wins a clash, and a hide
from any layout wins over every move and resize.

`changes` is `{add, move, resize, hide}`, keyed by block id:

    add:    [{"after": id | None, "in": id?, "block": {...}}]
    move:   [{"id": id, "after": id | None, "in": id?}]
    resize: {id: cols}, or {id: {col, row}} for a block with a height
    hide:   [id]

`after: None` is the top. A missing or hidden anchor puts the block at the end. `in` names a
container, a Card, to reach inside it.
"""

import hashlib
import time
from json import loads

import frappe
from frappe import _

LAYOUTS_KEY = "workspace_layouts"
USER_LAYOUTS_KEY = "workspace_user_layouts"
PAGES_KEY = "workspace_merged_pages"
CONDITIONS_KEY = "workspace_layout_conditions"
CONDITION_TTL = 600

# old blocks name their widget row by label
LABELLED_BLOCKS = ("chart", "number_card", "shortcut", "card", "quick_list", "custom_block", "onboarding")

OTHER_APP, OWNER_APP, SITE, USER = range(4)


# Block ids


def block_id(block: dict) -> str:
	"""A widget block's id is its widget; an old block's its label; text keeps its own random id."""
	block_type = block.get("type")
	data = block.get("data") or {}
	if block_type == "widget":
		return short_hash(f"widget:{data.get('widget')}")
	if block_type in LABELLED_BLOCKS:
		return short_hash(f"{block_type}:{data.get(f'{block_type}_name')}")
	return block.get("id") or frappe.generate_hash(length=10)


def item_id(container_id: str, widget: str) -> str:
	return short_hash(f"{container_id}:{widget}")


def short_hash(text: str) -> str:
	return hashlib.sha1(text.encode()).hexdigest()[:10]


def with_ids(content: list) -> list:
	return [{**block, "id": block_id(block)} for block in content]


# The page a user gets


def merged_content(doc, layouts: list[dict]) -> list:
	"""The workspace's default with `layouts` applied, shared by every user with the same set."""
	key = "|".join([doc.name, short_hash(doc.content or ""), *(layout["name"] for layout in layouts)])
	return frappe.cache.hget(
		PAGES_KEY, key, lambda: merge(loads(doc.content or "[]"), [layout["changes"] for layout in layouts])
	)


def matched_layouts(doc, until: str | None = None) -> list[dict]:
	"""The layouts of `doc` that apply to the session user, weakest first.

	`until` names a layout to stop at: it and the weaker ones that apply, whatever its own condition.
	"""
	layouts = sorted(workspace_layouts(doc.name), key=lambda layout: strength(layout, owner_app(doc)))
	matched = []
	for layout in layouts:
		if layout["name"] == until:
			return [*matched, layout]
		if condition_holds(layout["condition"]):
			matched.append(layout)
	return matched


def layouts_under(doc, layout: dict) -> list[dict]:
	"""The layouts weaker than `layout` that apply to the session user, weakest first."""
	owner = owner_app(doc)
	return [
		match
		for match in matched_layouts(doc)
		if match["name"] != layout.get("name") and strength(match, owner) < strength(layout, owner)
	]


def workspace_layouts(workspace: str) -> list[dict]:
	shared = frappe.cache.hget(
		LAYOUTS_KEY, workspace, lambda: load_layouts({"workspace": workspace, "user": ""})
	)
	own = frappe.cache.hget(
		USER_LAYOUTS_KEY, frappe.session.user, lambda: load_layouts({"user": frappe.session.user})
	)
	return shared + [layout for layout in own if layout["workspace"] == workspace]


def load_layouts(filters: dict) -> list[dict]:
	fields = ["name", "workspace", "layout_name", "module", "user", "condition", "changes"]
	layouts = frappe.get_all("Workspace Layout", filters=filters, fields=fields, order_by="name")
	for layout in layouts:
		layout["changes"] = frappe.parse_json(layout["changes"]) or {}
	return layouts


def owner_app(doc) -> str | None:
	return frappe.local.module_app.get(frappe.scrub(doc.module)) if doc.module else None


def strength(layout: dict, owner: str | None) -> tuple:
	"""Sorts weakest first. A site's edit, which has no condition, is its strongest site layout."""
	if layout["user"]:
		return (USER,)
	if not layout["module"]:
		return (SITE, not layout["condition"], layout["layout_name"] or "")
	app = frappe.local.module_app.get(frappe.scrub(layout["module"])) or ""
	if app == owner:
		return (OWNER_APP, "", layout["layout_name"] or "")
	return (OTHER_APP, app, layout["layout_name"] or "")


def clear_caches(workspace: str | None = None, user: str | None = None, all_users: bool = False):
	if workspace:
		frappe.cache.hdel(LAYOUTS_KEY, workspace)
	if all_users:
		frappe.cache.delete_value(USER_LAYOUTS_KEY)
	elif user:
		frappe.cache.hdel(USER_LAYOUTS_KEY, user)
	frappe.cache.delete_value([PAGES_KEY, CONDITIONS_KEY])


# Conditions


def condition_holds(expression: str | None) -> bool:
	if not expression:
		return True
	user = frappe.session.user
	cached = frappe.cache.hget(CONDITIONS_KEY, user) or {}
	if cached.get("at", 0) < time.time() - CONDITION_TTL:
		cached = {"at": time.time(), "results": {}}
	results = cached["results"]
	if expression not in results:
		results[expression] = evaluate(expression)
		frappe.cache.hset(CONDITIONS_KEY, user, cached)
	return results[expression]


def evaluate(expression: str) -> bool:
	"""Whether a layout's condition holds for the session user. One that raises counts as false."""
	try:
		return bool(frappe.safe_eval(expression, eval_globals={"frappe": condition_namespace()}))
	except Exception:
		frappe.log_error(_("Workspace layout condition failed"), message=expression)
		return False


def condition_namespace():
	"""All a condition can read: who the user is and how the site is set up."""
	return frappe._dict(
		get_roles=frappe.get_roles,
		get_installed_apps=frappe.get_installed_apps,
		get_system_settings=frappe.get_system_settings,
		db=frappe._dict(
			get_single_value=frappe.db.get_single_value,
			exists=frappe.db.exists,
			get_value=frappe.db.get_value,
		),
		session=frappe._dict(user=frappe.session.user),
		defaults=frappe._dict(get_user_default=frappe.defaults.get_user_default),
	)


# Merging


def merge(content: list, changes_list: list[dict]) -> list:
	"""`content` with each layout's changes applied in order, hides last."""
	blocks = [dict(block) for block in with_ids(content)]
	hidden = {block for changes in changes_list for block in changes.get("hide") or []}
	if hidden - {block["id"] for block in blocks}:
		for block in blocks:
			open_container(block)

	for changes in changes_list:
		for entry in changes.get("add") or []:
			add(blocks, entry, hidden)
		for entry in changes.get("move") or []:
			move(blocks, entry, hidden)
		for block_id_, size in (changes.get("resize") or {}).items():
			if block := find(blocks, block_id_):
				block["data"] = {**block["data"], **(size if isinstance(size, dict) else {"col": size})}

	return drop_hidden(blocks, hidden)


def add(blocks: list, entry: dict, hidden: set):
	siblings = siblings_of(blocks, entry.get("in"))
	if siblings is None:
		return
	block = new_item(entry["in"], entry["block"]) if entry.get("in") else {**entry["block"]}
	block["id"] = block.get("id") or block_id(block)
	if any(sibling["id"] == block["id"] for sibling in siblings):
		return
	place(siblings, block, entry.get("after"), hidden)


def new_item(container_id: str, block: dict) -> dict:
	widget = block["data"]["widget"]
	return {"id": item_id(container_id, widget), "widget": widget}


def move(blocks: list, entry: dict, hidden: set):
	siblings = siblings_of(blocks, entry.get("in"))
	block = find(siblings or [], entry["id"])
	if block:
		siblings.remove(block)
		place(siblings, block, entry.get("after"), hidden)


def place(siblings: list, block: dict, after: str | None, hidden: set):
	ids = [sibling["id"] for sibling in siblings]
	if after is None:
		siblings.insert(0, block)
	elif after in ids and after not in hidden:
		siblings.insert(ids.index(after) + 1, block)
	else:
		siblings.append(block)


def siblings_of(blocks: list, container_id: str | None) -> list | None:
	"""The top-level blocks, or the items inside a container."""
	if not container_id:
		return blocks
	container = find(blocks, container_id)
	return open_container(container) if container else None


def open_container(block: dict) -> list | None:
	"""A container block's items as `{id, widget}`, read from its widget the first time."""
	data = block.get("data") or {}
	if "items" not in data:
		children = container_children(data.get("widget")) if block.get("type") == "widget" else None
		if children is None:
			return None
		block["data"] = data = {
			**data,
			"items": [{"id": item_id(block["id"], c), "widget": c} for c in children],
		}
	return data["items"]


def container_children(widget_name: str | None) -> list[str] | None:
	from frappe.desk.widgets import get, get_types

	widget = get(widget_name) if widget_name else None
	if not widget or not get_types()[widget.widget.type]["child_type"]:
		return None
	return [row["widget"] for row in widget.config.get("widgets") or []]


def find(blocks: list, block_id_: str) -> dict | None:
	return next((block for block in blocks if block["id"] == block_id_), None)


def drop_hidden(blocks: list, hidden: set) -> list:
	kept = []
	for block in blocks:
		if block["id"] in hidden:
			continue
		if "items" in (block.get("data") or {}):
			items = [item for item in block["data"]["items"] if item["id"] not in hidden]
			block["data"] = {**block["data"], "items": items}
		kept.append(block)
	return kept


# Saving


def diff(base: list, page: list, visible: set) -> dict:
	"""The changes that turn `base` into `page`, the page an editor drew.

	A block of `base` the editor could not see (not in `visible`) is left where it is, never hidden.
	"""
	base_by_id = {block["id"]: block for block in base}
	page_ids = [block["id"] for block in page]
	changes = {"add": [], "move": [], "resize": {}, "hide": []}
	changes["hide"] = [b["id"] for b in base if b["id"] not in page_ids and b["id"] in visible]

	for index, block in enumerate(page):
		after = page_ids[index - 1] if index else None
		old = base_by_id.get(block["id"])
		if old is None:
			changes["add"].append({"after": after, "block": block})
		elif text_changed(old, block):
			changes["hide"].append(block["id"])
			changes["add"].append({"after": after, "block": {**block, "id": frappe.generate_hash(length=10)}})
		elif size_of(old) != size_of(block):
			changes["resize"][block["id"]] = size_of(block)

	changes["move"] = moves(base, page, changes)
	return {key: value for key, value in changes.items() if value}


def moves(base: list, page: list, changes: dict) -> list:
	"""The fewest moves that put the blocks both share in the page's order, else every block."""
	base_ids = [block["id"] for block in base]
	page_ids = [block["id"] for block in page]
	shared = [block_id_ for block_id_ in page_ids if block_id_ in base_ids]
	kept = set(longest_common_order([i for i in base_ids if i in shared], shared))
	few = [move_entry(page_ids, i) for i in shared if i not in kept]
	if order_matches(base, {**changes, "move": few}, page_ids):
		return few
	return [move_entry(page_ids, i) for i in page_ids]


def move_entry(page_ids: list, block_id_: str) -> dict:
	index = page_ids.index(block_id_)
	return {"id": block_id_, "after": page_ids[index - 1] if index else None}


def order_matches(base: list, changes: dict, page_ids: list) -> bool:
	merged = [block["id"] for block in merge(base, [changes])]
	return [i for i in merged if i in page_ids] == page_ids


def longest_common_order(first: list, second: list) -> list:
	lengths = [[0] * (len(second) + 1) for _ in range(len(first) + 1)]
	for i, a in enumerate(first):
		for j, b in enumerate(second):
			lengths[i + 1][j + 1] = lengths[i][j] + 1 if a == b else max(lengths[i][j + 1], lengths[i + 1][j])
	common, i, j = [], len(first), len(second)
	while i and j:
		if first[i - 1] == second[j - 1]:
			common.append(first[i - 1])
			i, j = i - 1, j - 1
		elif lengths[i - 1][j] >= lengths[i][j - 1]:
			i -= 1
		else:
			j -= 1
	return common[::-1]


def size_of(block: dict) -> int | dict:
	data = block.get("data") or {}
	return {"col": data.get("col"), "row": data["row"]} if data.get("row") else data.get("col")


def text_changed(old: dict, new: dict) -> bool:
	"""A heading or paragraph whose words changed. A widget's own content lives on the Widget."""
	if new.get("type") == "widget" or new.get("type") in LABELLED_BLOCKS:
		return False
	return old.get("type") != new.get("type") or words_of(old) != words_of(new)


def words_of(block: dict) -> dict:
	return {key: value for key, value in (block.get("data") or {}).items() if key not in ("col", "row")}
