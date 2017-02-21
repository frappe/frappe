from __future__ import unicode_literals
import frappe
from frappe import conf


@frappe.whitelist()
def get_dev_port():
    return conf.get("developer_mode"), conf.get('socketio_port')


@frappe.whitelist()
def get_all_users():
    return frappe.get_all(
        'User', ["email", "first_name", "last_name", "last_active"])
