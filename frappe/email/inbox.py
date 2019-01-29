from __future__ import unicode_literals
import frappe
import json

def get_email_accounts(user=None):
	if not user:
		user = frappe.session.user

	email_accounts = []

	accounts = frappe.get_all("User Email", filters={ "parent": user },
		fields=["email_account", "email_id", "enable_outgoing"],
		distinct=True, order_by="idx")

	if not accounts:
		return {
			"email_accounts": [],
			"all_accounts": ""
		}

	all_accounts = ",".join([ account.get("email_account") for account in accounts ])
	if len(accounts) > 1:
		email_accounts.append({
			"email_account": all_accounts,
			"email_id": "All Accounts"
		})
	email_accounts.extend(accounts)

	email_accounts.extend([
		{
			"email_account": "Sent",
			"email_id": "Sent Mail"
		},
		{
			"email_account": "Spam",
			"email_id": "Spam"
		},
		{
			"email_account": "Trash",
			"email_id": "Trash"
		}
	])

	return {
		"email_accounts": email_accounts,
		"all_accounts": all_accounts
	}

@frappe.whitelist()
def create_email_flag_queue(names, action):
	""" create email flag queue to mark email either as read or unread """
	def mark_as_seen_unseen(name, action):
		doc = frappe.get_doc("Communication", name)
		if action == "Read":
			doc.add_seen()
		else:
			_seen = json.loads(doc._seen or '[]')
			_seen = [user for user in _seen if frappe.session.user != user]
			doc.db_set('_seen', json.dumps(_seen), update_modified=False)

	if not all([names, action]):
		return

	for name in json.loads(names or []):
		uid, seen_status, email_account = frappe.db.get_value("Communication", name, 
			["ifnull(uid, -1)", "ifnull(seen, 0)", "email_account"])

		# can not mark email SEEN or UNSEEN without uid
		if not uid or uid == -1:
			continue

		seen = 1 if action == "Read" else 0
		# check if states are correct
		if (action =='Read' and seen_status == 0) or (action =='Unread' and seen_status == 1):
			create_new = True
			email_flag_queue = frappe.db.sql("""select name, action from `tabEmail Flag Queue`
				where communication = %(name)s and is_completed=0""", {"name":name}, as_dict=True)

			for queue in email_flag_queue:
				if queue.action != action:
					frappe.delete_doc("Email Flag Queue", queue.name, ignore_permissions=True)
				elif queue.action == action:
					# Read or Unread request for email is already available
					create_new = False

			if create_new:
				flag_queue = frappe.get_doc({
					"uid": uid,
					"action": action,
					"communication": name,
					"doctype": "Email Flag Queue",
					"email_account": email_account
				})
				flag_queue.save(ignore_permissions=True)
				frappe.db.set_value("Communication", name, "seen", seen, 
					update_modified=False)
				mark_as_seen_unseen(name, action)

@frappe.whitelist()
def mark_as_trash(communication):
	"""set email status to trash"""
	frappe.db.set_value("Communication", communication, "email_status", "Trash")

@frappe.whitelist()
def mark_as_spam(communication, sender):
	""" set email status to spam """
	email_rule = frappe.db.get_value("Email Rule", { "email_id": sender })
	if not email_rule:
		frappe.get_doc({
			"doctype": "Email Rule",
			"email_id": sender,
			"is_spam": 1	
		}).insert(ignore_permissions=True)
	frappe.db.set_value("Communication", communication, "email_status", "Spam")

def link_communication_to_document(doc, reference_doctype, reference_name, ignore_communication_links):
	if not ignore_communication_links:
		doc.reference_doctype = reference_doctype
		doc.reference_name = reference_name
		doc.status = "Linked"
		doc.save(ignore_permissions=True)

@frappe.whitelist()
def make_issue_from_communication(communication, ignore_communication_links=False):
	""" raise a issue from email """

	doc = frappe.get_doc("Communication", communication)
	issue = frappe.get_doc({
		"doctype": "Issue",
		"subject": doc.subject,
		"communication_medium": doc.communication_medium,
		"raised_by": doc.sender or "",
		"raised_by_phone": doc.phone_no or ""
	}).insert(ignore_permissions=True)

	link_communication_to_document(doc, "Issue", issue.name, ignore_communication_links)

	return issue.name

@frappe.whitelist()
def make_lead_from_communication(communication, ignore_communication_links=False):
	""" raise a issue from email """

	doc = frappe.get_doc("Communication", communication)
	frappe.errprint(doc.sender_full_name)
	lead_name = frappe.db.get_value("Lead", {"email_id": doc.sender,"mobile_no": doc.phone_no})
	if not lead_name:
		lead = frappe.get_doc({
			"doctype": "Lead",
			"lead_name": doc.sender_full_name,
			"email_id": doc.sender,
			"mobile_no": doc.phone_no
		})
		lead.flags.ignore_mandatory = True
		lead.flags.ignore_permissions = True
		lead.insert()

		lead_name = lead.name

	link_communication_to_document(doc, "Lead", lead_name, ignore_communication_links)
	return lead_name

@frappe.whitelist()
def make_opportunity_from_communication(communication, ignore_communication_links=False):
	doc = frappe.get_doc("Communication", communication)

	lead = doc.reference_name if doc.reference_doctype == "Lead" else None
	if not lead:
		lead = make_lead_from_communication(communication, ignore_communication_links=True)

	enquiry_from = "Lead"

	opportunity = frappe.get_doc({
		"doctype": "Opportunity",
		"enquiry_from": enquiry_from,
		"lead": lead
	}).insert(ignore_permissions=True)

	link_communication_to_document(doc, "Opportunity", opportunity.name, ignore_communication_links)

	return opportunity.name
