# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, has_gravatar
from frappe import _
from frappe.model.document import Document

class Contact(Document):
	def autoname(self):
		# concat first and last name
		self.name = " ".join(filter(None,
			[cstr(self.get(f)).strip() for f in ["first_name", "last_name"]]))

		# concat party name if reqd
		for link in self.links:
			self.name = self.name + '-' + link.link_name.strip()
			break

	def validate(self):
		self.set_user()
		if self.email_id:
			self.image = has_gravatar(self.email_id)

	def set_user(self):
		if not self.user and self.email_id:
			self.user = frappe.db.get_value("User", {"email": self.email_id})

	def on_trash(self):
		frappe.db.sql("""update `tabIssue` set contact='' where contact=%s""",
			self.name)

	def get_link_for(self, link_doctype):
		'''Return the link name, if exists for the given link DocType'''
		for link in self.links:
			if link.link_doctype==link_doctype:
				return link.link_name

		return None

	def has_common_link(self, doc):
		reference_links = [(link.link_doctype, link.link_name) for link in doc.links]
		for link in self.links:
			if (link.link_doctype, link.link_name) in reference_links:
				return True


def get_default_contact(doctype, name):
	'''Returns default contact for the given doctype, name'''
	out = frappe.db.sql('''select contact.name
		from
			tabContact contact, `tabDynamic Link` dl
		where
			dl.parent = contact.name and
			dl.link_doctype=%s and
			dl.link_name=%s and
			dl.parenttype = "Contact"
		order by
			contact.is_primary_contact desc, name
		limit 1''', (doctype, name))

	return out and out[0][0] or None

@frappe.whitelist()
def invite_user(contact):
	contact = frappe.get_doc("Contact", contact)

	if not contact.email_id:
		frappe.throw(_("Please set Email Address"))

	if contact.has_permission("write"):
		user = frappe.get_doc({
			"doctype": "User",
			"first_name": contact.first_name,
			"last_name": contact.last_name,
			"email": contact.email_id,
			"user_type": "Website User",
			"send_welcome_email": 1
		}).insert(ignore_permissions = True)

		return user.name

@frappe.whitelist()
def get_contact_details(contact):
	contact = frappe.get_doc("Contact", contact)
	out = {
		"contact_person": contact.get("name"),
		"contact_display": " ".join(filter(None,
			[contact.get("first_name"), contact.get("last_name")])),
		"contact_email": contact.get("email_id"),
		"contact_mobile": contact.get("mobile_no"),
		"contact_phone": contact.get("phone"),
		"contact_designation": contact.get("designation"),
		"contact_department": contact.get("department")
	}
	return out

def update_contact(doc, method):
	'''Update contact when user is updated, if contact is found. Called via hooks'''
	contact_name = frappe.db.get_value("Contact", {"email_id": doc.name})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for key in ("first_name", "last_name", "phone"):
			if doc.get(key):
				contact.set(key, doc.get(key))
		contact.flags.ignore_mandatory = True
		contact.save(ignore_permissions=True)

def contact_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.reportview import get_match_cond

	return frappe.db.sql("""select
			contact.name, contact.first_name, contact.last_name
		from
			tabContact as contact, `tabDynamic Link` as dl
		where
			dl.parent = contact.name and
			dl.parenttype = 'Contact' and
			dl.link_doctype = %(link_doctype)s and
			dl.link_name = %(link_name)s and
			contact.`{key}` like %(txt)s
			{mcond}
		order by
			if(locate(%(_txt)s, contact.name), locate(%(_txt)s, contact.name), 99999),
			contact.idx desc, contact.name
		limit %(start)s, %(page_len)s """.format(
			mcond=get_match_cond(doctype),
			key=frappe.db.escape(searchfield)),
		{
			'txt': "%%%s%%" % frappe.db.escape(txt),
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
			'link_doctype': filters.get('link_doctype'),
			'link_name': filters.get('link_name')
		})

def contact_links(doctype, txt, searchfield, start, page_len, filters):
	if not txt: txt = ""
	txt = txt.lower()
	return [[d] for d in get_link_doctypes() if txt in d.lower()]

@frappe.whitelist()
def get_link_doctypes():
	return [x.parent for x in frappe.db.get_values("DocField", {"fieldname": 'contact_html'}, "parent", order_by="name", as_dict=1)]

