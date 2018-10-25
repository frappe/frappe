import frappe
from frappe.frappeclient import FrappeClient
import json
from frappe.defaults import set_defaults

def get_remote_logs():
    sync_status = frappe.db.sql('''
		select
			defkey, defValue
		from
			`tabDefaultValue`
		where
			defkey=%s and parent=%s
		for update''', ("client_sync_running", "__default"), as_dict = True)
    
    if sync_status[0]["defValue"] == "Active":
        return

    sync_pos = frappe.db.sql('''
		select
			defkey, defValue
		from
			`tabDefaultValue`
		where
			defkey=%s and parent=%s
		for update''', ("client_sync_pos", "__default"), as_dict = True)

    last_inserted_logid = sync_pos[0]["defValue"]

    current_working_logid = last_inserted_logid

    master_setup = FrappeClient(frappe.local.conf.federation_master_hostname,frappe.local.conf.federation_master_user, frappe.local.conf.federation_master_password)
    new_master_logs = master_setup.post_request({
        "cmd": "frappe.federation_master.send_new_logs",
        "name_threshold": last_inserted_logid,
        "limit": 100
    })
    new_master_logs = json.loads(new_master_logs)

    for master_log in new_master_logs:

        if master_log["action"] == "INSERT":
            new_doc = frappe.get_doc(master_setup.get_doc(master_log["doctype"], master_log["docname"]))
            new_doc.insert()
        elif master_log["action"] == "UPDATE":
            updated_doc = master_setup.get_doc(master_log["doctype"], master_log["docname"])
            original_doc = frappe.get_doc(master_log["doctype"], master_log["docname"])
            for fieldname in updated_doc.keys()
                original_doc.set(fieldname, updated_doc.get(fieldname))
            original_doc.save()
        elif master_log["action"] == "RENAME":
            frappe.rename_doc(master_log["doctype"], master_log["docname"], master_log["actiondata"])
        elif master_log["action"] == "DELETE":
            frappe.delete_doc_if_exists(master_log["doctype"], master_log["docname"]))

        current_working_logid = current_working_logid

    set_defaults("client_sync_pos", current_working_logid, "__default")
    set_defaults("client_sync_running", "Inactive", "__default")
    

