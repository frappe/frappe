# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE


from urllib.parse import quote

from googleapiclient.errors import HttpError

import frappe
from frappe import _
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.model.document import Document


class GoogleContacts(Document):
	def validate(self):
		if not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def get_access_token(self):
		if not self.refresh_token:
			button_label = frappe.bold(_("Allow Google Contacts Access"))
			raise frappe.ValidationError(_("Click on {0} to generate Refresh Token.").format(button_label))

		oauth_obj = GoogleOAuth("contacts")
		r = oauth_obj.refresh_access_token(
			self.get_password(fieldname="refresh_token", raise_exception=False)
		)

		return r.get("access_token")


@frappe.whitelist(methods=["POST"])
def authorize_access(g_contact, reauthorize=False, code=None):
	"""
	If no Authorization code get it from Google and then request for Refresh Token.
	Google Contact Name is set to flags to set_value after Authorization Code is obtained.
	"""

	oauth_code = (
		frappe.db.get_value("Google Contacts", g_contact, "authorization_code") if not code else code
	)
	oauth_obj = GoogleOAuth("contacts")

	if not oauth_code or reauthorize:
		return oauth_obj.get_authentication_url(
			{
				"g_contact": g_contact,
				"redirect": f"/app/Form/{quote('Google Contacts')}/{quote(g_contact)}",
			},
		)

	r = oauth_obj.authorize(oauth_code)
	frappe.db.set_value(
		"Google Contacts",
		g_contact,
		{"authorization_code": oauth_code, "refresh_token": r.get("refresh_token")},
	)


def get_google_contacts_object(g_contact):
	"""
	Returns an object of Google Calendar along with Google Calendar doc.
	"""
	account = frappe.get_doc("Google Contacts", g_contact)
	oauth_obj = GoogleOAuth("contacts")

	google_contacts = oauth_obj.get_google_service_object(
		account.get_access_token(),
		account.get_password(fieldname="indexing_refresh_token", raise_exception=False),
	)

	return google_contacts, account


@frappe.whitelist()
def sync(g_contact=None):
	filters = {"enable": 1}

	if g_contact:
		filters.update({"name": g_contact})

	google_contacts = frappe.get_list("Google Contacts", filters=filters)

	for g in google_contacts:
		return sync_contacts_from_google_contacts(g.name)


def sync_contacts_from_google_contacts(g_contact):
	"""
	Syncs Contacts from Google Contacts.
	https://developers.google.com/people/api/rest/v1/people.connections/list
	"""
	google_contacts, account = get_google_contacts_object(g_contact)

	if not account.pull_from_google_contacts:
		return

	results = []
	contacts_updated = 0

	sync_token = account.get_password(fieldname="next_sync_token", raise_exception=False) or None
	contacts = frappe._dict()

	while True:
		try:
			contacts = (
				google_contacts.people()
				.connections()
				.list(
					resourceName="people/me",
					pageToken=contacts.get("nextPageToken"),
					syncToken=sync_token,
					pageSize=2000,
					requestSyncToken=True,
					personFields="names,emailAddresses,organizations,phoneNumbers",
				)
				.execute()
			)

		except HttpError as err:
			frappe.throw(
				_(
					"Google Contacts - Could not sync contacts from Google Contacts {0}, error code {1}."
				).format(account.name, err.resp.status)
			)

		for contact in contacts.get("connections", []):
			results.append(contact)

		if not contacts.get("nextPageToken"):
			if contacts.get("nextSyncToken"):
				frappe.db.set_value(
					"Google Contacts", account.name, "next_sync_token", contacts.get("nextSyncToken")
				)
				frappe.db.commit()
			break

	frappe.db.set_value("Google Contacts", account.name, "last_sync_on", frappe.utils.now_datetime())

	for idx, connection in enumerate(results):
		frappe.publish_realtime(
			"import_google_contacts", dict(progress=idx + 1, total=len(results)), user=frappe.session.user
		)

		for name in connection.get("names"):
			if name.get("metadata").get("primary"):
				contacts_updated += 1
				contact = frappe.get_doc(
					{
						"doctype": "Contact",
						"first_name": name.get("givenName") or "",
						"middle_name": name.get("middleName") or "",
						"last_name": name.get("familyName") or "",
						"designation": get_indexed_value(connection.get("organizations"), 0, "title"),
						"pulled_from_google_contacts": 1,
						"google_contacts": account.name,
						"company_name": get_indexed_value(connection.get("organizations"), 0, "name"),
					}
				)

				for email in connection.get("emailAddresses", []):
					contact.add_email(
						email_id=email.get("value"), is_primary=1 if email.get("metadata").get("primary") else 0
					)

				for phone in connection.get("phoneNumbers", []):
					contact.add_phone(
						phone=phone.get("value"), is_primary_phone=1 if phone.get("metadata").get("primary") else 0
					)

				contact.insert(ignore_permissions=True)

	return (
		_("{0} Google Contacts synced.").format(contacts_updated)
		if contacts_updated > 0
		else _("No new Google Contacts synced.")
	)


