import frappe
import json
from six import string_types
import traceback

master_doctypes = None

def get_master_doctypes():
    global master_doctypes
    if not frappe.local.conf.master:
        return []
    if master_doctypes is None:
        master_doctypes = frappe.local.conf.master_doctypes or []
    return master_doctypes

def log_insert(doctype, name=None):
    if not isinstance(doctype, string_types):
        name = doctype.name
        doctype = doctype.doctype
    if doctype in get_master_doctypes():
        make_log(doctype, name, 'INSERT')

def log_update(doctype, name=None):
    if not isinstance(doctype, string_types):
        name = doctype.name
        doctype = doctype.doctype
    if doctype in get_master_doctypes():
        make_log(doctype, name, 'UPDATE')

def is_being_inserted(doctype, name):
    return is_being_used('currently_inserting', doctype, name)

def is_being_renamed(doctype, name):
    return is_being_used('currently_renaming', doctype, name)

def is_being_used(flag, doctype, name):
    currently_used = frappe.flags.get(flag)
    currently_used_docs = currently_used and currently_used.get(doctype)
    if currently_used_docs:
        if name in currently_used_docs:
            return True

def log_set_value(doctype, name):
    if doctype not in get_master_doctypes():
        return
    if is_being_renamed(doctype, name) or is_being_inserted(doctype, name):
        return
    make_log(doctype, name, 'UPDATE')

def log_rename(doctype, old, new, merge):
    if doctype in get_master_doctypes():
        make_log(doctype, old, 'RENAME', json.dumps({
            'new_name': new,
            'merge': merge,
        }))

def log_delete(doctype, name, **kwargs):
    if is_being_renamed(doctype, name):
        return
    if doctype in get_master_doctypes():
        make_log(doctype, name, 'DELETE', json.dumps(kwargs))

def make_log(doctype, docname, action, actiondata=''):
    frappe.db.sql('''
        INSERT
            into
        `tabDocument Change Log`(
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
def get_change_logs(name_threshold, limit):
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
            `tabDocument Change Log`
        WHERE
            name > %(name_threshold)s
        LIMIT {}
    '''.format(limit), {
        'name_threshold': name_threshold
    }, as_dict=1)
    return new_logs
