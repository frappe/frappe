# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def sendmail_to_system_managers(subject, content):
	frappe.sendmail(recipients=get_system_managers(), subject=subject, content=content)

@frappe.whitelist()
def get_contact_list(doctype, fieldname, txt):
	"""Returns contacts (from autosuggest)"""
	txt = txt.replace('%', '')

	def get_users():
		return filter(None, frappe.db.sql_list('select email from tabUser where email like %s',
			('%' + txt + '%')))
	try:
		out = filter(None, frappe.db.sql_list('select `{0}` from `tab{1}` where `{0}` like %s'.format(fieldname, doctype),
			'%' + txt + '%'))
		if out:
			out = get_users()
	except Exception, e:
		if e.args[0]==1146:
			# no Contact, use User
			out = get_users()
		else:
			raise

	return out

def get_system_managers():
	return frappe.db.sql_list("""select parent FROM tabUserRole
		WHERE role='System Manager'
		AND parent!='Administrator'
		AND parent IN (SELECT email FROM tabUser WHERE enabled=1)""")

@frappe.whitelist()
def relink(name,reference_doctype=None,reference_name=None):
		dt = reference_doctype
		dn = reference_name
		origin = frappe.db.get_value("Communication", name, ["reference_doctype", "reference_name", "communication_medium", "subject"], as_dict=1)

		subject_link = '<a href="/desk#Form/Communication/' + name +'" target="_blank">' + origin.subject
		content= 'Relinked ' + origin.communication_medium + ' ' + subject_link + '</a>'

		if origin.reference_doctype:
			from_link = '<a href="/desk#Form/' + origin.reference_doctype +'/'+ origin.reference_name +'" target="_blank">'
			content += ' from ' + from_link + origin.reference_doctype +' '+ origin.reference_name +'</a>'

		frappe.db.sql("""UPDATE `tabCommunication`
			SET reference_doctype = %(ref_doc)s, reference_name = %(ref_name)s, STATUS = "Linked"
			WHERE communication_type = "Communication" and name = %(name)s OR timeline_hide = %(name)s""",
              {'ref_doc': dt,
               'ref_name': dn, 'name': name})

		dup_list = [{"name":name, "timeline_label":False}] + frappe.db.get_values("Communication", {"timeline_hide": name, "communication_type":"Communication"}, ["name", "timeline_label"], as_dict=1)
		for comm in dup_list:
			if not comm["timeline_label"]:
				doc = frappe.get_doc("Communication", comm["name"])
				if not doc.timeline_label:
					doc.timeline_doctype = None
					doc.timeline_name = None
					doc.set_timeline_doc()
					if comm["name"] == dup_list[0]["name"]:
						doc.save(ignore_permissions=True)
					else:
						doc.db_update()

		frappe.get_doc({
				"doctype": "Communication",
				"communication_type": "Comment",
				"comment_type": "Relinked",
				"reference_doctype": dt,
				"reference_name": dn,
				"subject": origin.subject,
				"communication_medium": frappe.db.get_value("Communication",name,"communication_medium"),
				"reference_owner": frappe.db.get_value(dt, dn, "owner"),
				"content": content,
				"sender":frappe.session.user
			}).insert(ignore_permissions=True)

def get_communication_doctype(doctype, txt, searchfield, start, page_len, filters):
	user_perms = frappe.utils.user.UserPermissions(frappe.session.user)
	user_perms.build_permissions()
	can_read = user_perms.can_read
	from frappe.modules import load_doctype_module
	com_doctypes = []
	if len(txt)<2:

		for name in ["Customer", "Supplier"]:
			try:
				module = load_doctype_module(name, suffix='_dashboard')
				if hasattr(module, 'get_data'):
					for i in module.get_data()['transactions']:
						com_doctypes += i["items"]
			except ImportError:
				pass
	else:
		com_doctypes = [d[0] for d in frappe.db.get_values("DocType", {"issingle": 0, "istable": 0, "hide_toolbar": 0})]

	out = []
	for dt in com_doctypes:
		if txt.lower().replace("%", "") in dt.lower() and dt in can_read:
			out.append([dt])
	return out
