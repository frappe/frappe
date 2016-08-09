import frappe
@frappe.whitelist(allow_guest=True)
def relink(self,name,reference_doctype,reference_name):
	dt = reference_doctype
	dn = reference_name

	if dt=="" or dt==None or dn == "" or dn == None:
		return # is blank maybe try flash missing required
	frappe.db.sql("""update `tabCommunication`
		set reference_doctype = %s ,reference_name = %s ,status = "Linked"
		where name = %s """,(dt,dn,name))

	return self.fetch()
