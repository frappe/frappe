import frappe
import json

@frappe.whitelist()
def update_doc(doc):
    doc = frappe.get_doc(json.loads(doc)).save()


@frappe.whitelist()
def make_communication(doc, communication):
    doc = json.loads(doc)
    communication = json.loads(communication)
    new_comm = {
        "doctype": "Communication",
        "reference_doctype": doc['doctype'],
        "reference_name": doc['name'],
        "content": communication['content'],
        "subject": communication['subject'],
        "sent_or_received": communication['sent_or_received'],
        "user": doc['contact_by']
        }
    frappe.get_doc(new_comm).insert()
