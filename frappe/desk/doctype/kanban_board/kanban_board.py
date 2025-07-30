# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from time import sleep
from urllib import request
from frappe.integrations.utils import make_post_request
import frappe
from frappe import _
from frappe.model.document import Document
from datetime import datetime

# Configurar el nivel de log para asegurar que los mensajes de debug se muestren
frappe.logger("debug").setLevel("DEBUG")
frappe.logger("debug").info("✅ Configuración de logging para Kanban Board activada")


class KanbanBoard(Document):
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
        frappe.cache.delete_keys("_user_settings")

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
def get_kanban_boards(doctype):
    """Get Kanban Boards for doctype to show in List View"""
    return frappe.get_list(
        "Kanban Board",
        fields=["name", "filters", "reference_doctype", "private"],
        filters={"reference_doctype": doctype},
    )


@frappe.whitelist()
def add_column(board_name, column_title):
    """Adds new column to Kanban Board"""
    doc = frappe.get_doc("Kanban Board", board_name)
    for col in doc.columns:
        if column_title == col.column_name:
            frappe.throw(_("Column <b>{0}</b> already exist.").format(column_title))

    doc.append("columns", dict(column_name=column_title))
    doc.save()
    return doc.columns


@frappe.whitelist()
def archive_restore_column(board_name, column_title, status):
    """Set column's status to status"""
    doc = frappe.get_doc("Kanban Board", board_name)
    for col in doc.columns:
        if column_title == col.column_name:
            col.status = status

    doc.save()
    return doc.columns


def order_column_by_project_order(project_ordered, projects_to_order):
    project_index_map = {}
    for index, project in enumerate(project_ordered):
        project_index_map[project["name"]] = index

    ordered_projects = {}
    for column, project_list in projects_to_order.items():
        sorted_project_list = sorted(
            project_list, key=lambda project: project_index_map.get(project, -1)
        )
        ordered_projects[column] = sorted_project_list

    return ordered_projects


@frappe.whitelist()
def update_order(board_name, order):
	"""Save the order of cards in columns"""
	board = frappe.get_doc("Kanban Board", board_name)
	doctype = board.reference_doctype
	updated_cards = []

	if not frappe.has_permission(doctype, "write"):
		# Return board data from db
		return board, updated_cards

	fieldname = board.field_name
	order_dict = json.loads(order)

	for col_name, cards in order_dict.items():
		for card in cards:
			column = frappe.get_value(doctype, {"name": card}, fieldname)
			if column != col_name:
				frappe.set_value(doctype, card, fieldname, col_name)
				updated_cards.append(dict(name=card, column=col_name))

		for column in board.columns:
			if column.column_name == col_name:
				column.order = json.dumps(cards)

	return board.save(ignore_permissions=True), updated_cards

