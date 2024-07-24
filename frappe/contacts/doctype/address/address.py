# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

from jinja2 import TemplateSyntaxError

import frappe
from frappe import _, throw
from frappe.contacts.address_and_contact import set_link_title
from frappe.core.doctype.dynamic_link.dynamic_link import deduplicate_dynamic_links
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cstr


class Address(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.dynamic_link.dynamic_link import DynamicLink
		from frappe.types import DF

		address_line1: DF.Data
		address_line2: DF.Data | None
		address_title: DF.Data | None
		address_type: DF.Literal[
			"Billing",
			"Shipping",
			"Office",
			"Personal",
			"Plant",
			"Postal",
			"Shop",
			"Subsidiary",
			"Warehouse",
			"Current",
			"Permanent",
			"Other",
		]
		city: DF.Data
		country: DF.Link
		county: DF.Data | None
		disabled: DF.Check
		email_id: DF.Data | None
		fax: DF.Data | None
		is_primary_address: DF.Check
		is_shipping_address: DF.Check
		links: DF.Table[DynamicLink]
		phone: DF.Data | None
		pincode: DF.Data | None
		state: DF.Data | None
	# end: auto-generated types

	def __setup__(self):
		self.flags.linked = False

	def autoname(self):
		if not self.address_title:
			if self.links:
				self.address_title = self.links[0].link_name

		if self.address_title:
			self.name = cstr(self.address_title).strip() + "-" + cstr(_(self.address_type)).strip()
			if frappe.db.exists("Address", self.name):
				self.name = make_autoname(
					cstr(self.address_title).strip() + "-" + cstr(self.address_type).strip() + "-.#",
					ignore_validate=True,
				)
		else:
			throw(_("Address Title is mandatory."))

	def validate(self):
		self.link_address()
		self.validate_preferred_address()
		set_link_title(self)
		deduplicate_dynamic_links(self)

	def link_address(self):
		"""Link address based on owner"""
		if not self.links:
			contact_name = frappe.db.get_value("Contact", {"email_id": self.owner})
			if contact_name:
				contact = frappe.get_cached_doc("Contact", contact_name)
				for link in contact.links:
					self.append("links", dict(link_doctype=link.link_doctype, link_name=link.link_name))
				return True

		return False

	def validate_preferred_address(self):
		preferred_fields = ["is_primary_address", "is_shipping_address"]

		for field in preferred_fields:
			if self.get(field):
				for link in self.links:
					address = get_preferred_address(link.link_doctype, link.link_name, field)

					if address:
						update_preferred_address(address, field)

	def get_display(self):
		return get_address_display(self.as_dict())

	def has_link(self, doctype, name):
		for link in self.links:
			if link.link_doctype == doctype and link.link_name == name:
				return True

	def has_common_link(self, doc):
		reference_links = [(link.link_doctype, link.link_name) for link in doc.links]
		for link in self.links:
			if (link.link_doctype, link.link_name) in reference_links:
				return True

		return False


def get_preferred_address(doctype, name, preferred_key="is_primary_address"):
	if preferred_key in ["is_shipping_address", "is_primary_address"]:
		address = frappe.db.sql(
			""" SELECT
				addr.name
			FROM
				`tabAddress` addr, `tabDynamic Link` dl
			WHERE
				dl.parent = addr.name and dl.link_doctype = {} and
				dl.link_name = {} and ifnull(addr.disabled, 0) = 0 and
				{} = {}
			""".format("%s", "%s", preferred_key, "%s"),
			(doctype, name, 1),
			as_dict=1,
		)

		if address:
			return address[0].name

	return


@frappe.whitelist()
def get_default_address(doctype: str, name: str | None, sort_key: str = "is_primary_address") -> str | None:
	"""Return default Address name for the given doctype, name."""
	if sort_key not in ["is_shipping_address", "is_primary_address"]:
		return None

	addresses = frappe.get_all(
		"Address",
		filters=[
			["Dynamic Link", "link_doctype", "=", doctype],
			["Dynamic Link", "link_name", "=", name],
			["disabled", "=", 0],
		],
		pluck="name",
		order_by=f"{sort_key} DESC",
		limit=1,
	)

	return addresses[0] if addresses else None


@frappe.whitelist()
def get_address_display(address_dict: dict | str | None) -> str | None:
	return render_address(address_dict)


def render_address(address: dict | str | None, check_permissions=True) -> str | None:
	if not address:
		return

	if not isinstance(address, dict):
		address = frappe.get_cached_doc("Address", address)
		if check_permissions:
			address.check_permission()
		address = address.as_dict()

	name, template = get_address_templates(address)

	try:
		return frappe.render_template(template, address)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template {0}").format(name))


def get_territory_from_address(address):
	"""Tries to match city, state and country of address to existing territory"""
	if not address:
		return

	if isinstance(address, str):
		address = frappe.get_cached_doc("Address", address)

	territory = None
	for fieldname in ("city", "state", "country"):
		if address.get(fieldname):
			territory = frappe.db.get_value("Territory", address.get(fieldname))
			if territory:
				break

	return territory


def get_list_context(context=None):
	return {
		"title": _("Addresses"),
		"get_list": get_address_list,
		"row_template": "templates/includes/address_row.html",
		"no_breadcrumbs": True,
	}


def get_address_list(doctype, txt, filters, limit_start, limit_page_length=20, order_by=None):
	from frappe.www.list import get_list

	user = frappe.session.user

	if not filters:
		filters = []
	filters.append(("Address", "owner", "=", user))

	return get_list(doctype, txt, filters, limit_start, limit_page_length)


def has_website_permission(doc, ptype, user, verbose=False):
	"""Return True if there is a related lead or contact related to this document."""
	contact_name = frappe.db.get_value("Contact", {"email_id": frappe.session.user})

	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		return contact.has_common_link(doc)

	return False


def get_address_templates(address):
	result = frappe.db.get_value(
		"Address Template", {"country": address.get("country")}, ["name", "template"]
	)

	if not result:
		result = frappe.db.get_value("Address Template", {"is_default": 1}, ["name", "template"])

	if not result:
		frappe.throw(
			_(
				"No default Address Template found. Please create a new one from Setup > Printing and Branding > Address Template."
			)
		)
	else:
		return result


def get_company_address(company):
	ret = frappe._dict()

	if company:
		ret.company_address = get_default_address("Company", company)
		ret.company_address_display = render_address(ret.company_address, check_permissions=False)

	return ret


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def address_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.search import search_widget

	_filters = []
	if link_doctype := filters.pop("link_doctype", None):
		_filters.append(["Dynamic Link", "link_doctype", "=", link_doctype])

	if link_name := filters.pop("link_name", None):
		_filters.append(["Dynamic Link", "link_name", "=", link_name])

	_filters.extend([key, "=", value] for key, value in filters.items())

	return search_widget(
		"Address", txt, filters=_filters, searchfield=searchfield, start=start, page_length=page_len
	)


def get_condensed_address(doc, no_title=False):
	fields = [
		"address_title",
		"address_line1",
		"address_line2",
		"city",
		"county",
		"state",
		"country",
	]
	if no_title:
		fields.remove("address_title")
	return ", ".join(doc.get(d) for d in fields if doc.get(d))


def update_preferred_address(address, field):
	frappe.db.set_value("Address", address, field, 0)


def get_address_display_list(doctype: str, name: str) -> list[dict]:
	if not frappe.has_permission("Address", "read"):
		return []

	address_list = frappe.get_list(
		"Address",
		filters=[
			["Dynamic Link", "link_doctype", "=", doctype],
			["Dynamic Link", "link_name", "=", name],
			["Dynamic Link", "parenttype", "=", "Address"],
		],
		fields=["*"],
		order_by="is_primary_address DESC, `tabAddress`.creation ASC",
	)
	for a in address_list:
		a["display"] = get_address_display(a)

	return address_list
