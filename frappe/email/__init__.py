# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def sendmail_to_system_managers(subject, content):
	frappe.sendmail(recipients=get_system_managers(), subject=subject, content=content)


@frappe.whitelist()
def get_contact_list(txt, page_length=20) -> list[dict]:
	"""Return email ids for a multiselect field."""
	from frappe.contacts.doctype.contact.contact import get_full_name

	if cached_contacts := get_cached_contacts(txt):
		return cached_contacts[:page_length]

	fields = ["first_name", "middle_name", "last_name", "company_name"]
	contacts = frappe.get_list(
		"Contact",
		fields=fields + ["`tabContact Email`.email_id"],
		filters=[
			["Contact Email", "email_id", "is", "set"],
		],
		or_filters=[[field, "like", f"%{txt}%"] for field in fields]
		+ [["Contact Email", "email_id", "like", f"%{txt}%"]],
		limit_page_length=page_length,
	)

	# The multiselect field will store the `label` as the selected value.
	# The `value` is just used as a unique key to distinguish between the options.
	# https://github.com/frappe/frappe/blob/6c6a89bcdd9454060a1333e23b855d0505c9ebc2/frappe/public/js/frappe/form/controls/autocomplete.js#L29-L35
	result = [
		frappe._dict(
			value=d.email_id,
			label=d.email_id,
			description=get_full_name(d.first_name, d.middle_name, d.last_name, d.company_name),
		)
		for d in contacts
	]

	update_contact_cache(result)

	return result


def get_system_managers():
	return frappe.db.sql_list(
		"""select parent FROM `tabHas Role`
		WHERE role='System Manager'
		AND parent!='Administrator'
		AND parent IN (SELECT email FROM tabUser WHERE enabled=1)"""
	)


def get_cached_contacts(txt):
	contacts = frappe.cache.hget("contacts", frappe.session.user) or []

	if not contacts:
		return

	if not txt:
		return contacts

	return [
		d
		for d in contacts
		if (d.value and ((d.value and txt in d.value) or (d.description and txt in d.description)))
	]


def update_contact_cache(contacts):
	cached_contacts = frappe.cache.hget("contacts", frappe.session.user) or []

	uncached_contacts = [d for d in contacts if d not in cached_contacts]
	cached_contacts.extend(uncached_contacts)

	frappe.cache.hset("contacts", frappe.session.user, cached_contacts)