@frappe.whitelist()
def update_order_for_single_card(board_name, docname, from_colname, to_colname, old_index, new_index):
    """Save the order of cards in columns"""
    frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Moving card {docname} from {from_colname} to {to_colname}, old_index: {old_index}, new_index: {new_index}")
    
    board = frappe.get_doc("Kanban Board", board_name)
    doctype = board.reference_doctype

    frappe.has_permission(doctype, "write", throw=True)

    fieldname = board.field_name
    old_index = frappe.parse_json(old_index)
    new_index = frappe.parse_json(new_index)

    # save current order and index of columns to be updated
    from_col_order, from_col_idx = get_kanban_column_order_and_index(board, from_colname)
    to_col_order, to_col_idx = get_kanban_column_order_and_index(board, to_colname)

    user = board.modified_by
    if doctype == "Project":
        create_status_shanged_comment(from_colname, to_colname, docname, user)
    
    if from_colname == to_colname:
        from_col_order = to_col_order

    if from_col_order and len(from_col_order) > 0:
        try:
            if old_index >= len(from_col_order):
                old_index = from_col_order.index(docname)

            to_col_order.insert(new_index, from_col_order.pop(old_index))
        except ValueError:
            frappe.logger("debug").info("[KANBAN SINGLE CARD] docname no se encuentra en from_col_order.")
        except IndexError as e:
            frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Error: {e}")

    # Special handling for Project doctype
    if doctype == "Project" and to_colname in ["In queue", "In parking"]:
        frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Special handling for Project with status '{to_colname}'")
        
        # Get the correctly sorted projects
        projects_ordered = get_projects_ordered_by_queue_position_and_appointment_date()
        
        # Get sorted order for the destination column
        sorted_cards = [p['name'] for p in projects_ordered if p.get('status') == to_colname]
        
        # Make sure the moved card is in the list
        if docname not in sorted_cards:
            frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Card {docname} not found in sorted order, adding it")
            # Actualizamos el status del proyecto en la base de datos para asegurar que aparezca en la columna correcta
            frappe.db.set_value("Project", docname, "status", to_colname)
            # Añadimos la tarjeta al final del orden calculado
            sorted_cards.append(docname)
        
        # Verificamos si hay tarjetas en el frontend que no estén en nuestro orden calculado
        missing_cards = [card for card in to_col_order if card not in sorted_cards and card != docname]
        if missing_cards:
            frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Found {len(missing_cards)} cards in frontend not in sorted order: {missing_cards}")
            # Añadimos las tarjetas faltantes al final del orden calculado
            sorted_cards.extend(missing_cards)
            
        # Verificar si hay proyectos en la base de datos con este estado que no estén en nuestro orden calculado
        projects_with_status = frappe.get_all("Project", filters={"status": to_colname}, fields=["name"])
        db_project_names = [p.name for p in projects_with_status]
        
        # Encontrar proyectos en la base de datos que no estén en nuestro orden calculado
        missing_from_sorted = [p for p in db_project_names if p not in sorted_cards]
        if missing_from_sorted:
            frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Found {len(missing_from_sorted)} projects in database with status '{to_colname}' not in sorted order: {missing_from_sorted}")
            # Añadir estos proyectos al final de nuestro orden calculado
            sorted_cards.extend(missing_from_sorted)
        
        frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Original to_col_order: {to_col_order}")
        frappe.logger("debug").info(f"[KANBAN SINGLE CARD] Sorted order for '{to_colname}': {sorted_cards}")
        
        # Use the sorted order for the destination column
        to_col_order = sorted_cards
    
    # save updated order
    board.columns[from_col_idx].order = frappe.as_json(from_col_order)
    board.columns[to_col_idx].order = frappe.as_json(to_col_order)
    board.save(ignore_permissions=True)

    # update changed value in doc
    frappe.set_value(doctype, docname, fieldname, to_colname)

    return board


def create_status_shanged_comment(from_colname, to_colname, docname, user):
    if from_colname != to_colname:
        comment = frappe.new_doc("Comment")
        comment.update(
            {
                "comment_type": "Comment",
                "reference_doctype": "Project",
                "reference_name": docname,
                "comment_email": "",
                "comment_by": "",
                "content": '<div class="ql-editor read-mode"><p>Project updated. From: '
                + from_colname
                + " TO: "
                + to_colname
                + ". Modified by: "
                + user
                + "</p></div>",
            }
        )
        comment.insert(ignore_permissions=True)


def get_kanban_column_order_and_index(board, colname):
    for i, col in enumerate(board.columns):
        if col.column_name == colname:
            col_order = frappe.parse_json(col.order)
            col_idx = i

    return col_order, col_idx


@frappe.whitelist()
def add_card(board_name, docname, colname):
    board = frappe.get_doc("Kanban Board", board_name)

    frappe.has_permission(board.reference_doctype, "write", throw=True)

    col_order, col_idx = get_kanban_column_order_and_index(board, colname)
    col_order.insert(0, docname)

    board.columns[col_idx].order = frappe.as_json(col_order)

    return board.save(ignore_permissions=True)


