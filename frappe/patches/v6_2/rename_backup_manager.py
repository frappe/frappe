import frappe

def execute():
	unset = False
	frappe.reload_doc("integrations", "doctype", "dropbox_backup")

	dropbox_backup = frappe.get_doc("Dropbox Backup", "Dropbox Backup")
	for df in dropbox_backup.meta.fields:
		value = frappe.db.get_single_value("Backup Manager", df.fieldname)
		if value:
			if df.fieldname=="upload_backups_to_dropbox" and value=="Never":
				value = "Daily"
				unset = True
			dropbox_backup.set(df.fieldname, value)

	if unset:
		dropbox_backup.set("send_backups_to_dropbox", 0)

	dropbox_backup.save()
