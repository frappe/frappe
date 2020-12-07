import frappe
from frappe.desk.utils import get_doctype_route

def execute():
    for doctype in frappe.get_all('DocType', ['name', 'route'], dict(istable=0)):
        if not doctype.route:
            frappe.db.set_value('DocType', doctype.name, 'route', get_doctype_route(doctype.name), update_modified = False)