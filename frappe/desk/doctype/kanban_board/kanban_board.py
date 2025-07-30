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
    
    # Special handling for Project doctype
    if doctype == "Project":
        frappe.logger("debug").info(f"[KANBAN UPDATE] Processing update_order for Project kanban board: {board_name}")
        
        # Get the correctly sorted projects for special columns
        special_order_statuses = ["In queue", "In parking"]
        projects_ordered = get_projects_ordered_by_queue_position_and_appointment_date()
        
        # Create a map of column name to sorted project names
        sorted_columns = {}
        for status in special_order_statuses:
            sorted_columns[status] = [p['name'] for p in projects_ordered if p.get('status') == status]
            frappe.logger("debug").info(f"[KANBAN UPDATE] Sorted order for '{status}': {sorted_columns[status]}")
            
        # Log the incoming order from frontend for comparison
        frappe.logger("debug").info(f"[KANBAN UPDATE] Order received from frontend: {order_dict}")
        
        # If order_dict is empty, we need to build it from the current board state
        if not order_dict:
            frappe.logger("debug").info("[KANBAN UPDATE] Order dict is empty, building from current board state")
            order_dict = {}
            for column in board.columns:
                try:
                    # Get the current order from the column
                    current_order = json.loads(column.order or '[]')
                    order_dict[column.column_name] = current_order
                    frappe.logger("debug").info(f"[KANBAN UPDATE] Current order for '{column.column_name}': {current_order}")
                except Exception as e:
                    frappe.logger("debug").info(f"[KANBAN UPDATE] Error parsing column order: {e}")
                    order_dict[column.column_name] = []
        
        # Primero, actualizar el estado de los proyectos según lo que viene del frontend
        # Esto asegura que los cambios recientes se apliquen primero
        for col_name, cards in order_dict.items():
            # Update the project status if it changed
            for card in cards:
                column = frappe.get_value(doctype, {"name": card}, fieldname)
                if column != col_name:
                    frappe.set_value(doctype, card, fieldname, col_name)
                    updated_cards.append(dict(name=card, column=col_name))
                    frappe.logger("debug").info(f"[KANBAN UPDATE] Updated card {card} status from {column} to {col_name}")
        
        # Después de actualizar todos los estados, refrescar la lista de proyectos ordenados
        # para incluir los cambios recientes
        if updated_cards:
            frappe.logger("debug").info(f"[KANBAN UPDATE] Cards were updated, refreshing ordered projects")
            projects_ordered = get_projects_ordered_by_queue_position_and_appointment_date()
            # Actualizar sorted_columns con la nueva información
            for status in special_order_statuses:
                sorted_columns[status] = [p['name'] for p in projects_ordered if p.get('status') == status]
                frappe.logger("debug").info(f"[KANBAN UPDATE] Refreshed sorted order for '{status}': {sorted_columns[status]}")
        
        # Ahora aplicar el orden a las columnas
        for col_name, cards in order_dict.items():
            # For special columns, use our sorted order instead of the order from the frontend
            if col_name in special_order_statuses and col_name in sorted_columns:
                # Obtener el estado actual de la base de datos para esta columna
                projects_with_status = frappe.get_all("Project", filters={"status": col_name}, fields=["name"])
                db_project_names = [p.name for p in projects_with_status]
                
                # Usar el orden calculado pero respetando el estado actual de la base de datos
                sorted_cards = [p for p in sorted_columns[col_name] if p in db_project_names]
                
                # Añadir cualquier proyecto que esté en la base de datos pero no en nuestro orden calculado
                missing_from_sorted = [p for p in db_project_names if p not in sorted_cards]
                if missing_from_sorted:
                    frappe.logger("debug").info(f"[KANBAN UPDATE] Adding {len(missing_from_sorted)} projects from database to sorted order for '{col_name}': {missing_from_sorted}")
                    sorted_cards.extend(missing_from_sorted)
                
                frappe.logger("debug").info(f"[KANBAN UPDATE] Original order for '{col_name}': {cards}")
                frappe.logger("debug").info(f"[KANBAN UPDATE] Applying sorted order to column '{col_name}': {sorted_cards}")
                
                # Update the column order with our sorted order
                for column in board.columns:
                    if column.column_name == col_name:
                        column.order = json.dumps(sorted_cards)
                        frappe.logger("debug").info(f"[KANBAN UPDATE] Applied sorted order to column '{col_name}': {sorted_cards}")
            else:
                # For other columns, keep the order as is
                for column in board.columns:
                    if column.column_name == col_name:
                        column.order = json.dumps(cards)
    else:
        # Standard behavior for non-Project doctypes
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

