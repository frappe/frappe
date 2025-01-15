# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe import _
from frappe.contacts.address_and_contact import set_link_title
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.core.doctype.dynamic_link.dynamic_link import deduplicate_dynamic_links
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import cstr, has_gravatar


class Contact(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.contacts.doctype.contact_email.contact_email import ContactEmail
		from frappe.contacts.doctype.contact_phone.contact_phone import ContactPhone
		from frappe.core.doctype.dynamic_link.dynamic_link import DynamicLink
		from frappe.types import DF

		address: DF.Link | None
		company_name: DF.Data | None
		department: DF.Data | None
		designation: DF.Data | None
		email_id: DF.Data | None
		email_ids: DF.Table[ContactEmail]
		first_name: DF.Data | None
		full_name: DF.Data | None
		gender: DF.Link | None
		google_contacts: DF.Link | None
		google_contacts_id: DF.Data | None
		image: DF.AttachImage | None
		is_primary_contact: DF.Check
		last_name: DF.Data | None
		links: DF.Table[DynamicLink]
		middle_name: DF.Data | None
		mobile_no: DF.Data | None
		phone: DF.Data | None
		phone_nos: DF.Table[ContactPhone]
		pulled_from_google_contacts: DF.Check
		salutation: DF.Link | None
		status: DF.Literal["Passive", "Open", "Replied"]
		sync_with_google_contacts: DF.Check
		unsubscribed: DF.Check
		user: DF.Link | None
	# end: auto-generated types

	def autoname(self):
		self.name = self._get_full_name()

		# concat party name if reqd
		for link in self.links:
			self.name = self.name + "-" + cstr(link.link_name).strip()
			break

		if frappe.db.exists("Contact", self.name):
			self.name = append_number_if_name_exists("Contact", self.name)

	def validate(self):
		self.full_name = self._get_full_name()
		self.set_primary_email()
		self.set_primary("phone")
		self.set_primary("mobile_no")

		self.set_user()

		set_link_title(self)

		if self.email_id and not self.image:
			self.image = has_gravatar(self.email_id)

		if self.get("sync_with_google_contacts") and not self.get("google_contacts"):
			frappe.throw(_("Select Google Contacts to which contact should be synced."))

		deduplicate_dynamic_links(self)

	def set_user(self):
		if not self.user and self.email_id:
			self.user = frappe.db.get_value("User", {"email": self.email_id})

	def get_link_for(self, link_doctype):
		"""Return the link name, if exists for the given link DocType"""
		for link in self.links:
			if link.link_doctype == link_doctype:
				return link.link_name

		return None

	def has_link(self, doctype, name):
		for link in self.links:
			if link.link_doctype == doctype and link.link_name == name:
				return True

	def has_common_link(self, doc):
		reference_links = [(link.link_doctype, link.link_name) for link in doc.links]
		for link in self.links:
			if (link.link_doctype, link.link_name) in reference_links:
				return True

	def add_email(self, email_id, is_primary=0, autosave=False):
		if not frappe.db.exists("Contact Email", {"email_id": email_id, "parent": self.name}):
			self.append("email_ids", {"email_id": email_id, "is_primary": is_primary})

			if autosave:
				self.save(ignore_permissions=True)

	def add_phone(self, phone, is_primary_phone=0, is_primary_mobile_no=0, autosave=False):
		if not frappe.db.exists("Contact Phone", {"phone": phone, "parent": self.name}):
			self.append(
				"phone_nos",
				{
					"phone": phone,
					"is_primary_phone": is_primary_phone,
					"is_primary_mobile_no": is_primary_mobile_no,
				},
			)

			if autosave:
				self.save(ignore_permissions=True)

	def set_primary_email(self):
		if not self.email_ids:
			self.email_id = ""
			return

		if len([email.email_id for email in self.email_ids if email.is_primary]) > 1:
			frappe.throw(_("Only one {0} can be set as primary.").format(frappe.bold(_("Email ID"))))

		if len(self.email_ids) == 1:
			self.email_ids[0].is_primary = 1

		primary_email_exists = False
		for d in self.email_ids:
			if d.is_primary == 1:
				primary_email_exists = True
				self.email_id = d.email_id.strip()
				break

		if not primary_email_exists:
			self.email_id = ""

	def set_primary(self, fieldname):
		# Used to set primary mobile and phone no.
		if len(self.phone_nos) == 0:
			setattr(self, fieldname, "")
			return

		field_name = "is_primary_" + fieldname

		is_primary = [phone.phone for phone in self.phone_nos if phone.get(field_name)]

		if len(is_primary) > 1:
			frappe.throw(
				_("Only one {0} can be set as primary.").format(frappe.bold(frappe.unscrub(fieldname)))
			)

		primary_number_exists = False
		for d in self.phone_nos:
			if d.get(field_name) == 1:
				primary_number_exists = True
				setattr(self, fieldname, d.phone)
				break

		if not primary_number_exists:
			setattr(self, fieldname, "")

	def _get_full_name(self) -> str:
		return get_full_name(self.first_name, self.middle_name, self.last_name, self.company_name)

	def get_vcard(self):
		from vobject import vCard
		from vobject.vcard import Name

		vcard = vCard()
		vcard.add("fn").value = self.full_name

		name = Name()
		if self.first_name:
			name.given = self.first_name

		if self.last_name:
			name.family = self.last_name

		if self.middle_name:
			name.additional = self.middle_name

		vcard.add("n").value = name

		if self.designation:
			vcard.add("title").value = self.designation

		org_list = []
		if self.company_name:
			org_list.append(self.company_name)

		if self.department:
			org_list.append(self.department)

		if org_list:
			vcard.add("org").value = org_list

		for row in self.email_ids:
			email = vcard.add("email")
			email.value = row.email_id
			if row.is_primary:
				email.type_param = "pref"

		for row in self.phone_nos:
			tel = vcard.add("tel")
			tel.value = row.phone
			if row.is_primary_phone:
				tel.type_param = "home"

			if row.is_primary_mobile_no:
				tel.type_param = "cell"

		return vcard


@frappe.whitelist()
def download_vcard(contact: str):
	"""Download vCard for the contact"""
	contact = frappe.get_doc("Contact", contact)
	contact.check_permission()

	vcard = contact.get_vcard()
	make_access_log(doctype="Contact", document=contact.name, file_type="vcf")

	frappe.response["filename"] = f"{contact.name}.vcf"
	frappe.response["filecontent"] = vcard.serialize().encode("utf-8")
	frappe.response["type"] = "binary"


@frappe.whitelist()
def download_vcards(contacts: str):
	"""Download vCard for the contact"""
	import json

	from frappe.utils.data import now

	contact_ids = frappe.parse_json(contacts)

	vcards = []
	for contact_id in contact_ids:
		contact = frappe.get_doc("Contact", contact_id)
		contact.check_permission()
		vcard = contact.get_vcard()
		vcards.append(vcard.serialize())

	make_access_log(
		doctype="Contact",
		filters=json.dumps([["name", "in", contact_ids]], ensure_ascii=False, indent="\t"),
		file_type="vcf",
	)

	timestamp = now()[:19]  # remove milliseconds

	frappe.response["filename"] = f"{timestamp} Contacts.vcf"
	frappe.response["filecontent"] = "\n".join(vcards).encode("utf-8")
	frappe.response["type"] = "binary"


def get_default_contact(doctype, name):
	"""Return default contact for the given doctype, name."""
	out = frappe.db.sql(
		"""select parent,
			IFNULL((select is_primary_contact from tabContact c where c.name = dl.parent), 0)
				as is_primary_contact
		from
			`tabDynamic Link` dl
		where
			dl.link_doctype=%s and
			dl.link_name=%s and
			dl.parenttype = 'Contact' """,
		(doctype, name),
		as_dict=True,
	)

	if out:
		for contact in out:
			if contact.is_primary_contact:
				return contact.parent
		return out[0].parent
	else:
		return None


@frappe.whitelist()
def invite_user(contact: str):
	contact = frappe.get_doc("Contact", contact)
	contact.check_permission()

	if not contact.email_id:
		frappe.throw(_("Please set Email Address"))

	user = frappe.get_doc(
		{
			"doctype": "User",
			"first_name": contact.first_name,
			"last_name": contact.last_name,
			"email": contact.email_id,
			"user_type": "Website User",
			"send_welcome_email": 1,
		}
	).insert()

	return user.name


@frappe.whitelist()
def get_contact_details(contact):
	contact = frappe.get_doc("Contact", contact)
	contact.check_permission()

	return {
		"contact_person": contact.get("name"),
		"contact_display": contact.get("full_name"),
		"contact_email": contact.get("email_id"),
		"contact_mobile": contact.get("mobile_no"),
		"contact_phone": contact.get("phone"),
		"contact_designation": contact.get("designation"),
		"contact_department": contact.get("department"),
	}


def update_contact(doc, method):
	"""Update contact when user is updated, if contact is found. Called via hooks"""
	contact_name = frappe.db.get_value("Contact", {"email_id": doc.name})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for key in ("first_name", "last_name", "phone"):
			if doc.get(key):
				contact.set(key, doc.get(key))
		contact.flags.ignore_mandatory = True
		contact.save(ignore_permissions=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def contact_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.reportview import get_match_cond

	doctype = "Contact"
	if not frappe.get_meta(doctype).get_field(searchfield) and searchfield not in frappe.db.DEFAULT_COLUMNS:
		return []

	link_doctype = filters.pop("link_doctype")
	link_name = filters.pop("link_name")

	return frappe.db.sql(
		f"""select
			`tabContact`.name, `tabContact`.full_name, `tabContact`.company_name
		from
			`tabContact`, `tabDynamic Link`
		where
			`tabDynamic Link`.parent = `tabContact`.name and
			`tabDynamic Link`.parenttype = 'Contact' and
			`tabDynamic Link`.link_doctype = %(link_doctype)s and
			`tabDynamic Link`.link_name = %(link_name)s and
			`tabContact`.`{searchfield}` like %(txt)s
			{get_match_cond(doctype)}
		order by
			if(locate(%(_txt)s, `tabContact`.full_name), locate(%(_txt)s, `tabContact`.company_name), 99999),
			`tabContact`.idx desc, `tabContact`.full_name
		limit %(start)s, %(page_len)s """,
		{
			"txt": "%" + txt + "%",
			"_txt": txt.replace("%", ""),
			"start": start,
			"page_len": page_len,
			"link_name": link_name,
			"link_doctype": link_doctype,
		},
	)


@frappe.whitelist()
def address_query(links):
	import json

	links = [
		{"link_doctype": d.get("link_doctype"), "link_name": d.get("link_name")} for d in json.loads(links)
	]
	result = []

	for link in links:
		if not frappe.has_permission(
			doctype=link.get("link_doctype"), ptype="read", doc=link.get("link_name")
		):
			continue

		res = frappe.db.sql(
			"""
			SELECT `tabAddress`.name
			FROM `tabAddress`, `tabDynamic Link`
			WHERE `tabDynamic Link`.parenttype='Address'
				AND `tabDynamic Link`.parent=`tabAddress`.name
				AND `tabDynamic Link`.link_doctype = %(link_doctype)s
				AND `tabDynamic Link`.link_name = %(link_name)s
		""",
			{
				"link_doctype": link.get("link_doctype"),
				"link_name": link.get("link_name"),
			},
			as_dict=True,
		)

		result.extend([l.name for l in res])

	return result


def get_contact_with_phone_number(number):
	if not number:
		return

	contacts = frappe.get_all(
		"Contact Phone", filters=[["phone", "like", f"%{number}"]], fields=["parent"], limit=1
	)

	return contacts[0].parent if contacts else None


def get_contact_name(email_id: str) -> str | None:
	"""Return the contact ID for the given email ID."""
	for contact_id in frappe.get_all(
		"Contact Email", filters={"email_id": email_id, "parenttype": "Contact"}, pluck="parent"
	):
		if frappe.db.exists("Contact", contact_id):
			return contact_id


def get_contacts_linking_to(doctype, docname, fields=None):
	"""Return a list of contacts containing a link to the given document."""
	return frappe.get_list(
		"Contact",
		fields=fields,
		filters=[
			["Dynamic Link", "link_doctype", "=", doctype],
			["Dynamic Link", "link_name", "=", docname],
		],
	)


def get_contacts_linked_from(doctype, docname, fields=None):
	"""Return a list of contacts that are contained in (linked from) the given document."""
	link_fields = frappe.get_meta(doctype).get("fields", {"fieldtype": "Link", "options": "Contact"})
	if not link_fields:
		return []

	contact_names = frappe.get_value(doctype, docname, fieldname=[f.fieldname for f in link_fields])
	if not contact_names:
		return []

	return frappe.get_list("Contact", fields=fields, filters={"name": ("in", contact_names)})


def get_full_name(
	first: str | None = None,
	middle: str | None = None,
	last: str | None = None,
	company: str | None = None,
) -> str:
	full_name = " ".join(filter(None, [cstr(f).strip() for f in [first, middle, last]]))
	if not full_name and company:
		full_name = company

	return full_name


def get_contact_display_list(doctype: str, name: str) -> list[dict]:
	from frappe.contacts.doctype.address.address import get_condensed_address

	if not frappe.has_permission("Contact", "read"):
		return []

	contact_list = frappe.get_list(
		"Contact",
		filters=[
			["Dynamic Link", "link_doctype", "=", doctype],
			["Dynamic Link", "link_name", "=", name],
			["Dynamic Link", "parenttype", "=", "Contact"],
		],
		fields=["*"],
		order_by="is_primary_contact DESC, `tabContact`.creation ASC",
	)

	for contact in contact_list:
		contact["email_ids"] = frappe.get_all(
			"Contact Email",
			filters={"parenttype": "Contact", "parent": contact.name, "is_primary": 0},
			fields=["email_id"],
		)

		contact["phone_nos"] = frappe.get_all(
			"Contact Phone",
			filters={
				"parenttype": "Contact",
				"parent": contact.name,
				"is_primary_phone": 0,
				"is_primary_mobile_no": 0,
			},
			fields=["phone"],
		)

		if contact.address and frappe.has_permission("Address", "read"):
			address = frappe.get_doc("Address", contact.address)
			contact["address"] = get_condensed_address(address)

	return contact_list
