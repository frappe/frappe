# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.utils.user_settings import clear_user_settings_cache
from frappe.utils import cint


class KanbanBoard(Document):
	_DOCTYPE_NAME = "Kanban Board"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.kanban_board_column.kanban_board_column import KanbanBoardColumn
		from frappe.desk.doctype.kanban_board_field.kanban_board_field import KanbanBoardField
		from frappe.desk.doctype.kanban_board_group_field.kanban_board_group_field import (
			KanbanBoardGroupField,
		)
		from frappe.types import DF

		card_fields: DF.Table[KanbanBoardField]
		columns: DF.Table[KanbanBoardColumn]
		field_name: DF.Literal[None]
		fields: DF.Code | None
		filters: DF.Code | None
		footer_date_field: DF.Literal["Modified", "Creation"]
		group_by_fields: DF.Table[KanbanBoardGroupField]
		image_field: DF.Autocomplete | None
		is_standard: DF.Literal["No", "Yes"]
		kanban_board_name: DF.Data
		preview_fields: DF.Table[KanbanBoardField]
		private: DF.Check
		reference_doctype: DF.Link
		show_assigned_to: DF.Check
		show_tags_on_card: DF.Check
		show_labels: DF.Check
		title_field: DF.Autocomplete | None
		use_kanban_v2: DF.Check
	# end: auto-generated types

	def validate(self):
		self.validate_standard_board_rules()
		self.validate_private_toggle_permission()
		self.validate_column_name()

	def validate_standard_board_rules(self):
		"""Standard boards are fixture-backed: only Administrator in developer
		mode can create/edit them, and standard boards cannot be converted by
		non-standard edits."""
		self.is_standard = self.is_standard or "No"

		if (
			self.is_standard == "No"
			and frappe.db.get_value("Kanban Board", self.name, "is_standard") == "Yes"
		):
			frappe.throw(_("Cannot edit a standard Kanban Board. Please duplicate and create a new board"))

		if self.is_standard == "Yes":
			self.validate_standard_board()

	def validate_standard_board(self):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can save a standard Kanban Board. Please rename and save."))

		if not cint(getattr(frappe.local.conf, "developer_mode", 0)):
			frappe.throw(_("Standard Kanban Boards can only be created in developer mode."))

	def validate_private_toggle_permission(self):
		"""Only the owner or Administrator can toggle private on existing boards."""
		if self.is_new() or not self.has_value_changed("private"):
			return

		user = frappe.session.user
		if user == "Administrator" or user == self.owner:
			return

		frappe.throw(
			_("Only the board owner or Administrator can change Private."),
			frappe.PermissionError,
		)

	def on_change(self):
		frappe.clear_cache(doctype=self.reference_doctype)
		clear_user_settings_cache(self.reference_doctype)

	def on_trash(self):
		if self.is_standard == "Yes":
			if (
				not cint(getattr(frappe.local.conf, "developer_mode", 0))
				and not frappe.flags.in_migrate
				and not frappe.flags.in_patch
			):
				frappe.throw(_("You are not allowed to delete Standard Kanban Board"))

	def before_insert(self):
		for column in self.columns:
			column.order = get_order_for_column(self, column.column_name)
		self.seed_title_and_image_fields()
		self.seed_card_fields()
		self.seed_preview_fields()
		self.seed_group_by_fields()

	def seed_title_and_image_fields(self):
		"""Pre-fill title and image fields for a new board. Old boards leave these
		empty and the client falls back to the doctype's title/image field."""
		if not self.reference_doctype:
			return
		if not self.title_field:
			self.title_field = default_title_field(self.reference_doctype)
		if not self.image_field:
			self.image_field = default_image_field(self.reference_doctype)

	def seed_card_fields(self):
		"""Pre-fill the card fields for a new board with sensible defaults (the
		doctype's in-list-view / mandatory fields). Only runs when the board is
		created and no card fields were configured; the new Kanban board falls
		back to the same auto-picking when this table is left empty."""
		self._seed_field_table("card_fields", default_card_fieldnames(self.reference_doctype))

	def seed_preview_fields(self):
		"""Pre-fill the hover-preview fields for a new board from the doctype's
		preview-api fields (`in_preview`, else mandatory). Empty on old boards;
		runtime then falls back: preview fields → preview api → card fields."""
		self._seed_field_table("preview_fields", default_preview_fieldnames(self.reference_doctype))

	def seed_group_by_fields(self):
		"""Pre-fill the group-by options for a new board with the doctype's Select
		fields (minus the column field, which already forms the board's columns).
		No runtime fallback — an empty table simply hides the Group button, so the
		user curates the list (add Link fields like Supplier, remove noise)."""
		self._seed_field_table("group_by_fields", default_group_by_fieldnames(self.reference_doctype))

	def _seed_field_table(self, tablefield: str, fieldnames: list[str]):
		if self.get(tablefield) or not self.reference_doctype:
			return
		meta = frappe.get_meta(self.reference_doctype)
		# Don't repeat the column field, title, or image — those live elsewhere on the card.
		skip = {self.field_name, self.title_field, self.image_field}
		for fieldname in fieldnames:
			if fieldname in skip:
				continue
			df = meta.get_field(fieldname)
			self.append(
				tablefield,
				{"fieldname": fieldname, "label": df.label if df else fieldname},
			)

	def validate_column_name(self):
		for column in self.columns:
			if not column.column_name:
				frappe.msgprint(_("Column Name cannot be empty"), raise_exception=True)