def get_projects_ordered_by_queue_position_and_appointment_date():
    """
    Orders project cards by queue_position and appointment_date for specific columns only.
    
    Requirements:
    - For "In queue" and "In parking" columns: sort by queue_position (ascending), then by appointment_date
    - For other columns: maintain original order
    - Database returns queue_position as string, so conversion to float is needed for proper sorting
    """
    frappe.logger("debug").info("[KANBAN DEBUG] Starting get_projects_ordered_by_queue_position_and_appointment_date()")
    
    projects = frappe.db.sql(
        """
        SELECT
            queue_position,
            name, status,
            appointment_date,
            status_modified
        FROM
            `tabProject`
        """,
        as_dict=True,
    )
    
    # Debug logging
    frappe.logger("debug").info(f"[KANBAN DEBUG] Total projects fetched: {len(projects)}")
    
    # Separate projects into two groups: those that need special ordering and those that don't
    special_order_statuses = ["In queue", "In parking"]
    special_order_projects = [p for p in projects if p.get('status') in special_order_statuses]
    regular_projects = [p for p in projects if p.get('status') not in special_order_statuses]
    
    frappe.logger("debug").info(f"[KANBAN DEBUG] Projects in special order statuses: {len(special_order_projects)}")
    frappe.logger("debug").info(f"[KANBAN DEBUG] Projects in regular statuses: {len(regular_projects)}")
    
    # Log all projects in special order statuses before sorting
    frappe.logger("debug").info(f"[KANBAN DEBUG] Projects in special order statuses before sorting:")
    for p in special_order_projects:
        frappe.logger("debug").info(f"[KANBAN DEBUG] {p.get('name')} - status: {p.get('status')}, queue_position: {p.get('queue_position')}, appointment_date: {p.get('appointment_date')}")
    
    def parse_queue_position(queue_pos):
        """Parse queue_position to float, handling edge cases"""
        if queue_pos is None or queue_pos == '' or queue_pos == 0:
            return 999999.0  # Put empty queue_position at the end
        
        try:
            # Cast queue_position to float for proper sorting
            return float(str(queue_pos).replace(',', '.'))  # Handle comma as decimal separator
        except (ValueError, TypeError):
            return 999999.0  # Put invalid queue_position at the end
    
    def parse_appointment_date(appointment_date):
        """Parse appointment_date to datetime object, handling various formats"""
        if not appointment_date or appointment_date == 'None' or str(appointment_date) == 'None':
            frappe.logger("debug").info(f"[KANBAN DEBUG] Empty appointment_date: {appointment_date}, returning far future date")
            return datetime(9999, 12, 31)  # Far future date for items without appointment date
        
        frappe.logger("debug").info(f"[KANBAN DEBUG] Parsing appointment_date: {appointment_date}, type: {type(appointment_date).__name__}")
        
        # Si ya es un objeto datetime, lo devolvemos directamente
        if isinstance(appointment_date, datetime):
            frappe.logger("debug").info(f"[KANBAN DEBUG] appointment_date ya es un objeto datetime, devolviéndolo directamente")
            return appointment_date
            
        # Si es un objeto date, lo convertimos a datetime
        if hasattr(appointment_date, 'year') and hasattr(appointment_date, 'month') and hasattr(appointment_date, 'day'):
            frappe.logger("debug").info(f"[KANBAN DEBUG] appointment_date es un objeto date, convirtiéndolo a datetime")
            return datetime(appointment_date.year, appointment_date.month, appointment_date.day)
        
        try:
            # Handle different date formats
            if isinstance(appointment_date, str):
                # Handle day-month format with year (e.g., "15-07-2025" or "19-07-25")
                if '-' in appointment_date:
                    parts = appointment_date.split('-')
                    
                    # Handle DD-MM-YYYY format (e.g., "15-07-2025")
                    if len(parts) == 3:
                        try:
                            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                            # Handle 2-digit year
                            if year < 100:
                                year += 2000
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Parsed DD-MM-YYYY: day={day}, month={month}, year={year}")
                            return datetime(year, month, day)
                        except (ValueError, IndexError) as e:
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Failed to parse DD-MM-YYYY: {e}")
                            pass
                    
                    # Handle DD-MM format (e.g., "15-07")
                    elif len(parts) == 2:
                        try:
                            day, month = int(parts[0]), int(parts[1])
                            current_year = datetime.now().year
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Parsed DD-MM: day={day}, month={month}, year={current_year}")
                            return datetime(current_year, month, day)
                        except (ValueError, IndexError) as e:
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Failed to parse DD-MM: {e}")
                            pass
                
                # Handle day-month format with slashes (e.g., "15/07/2025" or "19/07")
                elif '/' in appointment_date:
                    parts = appointment_date.split('/')
                    
                    # Handle DD/MM/YYYY format
                    if len(parts) == 3:
                        try:
                            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                            # Handle 2-digit year
                            if year < 100:
                                year += 2000
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Parsed DD/MM/YYYY: day={day}, month={month}, year={year}")
                            return datetime(year, month, day)
                        except (ValueError, IndexError) as e:
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Failed to parse DD/MM/YYYY: {e}")
                            pass
                    
                    # Handle DD/MM format
                    elif len(parts) == 2:
                        try:
                            day, month = int(parts[0]), int(parts[1])
                            current_year = datetime.now().year
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Parsed DD/MM: day={day}, month={month}, year={current_year}")
                            return datetime(current_year, month, day)
                        except (ValueError, IndexError) as e:
                            frappe.logger("debug").info(f"[KANBAN DEBUG] Failed to parse DD/MM: {e}")
                            pass
                
                # Try standard date formats
                date_formats = ['%d-%m-%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y']
                for fmt in date_formats:
                    try:
                        result = datetime.strptime(appointment_date, fmt)
                        frappe.logger("debug").info(f"[KANBAN DEBUG] Parsed with format {fmt}: {result}")
                        return result
                    except ValueError:
                        continue
            
            # If it's already a datetime object, use it directly
            elif hasattr(appointment_date, 'date'):
                result = appointment_date if isinstance(appointment_date, datetime) else datetime.combine(appointment_date, datetime.min.time())
                frappe.logger("debug").info(f"[KANBAN DEBUG] Using datetime object directly: {result}")
                return result
        
        except (ValueError, TypeError, AttributeError) as e:
            frappe.logger("debug").info(f"[KANBAN DEBUG] Exception parsing date: {e}")
            pass  # If all parsing attempts fail, use default
        
        # Default if all parsing attempts fail
        frappe.logger("debug").info(f"[KANBAN DEBUG] All parsing attempts failed for {appointment_date}, returning far future date")
        return datetime(9999, 12, 31)
    
    # Print raw data before sorting for debugging
    frappe.logger("debug").info("[KANBAN DEBUG] Raw data before sorting:")
    for p in special_order_projects:
        queue_pos = p.get('queue_position')
        appointment_date = p.get('appointment_date')
        frappe.logger("debug").info(f"[KANBAN DEBUG] {p.get('name')} - status: {p.get('status')}, queue_pos: {queue_pos}, type: {type(queue_pos).__name__}, appointment_date: {appointment_date}, type: {type(appointment_date).__name__}")
    
    # Sort the special order projects
    # Primero ordenamos por queue_position (ascendente) y luego por appointment_date (ascendente)
    sorted_special_projects = sorted(
        special_order_projects,
        key=lambda p: (
            parse_queue_position(p.get('queue_position')),
            parse_appointment_date(p.get('appointment_date'))
        )
    )
    
    # Verificamos si hay algún proyecto con queue_position None o vacío
    # y los movemos al final de la lista para cada status
    in_queue_projects = [p for p in sorted_special_projects if p.get('status') == 'In queue']
    in_parking_projects = [p for p in sorted_special_projects if p.get('status') == 'In parking']
    
    # Reordenamos los proyectos 'In queue' para que los que tienen queue_position None o vacío vayan al final
    in_queue_with_position = [p for p in in_queue_projects if p.get('queue_position') not in [None, '', 0]]
    in_queue_without_position = [p for p in in_queue_projects if p.get('queue_position') in [None, '', 0]]
    
    # Reordenamos los proyectos 'In parking' para que los que tienen queue_position None o vacío vayan al final
    in_parking_with_position = [p for p in in_parking_projects if p.get('queue_position') not in [None, '', 0]]
    in_parking_without_position = [p for p in in_parking_projects if p.get('queue_position') in [None, '', 0]]
    
    # Reconstruimos la lista de proyectos especiales ordenados
    sorted_special_projects = in_queue_with_position + in_queue_without_position + in_parking_with_position + in_parking_without_position
    
    # Log all projects in special order statuses after sorting
    frappe.logger("debug").info("[KANBAN DEBUG] Projects in special order statuses after sorting:")
    for p in sorted_special_projects:
        queue_pos = p.get('queue_position')
        parsed_queue_pos = parse_queue_position(queue_pos)
        appointment_date = p.get('appointment_date')
        parsed_date = parse_appointment_date(appointment_date)
        frappe.logger("debug").info(f"[KANBAN DEBUG] {p.get('name')} - status: {p.get('status')}, raw queue_pos: {queue_pos}, parsed: {parsed_queue_pos}, raw date: {appointment_date}, parsed: {parsed_date}")
    
    # Combine the sorted special projects with the regular projects (maintaining original order)
    sorted_projects = sorted_special_projects + regular_projects
    
    # Debug logging for final order
    in_queue_projects = [p for p in sorted_projects if p.get('status') == 'In queue']
    frappe.logger("debug").info(f"[KANBAN DEBUG] Final 'In queue' order:")
    for i, p in enumerate(in_queue_projects):
        frappe.logger("debug").info(f"[KANBAN DEBUG] {i+1}. {p.get('name')} - queue_position: {p.get('queue_position')}, appointment_date: {p.get('appointment_date')}")
    
    return sorted_projects

    
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
