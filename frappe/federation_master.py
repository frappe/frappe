import frappe
import json
from six import string_types
import traceback

federation_master_data = None

def get_federation_master_doctypes():
    global federation_master_data
    if not federation_master_data:
        federation_master_data = frappe.get_hooks('federation_master_data')
    return federation_master_data

def log_insert(doctype, name=None):
    if not isinstance(doctype, string_types):
        name = doctype.name
        doctype = doctype.doctype
    if doctype in get_federation_master_doctypes():
        make_log(doctype, name, 'INSERT')

def log_update(doctype, name=None):
    if not isinstance(doctype, string_types):
        name = doctype.name
        doctype = doctype.doctype
    if doctype in get_federation_master_doctypes():
        print('\n\n\n\n\n==================================\n\n\n\n\n\n\n')
        traceback.print_stack()
        make_log(doctype, name, 'UPDATE')

def log_rename(doctype, old, new, merge):
    if doctype in get_federation_master_doctypes():
        make_log(doctype, old, 'RENAME', json.dumps({
            'new_name': new,
            'merge': merge,
        }))

def log_delete(doctype, name, **kwargs):
    if doctype in get_federation_master_doctypes():
        make_log(doctype, name, 'DELETE', json.dumps(kwargs))

def make_log(doctype, docname, action, actiondata=''):
    frappe.db.sql('''
        INSERT
            into
        `tabFederation Master Log`(
            `doctype`,
            `docname`,
            `action`,
            `actiondata`
        ) values (
            %(doctype)s,
            %(docname)s,
            %(action)s,
            %(actiondata)s
        )
    ''', {
        'doctype': doctype,
        'docname': docname,
        'action': action,
        'actiondata': actiondata,
    })

@frappe.whitelist()
def send_new_logs(name_threshold):
    new_logs = json.dumps(frappe.db.sql("""SELECT * FROM `tabFederation Master Log` WHERE name > {}""".format(name_threshold)))
    print(new_logs)
    return {"tosay": "  hello"}