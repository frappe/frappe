import frappe
import json
from six import string_types
import traceback

federation_master_data = None

def get_federation_master_doctypes():
    global federation_master_data
    if not federation_master_data:
        federation_master_data = frappe.get_hooks('federation_master_doctypes')
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
        make_log(doctype, name, 'UPDATE')

def is_being_renamed(doctype, name):
    currently_renaming = frappe.flags.currently_renaming
    currently_renaming_docs = currently_renaming and currently_renaming.get(doctype)
    if currently_renaming_docs:
        if name in currently_renaming_docs:
            return True

def log_set_value(doctype, name):
    if doctype not in get_federation_master_doctypes():
        return
    if is_being_renamed(doctype, name):
        return
    make_log(doctype, name, 'UPDATE')

def log_rename(doctype, old, new, merge):
    if doctype in get_federation_master_doctypes():
        make_log(doctype, old, 'RENAME', json.dumps({
            'new_name': new,
            'merge': merge,
        }))

def log_delete(doctype, name, **kwargs):
    if is_being_renamed(doctype, name):
        return
    if doctype in get_federation_master_doctypes():
        make_log(doctype, name, 'DELETE', json.dumps(kwargs))

def make_log(doctype, docname, action, actiondata=''):
    # print('Making Log for ', doctype, docname, 'of type', action, 'with actiondata', actiondata)
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
def send_new_logs(name_threshold, limit):
    if not unicode(limit).isnumeric():
        frappe.throw("Limit must be Numeric")
    new_logs = frappe.db.sql('''
        SELECT
            `name`,
            `doctype`,
            `docname`,
            `action`,
            `actiondata`
        FROM
            `tabFederation Master Log`
        WHERE
            name > %(name_threshold)s
        LIMIT {}
    '''.format(limit), {
        'name_threshold': name_threshold
    }, as_dict=1)
    return new_logs
