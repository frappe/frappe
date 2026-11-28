from datetime import timedelta

import frappe
from frappe.contacts.doctype.contact.contact import reads_contacts_only_as_owner


def execute():
	"""Hand contacts created for a user (within 30 minutes of the user) to Administrator when their
	owner can read contacts only as owner."""
	contact = frappe.qb.DocType("Contact")
	user = frappe.qb.DocType("User")
	contacts = (
		frappe.qb.from_(contact)
		.join(user)
		.on(user.name == contact.user)
		.select(contact.name, contact.owner, contact.creation, user.creation.as_("user_creation"))
		.where(contact.owner != contact.user)
		.run(as_dict=True)
	)
	contacts = [c for c in contacts if timedelta(0) <= c.creation - c.user_creation <= timedelta(minutes=30)]
	owners_only_as_owner = {
		owner for owner in {c.owner for c in contacts} if reads_contacts_only_as_owner(owner)
	}
	frappe.db.bulk_update(
		"Contact",
		{c.name: {"owner": "Administrator"} for c in contacts if c.owner in owners_only_as_owner},
		update_modified=False,
	)
