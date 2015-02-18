import frappe
import frappe.share

def execute():
	frappe.reload_doc("core", "doctype", "docperm")
	frappe.reload_doc("core", "doctype", "docshare")

	# default share to all writes
	frappe.db.sql("""update tabDocPerm set `share`=1 where ifnull(`write`,0)=1 and ifnull(`permlevel`,0)=0""")

	# every user must have access to his / her own detail
	for user in frappe.get_all("User", filters={"user_type": "System User"}):
		frappe.share.add("User", user.name, user.name, share=1)

	# move event user to shared
	if frappe.db.exists("DocType", "Event User"):
		for event in frappe.get_all("Event User", fields=["parent", "person"]):
			frappe.share.add("Event", event.parent, event.person, write=1)

		frappe.delete_doc("DocType", "Event User")

	# move note user to shared
	if frappe.db.exists("DocType", "Note User"):
		for note in frappe.get_all("Note User", fields=["parent", "user", "permission"]):
			perm = {"read": 1} if note.permission=="Read" else {"write": 1}
			frappe.share.add("Note", note.parent, note.user, **perm)

		frappe.delete_doc("DocType", "Note User")
