import re

import nts
from nts.core.doctype.user.user import create_contact


def execute():
	"""Create Contact for each User if not present"""
	nts.reload_doc("integrations", "doctype", "google_contacts")
	nts.reload_doc("contacts", "doctype", "contact")
	nts.reload_doc("core", "doctype", "dynamic_link")

	contact_meta = nts.get_meta("Contact")
	if contact_meta.has_field("phone_nos") and contact_meta.has_field("email_ids"):
		nts.reload_doc("contacts", "doctype", "contact_phone")
		nts.reload_doc("contacts", "doctype", "contact_email")

	users = nts.get_all("User", filters={"name": ("not in", "Administrator, Guest")}, fields=["*"])
	for user in users:
		if nts.db.exists("Contact", {"email_id": user.email}) or nts.db.exists(
			"Contact Email", {"email_id": user.email}
		):
			continue
		if user.first_name:
			user.first_name = re.sub("[<>]+", "", nts.safe_decode(user.first_name))
		if user.last_name:
			user.last_name = re.sub("[<>]+", "", nts.safe_decode(user.last_name))
		create_contact(user, ignore_links=True, ignore_mandatory=True)