def default_title_field(doctype: str) -> str:
	"""Card title field for a new board: doctype title_field when it is Data,
	else the first Data field, else name (ID). Only name and Data are allowed."""
	meta = frappe.get_meta(doctype)
	title = meta.get("title_field")
	if title:
		df = meta.get_field(title)
		if df and df.fieldtype == "Data" and not df.hidden:
			return title
	for df in meta.fields:
		if df.fieldtype == "Data" and df.fieldname and not df.hidden:
			return df.fieldname
	return "name"


def default_image_field(doctype: str) -> str | None:
	"""Card image field for a new board: doctype image_field, else the first
	Attach Image field. None when the doctype has no image fields."""
	meta = frappe.get_meta(doctype)
	if meta.image_field:
		return meta.image_field
	images = meta.get_image_fields()
	return images[0].fieldname if images else None


def default_card_fieldnames(doctype: str) -> list[str]:
	"""Default fields to show on a card: the doctype's in-list-view fields,
	falling back to its mandatory fields. Skips layout/table/no-value fields.
	Mirrors the new Kanban board's client-side fallback."""
	from frappe.model import no_value_fields, table_fields

	meta = frappe.get_meta(doctype)

	def usable(df):
		return (
			df.fieldtype not in no_value_fields
			and df.fieldtype not in table_fields
			and df.fieldtype != "Check"
			and not df.hidden
		)

	fieldnames = [df.fieldname for df in meta.fields if df.in_list_view and usable(df)]
	if not fieldnames:
		fieldnames = [df.fieldname for df in meta.fields if df.reqd and usable(df)]
	return fieldnames[:6]


def default_preview_fieldnames(doctype: str) -> list[str]:
	"""Default fields for the hover preview — same source as
	`frappe.desk.link_preview.get_preview_data`: `in_preview`, else mandatory.
	Skips title/image (they head the preview) and layout/table/no-value fields.
	Runtime fallback when the board table is empty: preview fields → these →
	card fields (see the kanban_v2 compute_preview_fields logic)."""
	from frappe.model import no_value_fields, table_fields

	meta = frappe.get_meta(doctype)
	skip = {meta.get_title_field(), meta.image_field, "name"}

	def usable(df):
		return (
			df.fieldtype not in no_value_fields
			and df.fieldtype not in table_fields
			and df.fieldtype != "Check"
			and not df.hidden
			and df.fieldname not in skip
		)

	fieldnames = [df.fieldname for df in meta.fields if df.in_preview and usable(df)]
	if not fieldnames:
		fieldnames = [df.fieldname for df in meta.fields if df.reqd and usable(df)]
	return fieldnames[:6]


def default_group_by_fieldnames(doctype: str) -> list[str]:
	"""Group-by options to seed a new board: the doctype's Select fields. The
	column field is dropped by `_seed_field_table` (it already splits the board
	into columns)."""
	meta = frappe.get_meta(doctype)
	return [df.fieldname for df in meta.fields if df.fieldtype == "Select" and not df.hidden]


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	return f"""(`tabKanban Board`.private=0 or `tabKanban Board`.owner={frappe.db.escape(user)})"""


def has_permission(doc, ptype, user):
	if doc.private == 0 or user == "Administrator":
		return True

	if user == doc.owner:
		return True

	return False


@frappe.whitelist()
def get_kanban_boards(doctype: str):
	"""Get Kanban Boards for doctype to show in List View"""
	return frappe.get_list(
		"Kanban Board",
		fields=["name", "filters", "reference_doctype", "private", "is_standard", "use_kanban_v2"],
		filters={"reference_doctype": doctype},
	)