@frappe.whitelist()
def quick_kanban_board(doctype, board_name, field_name, project=None):
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
    # For Project doctype, use custom sorting for all columns during initial load
    if board.reference_doctype == "Project":
        # Get all projects with proper sorting
        projects_ordered = get_projects_ordered_by_queue_position_and_appointment_date()
        
        # Filter projects for this specific column
        column_projects = [p['name'] for p in projects_ordered if p.get('status') == colname]
        
        return frappe.as_json(column_projects)
    
    # For other doctypes, use the original logic
    filters = [[board.reference_doctype, board.field_name, "=", colname]]
    if board.filters:
        filters.append(frappe.parse_json(board.filters)[0])

    return frappe.as_json(frappe.get_list(board.reference_doctype, filters=filters, pluck="name"))


@frappe.whitelist()
def update_column_order(board_name, order):
    """Set the order of columns in Kanban Board"""
    board = frappe.get_doc("Kanban Board", board_name)
    order = json.loads(order)
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
def set_indicator(board_name, column_name, indicator):
    """Set the indicator color of column"""
    board = frappe.get_doc("Kanban Board", board_name)

    for column in board.columns:
        if column.column_name == column_name:
            column.indicator = indicator

    board.save()
    return board


@frappe.whitelist()
def save_settings(board_name: str, settings: str) -> Document:
    settings = json.loads(settings)
    doc = frappe.get_doc("Kanban Board", board_name)

    fields = settings["fields"]
    if not isinstance(fields, str):
        fields = json.dumps(fields)

    doc.fields = fields
    doc.show_labels = settings["show_labels"]
    doc.save()

    resp = doc.as_dict()
    resp["fields"] = frappe.parse_json(resp["fields"])

    return resp

@frappe.whitelist()
def call_freeze_queue_position_message(aws_url):
     return make_post_request(
                f"{aws_url}queue/send-freeze-queue-position-message",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )

@frappe.whitelist()
def refresh_kanban_project_order(board_name):
    """Refresh the order of Project kanban board columns based on queue_position and appointment_date"""
    try:
        board = frappe.get_doc("Kanban Board", board_name)
        
        if board.reference_doctype != "Project":
            return {"status": "error", "message": "This function only works for Project kanban boards"}
        
        # Get the correctly sorted projects
        projects_ordered = get_projects_ordered_by_queue_position_and_appointment_date()
        
        # Update each column's order
        for column in board.columns:
            column_projects = [p['name'] for p in projects_ordered if p.get('status') == column.column_name]
            column.order = frappe.as_json(column_projects)
            frappe.logger("debug").info(f"[KANBAN REFRESH] Updated column '{column.column_name}' with {len(column_projects)} projects")
        
        # Save the board
        board.save(ignore_permissions=True)
        
        frappe.logger("debug").info(f"[KANBAN REFRESH] Successfully refreshed kanban board: {board_name}")
        return {"status": "success", "message": f"Kanban board '{board_name}' order refreshed successfully"}
        
    except Exception as e:
        frappe.logger("debug").error(f"[KANBAN REFRESH] Error refreshing kanban board {board_name}: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def kanban_project_refresh(name:str):
    sleep(2)
    frappe.publish_realtime("kanban_project_refresh")
    frappe.publish_realtime("list_update",{"doctype":"Project", "user":"support@tvsgroup.nl", "name": name})
    return "called kanban_project_refresh"

@frappe.whitelist()
def force_refresh_kanban_order(board_name):
    """Endpoint para forzar la actualización del orden del tablero Kanban desde el frontend"""
    frappe.logger("debug").info(f"[KANBAN FORCE REFRESH] Forzando actualización del orden para el tablero: {board_name}")
    
    try:
        result = refresh_kanban_project_order(board_name)
        # Notificar a todos los clientes que deben actualizar su vista
        frappe.publish_realtime("kanban_board_update", {"board_name": board_name})
        return result
    except Exception as e:
        frappe.logger("debug").error(f"[KANBAN FORCE REFRESH] Error al forzar actualización: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==================== CUSTOM FUNCTIONS ====================

@frappe.whitelist()
def call_send_whatsapp_message(aws_url: str, project_name: str):
    project = frappe.get_doc('Project', project_name)

    return make_post_request(
        f"{aws_url}/send-after-remote-diagnose-message",
        headers={"Content-Type":"application/json"},
        data=json.dumps({
            "phone_number": project.custom_customers_phone_number,
            "project_name": project_name
        })
    )