def insert_contacts_to_google_contacts(doc, method=None):
	"""
	Syncs Contacts from Google Contacts.
	https://developers.google.com/people/api/rest/v1/people/createContact
	"""
	if (
		not frappe.db.exists("Google Contacts", {"name": doc.google_contacts})
		or doc.pulled_from_google_contacts
		or not doc.sync_with_google_contacts
	):
		return

	google_contacts, account = get_google_contacts_object(doc.google_contacts)

	if not account.push_to_google_contacts:
		return

	names = {"givenName": doc.first_name, "middleName": doc.middle_name, "familyName": doc.last_name}

	phoneNumbers = [{"value": phone_no.phone} for phone_no in doc.phone_nos]
	emailAddresses = [{"value": email_id.email_id} for email_id in doc.email_ids]

	try:
		contact = (
			google_contacts.people()
			.createContact(
				body={"names": [names], "phoneNumbers": phoneNumbers, "emailAddresses": emailAddresses}
			)
			.execute()
		)
		frappe.db.set_value("Contact", doc.name, "google_contacts_id", contact.get("resourceName"))
	except HttpError as err:
		frappe.msgprint(
			_("Google Calendar - Could not insert contact in Google Contacts {0}, error code {1}.").format(
				account.name, err.resp.status
			)
		)


def update_contacts_to_google_contacts(doc, method=None):
	"""
	Syncs Contacts from Google Contacts.
	https://developers.google.com/people/api/rest/v1/people/updateContact
	"""
	# Workaround to avoid triggering updation when Event is being inserted since
	# creation and modified are same when inserting doc
	if (
		not frappe.db.exists("Google Contacts", {"name": doc.google_contacts})
		or doc.modified == doc.creation
		or not doc.sync_with_google_contacts
	):
		return

	if doc.sync_with_google_contacts and not doc.google_contacts_id:
		# If sync_with_google_contacts is checked later, then insert the contact rather than updating it.
		insert_contacts_to_google_contacts(doc)
		return

	google_contacts, account = get_google_contacts_object(doc.google_contacts)

	if not account.push_to_google_contacts:
		return

	names = {"givenName": doc.first_name, "middleName": doc.middle_name, "familyName": doc.last_name}

	phoneNumbers = [{"value": phone_no.phone} for phone_no in doc.phone_nos]
	emailAddresses = [{"value": email_id.email_id} for email_id in doc.email_ids]

	try:
		contact = (
			google_contacts.people()
			.get(
				resourceName=doc.google_contacts_id,
				personFields="names,emailAddresses,organizations,phoneNumbers",
			)
			.execute()
		)

		contact["names"] = [names]
		contact["phoneNumbers"] = phoneNumbers
		contact["emailAddresses"] = emailAddresses

		google_contacts.people().updateContact(
			resourceName=doc.google_contacts_id,
			body={
				"names": [names],
				"phoneNumbers": phoneNumbers,
				"emailAddresses": emailAddresses,
				"etag": contact.get("etag"),
			},
			updatePersonFields="names,emailAddresses,organizations,phoneNumbers",
		).execute()
		frappe.msgprint(_("Contact Synced with Google Contacts."))
	except HttpError as err:
		frappe.msgprint(
			_("Google Contacts - Could not update contact in Google Contacts {0}, error code {1}.").format(
				account.name, err.resp.status
			)
		)


def get_indexed_value(d, index, key):
	if not d:
		return ""

	try:
		return d[index].get(key)
	except IndexError:
		return ""