def ensure_kanban_board_permission(board: Document, ptype: str = "read") -> None:
	"""Enforce Kanban Board access (private boards are owner-only)."""
	frappe.has_permission("Kanban Board", ptype, doc=board, throw=True)


@frappe.whitelist()
@frappe.read_only()
def get_card_config(board_name: str) -> dict:
	"""Bits that decide how a card and its hover peek look: title/image fields,
	card fields, and preview fields (with optional icons and labels).

	The new Kanban polls this when returning to an already-open board, so it can
	pick up config edits without re-fetching the whole board document (whose
	column orders hold every card name and can be large).
	"""
	board = frappe.get_doc("Kanban Board", board_name)
	ensure_kanban_board_permission(board, "read")
	frappe.has_permission(board.reference_doctype, "read", throw=True)

	def _field_rows(rows):
		return [{"fieldname": f.fieldname, "label": f.label, "icon": f.icon} for f in rows]

	return {
		"title_field": board.title_field,
		"image_field": board.image_field,
		"show_assigned_to": board.show_assigned_to,
		"show_tags_on_card": board.show_tags_on_card,
		"footer_date_field": board.footer_date_field,
		"card_fields": _field_rows(board.card_fields),
		"preview_fields": _field_rows(board.preview_fields),
	}


# Paginated Kanban APIs — load cards in chunks instead of all at once.
#
# Before: opening Kanban loaded every card for every column (slow on large boards).
# Now:
#   get_kanban_board_data  — first open: count per column + first 50 cards each.
#   get_kanban_column_page — load more for one column when user scrolls.
#
# Uses the same filters and fields as list view. Client sends kanban_start and
# kanban_page_length to ask for the next chunk.
def get_kanban_reportview_args():
	"""Read list-view style args from the request, plus Kanban paging fields."""
	from frappe.desk.reportview import clean_params, validate_args

	data = frappe._dict(frappe.local.form_dict)
	board_name = data.pop("board_name", None)
	column_name = data.pop("column_name", None)
	kanban_start = cint(data.pop("kanban_start", data.pop("start", 0)))
	kanban_page_length = cint(data.pop("kanban_page_length", 50)) or 50

	if not board_name:
		frappe.throw(_("Board name is required"), title=_("Kanban Board"))

	clean_params(data)
	validate_args(data)
	return board_name, column_name, kanban_start, kanban_page_length, data


def get_kanban_board_context(board_name: str):
	"""Load the board and return active (non-archived) column names."""
	board = frappe.get_doc("Kanban Board", board_name)
	ensure_kanban_board_permission(board, "read")
	frappe.has_permission(board.reference_doctype, "read", throw=True)
	column_names = [col.column_name for col in board.columns if col.status != "Archived"]
	return board, column_names


def merge_kanban_filters(board: Document, filters: list | None) -> list:
	"""Add board filters to the request without duplicating them."""
	merged = list(filters or [])
	if not board.filters:
		return merged

	board_filters = frappe.parse_json(board.filters)
	if not board_filters:
		return merged

	existing = {_kanban_filter_key(f) for f in merged}
	for filt in board_filters:
		if _kanban_filter_key(filt) not in existing:
			merged.append(filt)
	return merged


def _kanban_filter_key(filt):
	"""Simple key so we do not add the same filter twice."""

	def _hashable(value):
		if isinstance(value, list):
			return tuple(value)
		return value

	if isinstance(filt, (list, tuple)):
		parts = list(filt[:4]) if len(filt) >= 4 else list(filt)
		return tuple(_hashable(part) for part in parts)
	return (_hashable(filt),)


def column_filter(doctype: str, field_name: str, column_name: str, filters: list | None) -> list:
	"""Add a filter so we only get cards in this column."""
	return [*(filters or []), [doctype, field_name, "=", column_name]]


def fetch_kanban_column_cards(
	reportview_args,
	doctype: str,
	field_name: str,
	column_name: str,
	start: int,
	page_length: int,
):
	"""Load one page of cards for a column from the database."""
	from frappe.desk.reportview import compress, execute

	query_args = frappe._dict(reportview_args.copy())
	query_args.start = cint(start)
	query_args.page_length = cint(page_length)
	query_args.filters = column_filter(doctype, field_name, column_name, query_args.filters)
	data = execute(**query_args)
	return compress(data, args=query_args)


