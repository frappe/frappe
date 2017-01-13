from __future__ import unicode_literals
import frappe
from frappe.utils import extract_email_id
from inbox.email_inbox.contact import match_email_to_contact
def execute():
	frappe.reload_doctype('Communication')
	for c in frappe.db.sql("""select name,sender from tabCommunication where communication_type = 'Communication' and sender like '%<%>'""",as_dict=1):
		frappe.db.set_value('Communication', c.name, 'sender',extract_email_id(c.sender) , update_modified=False)
		communication = frappe.get_doc('Communication', c.name)
		match_email_to_contact(communication)

	