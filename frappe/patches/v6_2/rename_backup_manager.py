import frappe

def execute():
	dropbox_backup = frappe.get_doc("Dropbox Backup", "Dropbox Backup")
	for df in dropbox_backup.meta.fields:
		value = frappe.db.get_single_value("Backup Manager", df.fieldname)
		if value:
			dropbox_backup.set(df.fieldname, value)

	dropbox_backup.save()
