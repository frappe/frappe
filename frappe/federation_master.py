import frappe
import json
from six import string_types
import traceback

@frappe.whitelist()
def get_change_logs(name_threshold, limit):
    if not str(limit).isnumeric():
        frappe.throw("Limit must be Numeric")
    new_logs = frappe.db.sql('''
        SELECT
            `name`,
            `doctype`,
            `docname`,
            `action`,
            `actiondata`
        FROM
            `tabVersion`
        WHERE
            name > %(name_threshold)s
        LIMIT {}
    '''.format(limit), {
        'name_threshold': name_threshold
    }, as_dict=1)
    return new_logs
