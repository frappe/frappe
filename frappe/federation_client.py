import frappe
from frappe.frappeclient import FrappeClient

def get_remote_logs():
    last_inserted_logid = frappe.db.sql("""SELECT MAX(name) FROM `tabFederation Master Log`""")[0][0]
    master_setup = FrappeClient(frappe.local.conf.federation_master_hostname,frappe.local.conf.federation_master_user, frappe.local.conf.federation_master_password)
    master_setup.post_request({
        "cmd": "frappe.federation_master.send_new_logs",
        "name_threshold": last_inserted_logid
    })