def get_kanban_column_counts(
	doctype: str, field_name: str, filters: list | None, column_names: list[str]
) -> dict[str, int]:
	"""Count cards in each column. If group-by fails, count each column separately."""
	counts = {name: 0 for name in column_names}
	if not column_names:
		return counts

	try:
		rows = frappe.get_list(
			doctype,
			filters=filters,
			group_by=field_name,
			fields=[f"{field_name} as name", {"COUNT": "*", "as": "_count"}],
			order_by=None,
			limit=0,
		)
		for row in rows:
			if row.name in counts:
				counts[row.name] = cint(row.get("_count", 0))
	except Exception:
		frappe.log_error(
			title="Kanban column count group-by failed",
			message=frappe.get_traceback(),
		)
		for column_name in column_names:
			counts[column_name] = frappe.db.count(
				doctype,
				filters=column_filter(doctype, field_name, column_name, filters),
			)
	return counts


@frappe.whitelist()
@frappe.read_only()
def get_kanban_board_data():
	"""First load: total per column + first page of cards (default 50 each).

	Example: 4 columns load 200 cards, not the entire board.
	"""
	board_name, _, _, kanban_page_length, reportview_args = get_kanban_reportview_args()
	board, column_names = get_kanban_board_context(board_name)
	doctype = board.reference_doctype
	field_name = board.field_name
	filters = merge_kanban_filters(board, reportview_args.filters)
	reportview_args.filters = filters

	counts = get_kanban_column_counts(doctype, field_name, filters, column_names)
	columns = {}

	for column_name in column_names:
		cards = fetch_kanban_column_cards(
			reportview_args, doctype, field_name, column_name, 0, kanban_page_length
		)
		columns[column_name] = {"total": counts.get(column_name, 0), "cards": cards}

	return {"columns": columns}


def validate_kanban_group_by(board, group_by: str):
	"""Reject group fields the board does not offer in the Group menu.

	`_assign` is allowed only when Show Assigned To is on; everything else must
	be listed in the board's Group By Fields (and still exist on the DocType).
	"""
	if group_by == "_assign":
		# Match client: missing/null defaults to on (cint(..., 1)).
		if not cint(board.show_assigned_to, 1):
			frappe.throw(_("Invalid group field"), title=_("Kanban Board"))
		return

	allowed = {row.fieldname for row in (board.group_by_fields or []) if row.fieldname}
	if group_by not in allowed or not frappe.get_meta(board.reference_doctype).get_field(group_by):
		frappe.throw(_("Invalid group field"), title=_("Kanban Board"))


@frappe.whitelist()
@frappe.read_only()
def get_kanban_group_values(board_name: str, group_by: str, filters: str | list | None = None):
	"""Swimlane values for a board: the distinct values of `group_by` across the
	board's cards (respecting board + runtime filters), most-populated first, with
	counts and a trailing "not set" bucket. Capped so a high-cardinality Link
	(Supplier, Customer) can't explode the board.
	"""
	from collections import Counter

	board, _ = get_kanban_board_context(board_name)
	doctype = board.reference_doctype
	validate_kanban_group_by(board, group_by)

	merged = merge_kanban_filters(board, frappe.parse_json(filters) if filters else None)
	limit = 20
	lanes = []
	unset = 0

	if group_by == "_assign":
		counter = Counter()
		# Bound the scan so large doctypes can't OOM workers. Counts past this
		# window are approximate; lane list is still the top assignees within it.
		assign_scan_limit = 5000
		for raw in frappe.get_all(doctype, filters=merged, pluck="_assign", limit=assign_scan_limit):
			users = frappe.parse_json(raw) if raw else []
			if users:
				for user in users:
					counter[user] += 1
			else:
				unset += 1
		lanes = [{"value": user, "label": user, "count": count} for user, count in counter.most_common(limit)]
	else:
		rows = frappe.get_all(
			doctype,
			filters=merged,
			fields=[f"{group_by} as value", {"COUNT": "*", "as": "_count"}],
			group_by=group_by,
			order_by="_count desc",
			limit=limit + 1,
		)
		for row in rows:
			value = row.get("value")
			count = cint(row.get("_count"))
			if value in (None, ""):
				unset += count
			else:
				lanes.append({"value": value, "label": value, "count": count})
		lanes = lanes[:limit]

	return {"lanes": lanes, "unset": unset}


