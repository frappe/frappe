import frappe
from frappe.utils import now_datetime

def execute():
	frappe.db.sql('update `tabBulk Email` set send_after=%s where send_after is null', now_datetime())