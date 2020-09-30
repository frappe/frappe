import frappe
import json


@frappe.whitelist()
def create_file_record(file_doc):
    if not isinstance(file_doc, str):
        return

    # convert string of dict to dict
    file_doc = json.loads(file_doc)

    # add doctype to file_doc
    file_doc['doctype'] = 'File'

    # create and save doctype
    file = frappe.get_doc(file_doc)
    file.save()