@frappe.whitelist()
@frappe.read_only()
def get_kanban_column_page():
	"""Load the next chunk of cards for one column (scroll up or down).

	kanban_start = which card index to start from (0 = first card in column).
	"""
	board_name, column_name, kanban_start, kanban_page_length, reportview_args = get_kanban_reportview_args()
	if not column_name:
		frappe.throw(_("Column name is required"), title=_("Kanban Board"))

	board, column_names = get_kanban_board_context(board_name)
	if column_name not in column_names:
		frappe.throw(_("Invalid column"), title=_("Kanban Board"))

	doctype = board.reference_doctype
	field_name = board.field_name
	filters = merge_kanban_filters(board, reportview_args.filters)
	reportview_args.filters = filters
	col_filters = column_filter(doctype, field_name, column_name, filters)

	cards = fetch_kanban_column_cards(
		reportview_args, doctype, field_name, column_name, kanban_start, kanban_page_length
	)
	total = frappe.db.count(doctype, filters=col_filters)

	return {"total": total, "cards": cards}


@frappe.whitelist()
def add_column(board_name: str, column_title: str):
	"""Adds new column to Kanban Board"""
	doc = frappe.get_doc("Kanban Board", board_name)
	for col in doc.columns:
		if column_title == col.column_name:
			frappe.throw(_("Column <b>{0}</b> already exist.").format(column_title))

	doc.append("columns", dict(column_name=column_title))
	doc.save()
	return doc.columns


@frappe.whitelist()
def archive_restore_column(board_name: str, column_title: str, status: str):
	"""Set column's status to status"""
	doc = frappe.get_doc("Kanban Board", board_name)
	for col in doc.columns:
		if column_title == col.column_name:
			col.status = status

	doc.save()
	return doc.columns


@frappe.whitelist()
def update_order(board_name: str, order: str | dict, throw_on_no_write: bool = False):
	"""Save the order of cards in columns"""
	board = frappe.get_doc("Kanban Board", board_name)
	ensure_kanban_board_permission(board, "write")
	doctype = board.reference_doctype
	updated_cards = []

	if not frappe.has_permission(doctype, "write"):
		# The classic board syncs order on load even for users who can only READ the
		# reference doctype, so it must be able to no-op here (return the board unsaved
		# and let the client render). The new Kanban only calls this for an explicit
		# multi-move and passes throw_on_no_write, so a move that can't be saved
		# surfaces an error instead of silently sticking on screen.
		if frappe.parse_json(throw_on_no_write):
			frappe.has_permission(doctype, "write", throw=True)
		return board, updated_cards

	fieldname = board.field_name
	order_dict = frappe.parse_json(order)

	for col_name, cards in order_dict.items():
		# Saved column.order can still list deleted docs (classic board syncs full
		# order on load). Skip missing names and prune them from the stored order.
		valid_cards = []
		for card in cards:
			column = frappe.db.get_value(doctype, card, fieldname)
			if column != col_name:
				if not frappe.db.exists(doctype, card):
					continue
				frappe.set_value(doctype, card, fieldname, col_name)
				updated_cards.append(dict(name=card, column=col_name))
			valid_cards.append(card)

		for column in board.columns:
			if column.column_name == col_name:
				column.order = json.dumps(valid_cards)

	saved = board.save(ignore_permissions=True)
	publish_kanban_board_update(saved)
	return saved, updated_cards


@frappe.whitelist()
def update_order_for_single_card(
	board_name: str,
	docname: str,
	from_colname: str,
	to_colname: str,
	old_index: str | int | None = None,
	new_index: str | int | None = None,
	from_order: str | list | None = None,
	to_order: str | list | None = None,
):
	"""Save card order after drag.

	Send from_order and to_order when the client already has the full lists.
	Otherwise send old_index and new_index.
	"""
	board = frappe.get_doc("Kanban Board", board_name)
	ensure_kanban_board_permission(board, "write")
	doctype = board.reference_doctype

	frappe.has_permission(doctype, "write", throw=True)

	fieldname = board.field_name
	from_col_order, from_col_idx = get_kanban_column_order_and_index(board, from_colname)
	to_col_order, to_col_idx = get_kanban_column_order_and_index(board, to_colname)

	if from_order is not None and to_order is not None:
		from_col_order = frappe.parse_json(from_order)
		to_col_order = frappe.parse_json(to_order)
	else:
		old_index = frappe.parse_json(old_index)
		new_index = frappe.parse_json(new_index)

		if from_colname == to_colname:
			from_col_order = to_col_order

		if from_col_order:
			to_col_order.insert(new_index, from_col_order.pop(old_index))

	# save updated order
	board.columns[from_col_idx].order = frappe.as_json(from_col_order)
	board.columns[to_col_idx].order = frappe.as_json(to_col_order)
	saved = board.save(ignore_permissions=True)
	publish_kanban_board_update(saved)

	# update changed value in doc
	frappe.set_value(doctype, docname, fieldname, to_colname)

	return saved


