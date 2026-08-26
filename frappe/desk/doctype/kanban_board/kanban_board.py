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
		from frappe.types import DF

		columns: DF.Table[KanbanBoardColumn]
		field_name: DF.Literal[None]
		fields: DF.Code | None
		filters: DF.Code | None
		kanban_board_name: DF.Data
		private: DF.Check
		reference_doctype: DF.Link
		show_labels: DF.Check
	# end: auto-generated types

	def validate(self):
		self.validate_column_name()

	def on_change(self):
		frappe.clear_cache(doctype=self.reference_doctype)
		clear_user_settings_cache(self.reference_doctype)

	def before_insert(self):
		for column in self.columns:
			column.order = get_order_for_column(self, column.column_name)

	def validate_column_name(self):
		for column in self.columns:
			if not column.column_name:
				frappe.msgprint(_("Column Name cannot be empty"), raise_exception=True)


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
		fields=["name", "filters", "reference_doctype", "private"],
		filters={"reference_doctype": doctype},
	)


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
	board.check_permission("read")
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
	doc.check_permission("write")
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
	doc.check_permission("write")
	for col in doc.columns:
		if column_title == col.column_name:
			col.status = status

	doc.save()
	return doc.columns


@frappe.whitelist()
def update_order(board_name: str, order: str | dict):
	"""Save the order of cards in columns"""
	board = frappe.get_doc("Kanban Board", board_name)
	# Card ordering only requires read access to the board plus write access to the
	# underlying records, so teammates who aren't the board owner (write is if_owner)
	# can still reorder cards on a shared board.
	board.check_permission("read")
	doctype = board.reference_doctype
	updated_cards = []

	if not frappe.has_permission(doctype, "write"):
		# Return board data from db
		return board, updated_cards

	fieldname = board.field_name
	order_dict = frappe.parse_json(order)

	for col_name, cards in order_dict.items():
		for card in cards:
			column = frappe.get_value(doctype, {"name": card}, fieldname)
			if column != col_name:
				frappe.set_value(doctype, card, fieldname, col_name)
				updated_cards.append(dict(name=card, column=col_name))

		for column in board.columns:
			if column.column_name == col_name:
				column.order = json.dumps(cards)

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
	# Card ordering only requires read access to the board plus write access to the
	# underlying records; see update_order for why this isn't board-write.
	board.check_permission("read")
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
			col_order = frappe.parse_json(col.order)
			col_idx = i

	return col_order, col_idx


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
	# Card ordering only requires read access to the board plus write access to the
	# underlying records; see update_order for why this isn't board-write.
	board.check_permission("read")

	frappe.has_permission(board.reference_doctype, "write", throw=True)

	col_order, col_idx = get_kanban_column_order_and_index(board, colname)
	col_order.insert(0, docname)

	board.columns[col_idx].order = frappe.as_json(col_order)

	saved = board.save(ignore_permissions=True)
	publish_kanban_board_update(saved)
	return saved


@frappe.whitelist()
def quick_kanban_board(doctype: str, board_name: str, field_name: str, project: str | None = None):
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
	board.check_permission("write")
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
	board.check_permission("write")

	for column in board.columns:
		if column.column_name == column_name:
			column.indicator = indicator

	board.save()
	return board


@frappe.whitelist()
def save_settings(board_name: str, settings: str | dict) -> Document:
	settings = frappe.parse_json(settings)
	doc = frappe.get_doc("Kanban Board", board_name)
	doc.check_permission("write")

	fields = settings["fields"]
	if not isinstance(fields, str):
		fields = json.dumps(fields)

	doc.fields = fields
	doc.show_labels = settings["show_labels"]
	doc.save()

	resp = doc.as_dict()
	resp["fields"] = frappe.parse_json(resp["fields"])

	return resp
