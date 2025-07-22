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
        print(f"\n\n[KANBAN UPDATE] Processing update_order for Project kanban board: {board_name}\n\n")
        frappe.logger().info(f"[KANBAN UPDATE] Processing update_order for Project kanban board: {board_name}")
        
        # Get the correctly sorted projects for special columns
        special_order_statuses = ["In queue", "In parking"]
        projects_ordered = get_projects_ordered_by_queue_position_and_appointment_date()
        
        # Create a map of column name to sorted project names
        sorted_columns = {}
        for status in special_order_statuses:
            sorted_columns[status] = [p['name'] for p in projects_ordered if p.get('status') == status]
            print(f"\n[KANBAN UPDATE] Sorted order for '{status}': {sorted_columns[status]}\n")
            frappe.logger().info(f"[KANBAN UPDATE] Sorted order for '{status}': {sorted_columns[status]}")
            
        # Log the incoming order from frontend for comparison
        print(f"\n[KANBAN UPDATE] Order received from frontend: {order_dict}\n")
        
        # If order_dict is empty, we need to build it from the current board state
        if not order_dict:
            print("\n[KANBAN UPDATE] Order dict is empty, building from current board state\n")
            order_dict = {}
            for column in board.columns:
                try:
                    # Get the current order from the column
                    current_order = json.loads(column.order or '[]')
                    order_dict[column.column_name] = current_order
                    print(f"\n[KANBAN UPDATE] Current order for '{column.column_name}': {current_order}\n")
                except Exception as e:
                    print(f"\n[KANBAN UPDATE] Error parsing column order: {e}\n")
                    order_dict[column.column_name] = []
        
        # Apply our custom sorting only to special columns, keep user's drag-drop order for others
        for col_name, cards in order_dict.items():
            # Update the project status if it changed
            for card in cards:
                column = frappe.get_value(doctype, {"name": card}, fieldname)
                if column != col_name:
                    frappe.set_value(doctype, card, fieldname, col_name)
                    updated_cards.append(dict(name=card, column=col_name))
            
            # For special columns, use our sorted order instead of the order from the frontend
            if col_name in special_order_statuses and col_name in sorted_columns:
                # Get the intersection of cards in this column and our sorted order
                # This ensures we only include cards that are actually in this column
                sorted_cards = [card for card in sorted_columns[col_name] if card in cards]
                
                # Add any cards that might be in the column but not in our sorted list (edge case)
                for card in cards:
                    if card not in sorted_cards:
                        sorted_cards.append(card)
                
                # Update the column order with our sorted order
                for column in board.columns:
                    if column.column_name == col_name:
                        column.order = json.dumps(sorted_cards)
                        frappe.logger().info(f"[KANBAN UPDATE] Applied sorted order to column '{col_name}': {sorted_cards}")
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
    print(f"\n\n[KANBAN SINGLE CARD] Moving card {docname} from {from_colname} to {to_colname}, old_index: {old_index}, new_index: {new_index}\n\n")
    
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
            print("docname no se encuentra en from_col_order.")
        except IndexError as e:
            print(e)

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
            frappe.logger().info(f"[KANBAN REFRESH] Updated column '{column.column_name}' with {len(column_projects)} projects")
        
        # Save the board
        board.save(ignore_permissions=True)
        
        frappe.logger().info(f"[KANBAN REFRESH] Successfully refreshed kanban board: {board_name}")
        return {"status": "success", "message": f"Kanban board '{board_name}' order refreshed successfully"}
        
    except Exception as e:
        frappe.logger().error(f"[KANBAN REFRESH] Error refreshing kanban board {board_name}: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def kanban_project_refresh(name:str):
    sleep(2)
    frappe.publish_realtime("kanban_project_refresh")
    frappe.publish_realtime("list_update",{"doctype":"Project", "user":"support@tvsgroup.nl", "name": name})
    return "called kanban_project_refresh"


# ==================== CUSTOM FUNCTIONS ====================

def get_projects_ordered_by_queue_position_and_appointment_date():
    """
    Orders project cards by queue_position and appointment_date for specific columns only.
    
    Requirements:
    - For "In queue" and "In parking" columns: sort by queue_position (ascending), then by appointment_date
    - For other columns: maintain original order
    - Database returns queue_position as string, so conversion to float is needed for proper sorting
    """
    print("\n[KANBAN DEBUG] Starting get_projects_ordered_by_queue_position_and_appointment_date()\n")
    
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
    print(f"\n[KANBAN DEBUG] Total projects fetched: {len(projects)}\n")
    frappe.logger().info(f"[KANBAN DEBUG] Total projects fetched: {len(projects)}")
    
    # Separate projects into two groups: those that need special ordering and those that don't
    special_order_statuses = ["In queue", "In parking"]
    special_order_projects = [p for p in projects if p.get('status') in special_order_statuses]
    regular_projects = [p for p in projects if p.get('status') not in special_order_statuses]
    
    print(f"\n[KANBAN DEBUG] Projects in special order statuses: {len(special_order_projects)}\n")
    print(f"\n[KANBAN DEBUG] Projects in regular statuses: {len(regular_projects)}\n")
    
    # Log all projects in special order statuses before sorting
    frappe.logger().info(f"[KANBAN DEBUG] Projects in special order statuses before sorting:")
    for p in special_order_projects:
        frappe.logger().info(f"[KANBAN DEBUG] {p.get('name')} - status: {p.get('status')}, queue_position: {p.get('queue_position')}, appointment_date: {p.get('appointment_date')}")
    
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
            return datetime(9999, 12, 31)  # Far future date for items without appointment date
        
        try:
            # Handle different date formats
            if isinstance(appointment_date, str):
                # Handle day-month format (e.g., "15-07" or "19/07")
                if '-' in appointment_date and len(appointment_date.split('-')) == 2:
                    day_month = appointment_date.split('-')
                    current_year = datetime.now().year
                    try:
                        return datetime(current_year, int(day_month[1]), int(day_month[0]))
                    except (ValueError, IndexError):
                        pass  # Continue to next format if this fails
                
                elif '/' in appointment_date and len(appointment_date.split('/')) == 2:
                    day_month = appointment_date.split('/')
                    current_year = datetime.now().year
                    try:
                        return datetime(current_year, int(day_month[1]), int(day_month[0]))
                    except (ValueError, IndexError):
                        pass  # Continue to next format if this fails
                
                # Try standard date formats
                date_formats = ['%d-%m-%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S']
                for fmt in date_formats:
                    try:
                        return datetime.strptime(appointment_date, fmt)
                    except ValueError:
                        continue
            
            # If it's already a datetime object, use it directly
            elif hasattr(appointment_date, 'date'):
                return appointment_date if isinstance(appointment_date, datetime) else datetime.combine(appointment_date, datetime.min.time())
        
        except (ValueError, TypeError, AttributeError):
            pass  # If all parsing attempts fail, use default
        
        # Default if all parsing attempts fail
        return datetime(9999, 12, 31)
    
    # Sort the special order projects
    sorted_special_projects = sorted(
        special_order_projects,
        key=lambda p: (
            parse_queue_position(p.get('queue_position')),
            parse_appointment_date(p.get('appointment_date'))
        )
    )
    
    # Log all projects in special order statuses after sorting
    frappe.logger().info(f"[KANBAN DEBUG] Projects in special order statuses after sorting:")
    for p in sorted_special_projects:
        queue_pos = p.get('queue_position')
        parsed_queue_pos = parse_queue_position(queue_pos)
        appointment_date = p.get('appointment_date')
        parsed_date = parse_appointment_date(appointment_date)
        frappe.logger().info(f"[KANBAN DEBUG] {p.get('name')} - status: {p.get('status')}, raw queue_pos: {queue_pos}, parsed: {parsed_queue_pos}, raw date: {appointment_date}, parsed: {parsed_date}")
    
    # Combine the sorted special projects with the regular projects (maintaining original order)
    sorted_projects = sorted_special_projects + regular_projects
    
    # Debug logging for final order
    in_queue_projects = [p for p in sorted_projects if p.get('status') == 'In queue']
    frappe.logger().info(f"[KANBAN DEBUG] Final 'In queue' order:")
    for i, p in enumerate(in_queue_projects):
        frappe.logger().info(f"[KANBAN DEBUG] {i+1}. {p.get('name')} - queue_position: {p.get('queue_position')}, appointment_date: {p.get('appointment_date')}")
    
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