def get_kanban_column_order_and_index(board, colname):
	"""Return parsed card-name order list and board.columns index for a column."""
	for i, col in enumerate(board.columns):
		if col.column_name == colname:
			return frappe.parse_json(col.order), i
	frappe.throw(_("Invalid column"), title=_("Kanban Board"))


def publish_kanban_board_update(board):
	"""Tell other open Kanban tabs to refresh column order."""
	frappe.publish_realtime(
		"kanban_board_update",
		{"board_name": board.name, "reference_doctype": board.reference_doctype},
		doctype=board.reference_doctype,
		after_commit=True,
	)


@frappe.whitelist()
def add_card(board_name: str, docname: str, colname: str):
	"""Prepend a new card to a column's saved order and notify other sessions."""
	board = frappe.get_doc("Kanban Board", board_name)
	ensure_kanban_board_permission(board, "write")

	frappe.has_permission(board.reference_doctype, "write", throw=True)

	col_order, col_idx = get_kanban_column_order_and_index(board, colname)
	col_order.insert(0, docname)

	board.columns[col_idx].order = frappe.as_json(col_order)

	saved = board.save(ignore_permissions=True)
	publish_kanban_board_update(saved)
	return saved


@frappe.whitelist()
def quick_kanban_board(
	doctype: str,
	board_name: str,
	field_name: str,
	project: str | None = None,
	use_kanban_v2: bool | None = None,
):
	"""Create new KanbanBoard quickly with default options"""

	doc = frappe.new_doc("Kanban Board")
	meta = frappe.get_meta(doctype)

	doc.kanban_board_name = board_name
	doc.reference_doctype = doctype
	doc.field_name = field_name

	if project:
		doc.filters = f'[["Task","project","=","{project}"]]'

	options = ""
	for field in meta.fields:
		if field.fieldname == field_name:
			options = field.options

	columns = []
	if options:
		columns = options.split("\n")

	for column in columns:
		if not column:
			continue
		doc.append("columns", dict(column_name=column))

	if doctype in ["Note", "ToDo"]:
		doc.private = 1

	# Explicitly convert to int to handle string/bool/int variants from JS
	if use_kanban_v2 is not None:
		doc.use_kanban_v2 = cint(use_kanban_v2)

	doc.save()
	return doc


def get_order_for_column(board, colname):
	filters = [[board.reference_doctype, board.field_name, "=", colname]]
	if board.filters and (parsed_filters := frappe.parse_json(board.filters)):
		filters.append(parsed_filters[0])

	return frappe.as_json(frappe.get_list(board.reference_doctype, filters=filters, pluck="name"))


@frappe.whitelist()
def update_column_order(board_name: str, order: str | list):
	"""Set the order of columns in Kanban Board"""
	board = frappe.get_doc("Kanban Board", board_name)
	order = frappe.parse_json(order)
	old_columns = board.columns
	new_columns = []

	for col in order:
		for column in list(old_columns):
			if col == column.column_name:
				new_columns.append(column)
				old_columns.remove(column)

	new_columns.extend(old_columns)

	board.columns = []
	for col in new_columns:
		board.append(
			"columns",
			dict(
				column_name=col.column_name,
				status=col.status,
				order=col.order,
				indicator=col.indicator,
			),
		)

	board.save()
	return board


@frappe.whitelist()
def set_indicator(board_name: str, column_name: str, indicator: str):
	"""Set the indicator color of column"""
	board = frappe.get_doc("Kanban Board", board_name)

	for column in board.columns:
		if column.column_name == column_name:
			column.indicator = indicator

	board.save()
	return board


@frappe.whitelist()
def save_settings(board_name: str, settings: str | dict) -> Document:
	settings = frappe.parse_json(settings) or {}
	doc = frappe.get_doc("Kanban Board", board_name)

	fields = settings.get("fields", [])
	if not isinstance(fields, str):
		fields = json.dumps(fields)

	doc.fields = fields
	if "show_labels" in settings:
		doc.show_labels = settings.get("show_labels")
	doc.save()

	resp = doc.as_dict()
	resp["fields"] = frappe.parse_json(resp["fields"])

	return resp
