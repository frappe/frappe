import frappe
import json

def get_email_accounts(user=None):
	if not user:
		user = frappe.session.user

	email_accounts = []

	accounts = frappe.get_all("User Email", filters={ "parent": user },
		fields=["email_account", "email_id"],
		distinct=True, order_by="idx")

	if not accounts:
		return None

	email_accounts.append({
		"email_account": "Sent",
		"email_id": "Sent Mail"
	})

	all_accounts = ",".join([ account.get("email_account") for account in accounts ])
	if len(accounts) > 1:
		email_accounts.append({
			"email_account": all_accounts,
			"email_id": "All Accounts"
		})

	email_accounts.extend(accounts)

	return {
		"email_accounts": email_accounts,
		"all_accounts": all_accounts
	}

@frappe.whitelist()
def create_email_flag_queue(communications, action, flag):
	""" create email flag queue to mark email either as read or unread """
	class Found(Exception):
		pass

	if not all([communications, action, flag]):
		return

	for communication in json.loads(communications or []):
		if not communication.get("uid", None):
			continue

		seen = 1 if action == "Read" else "Unread"
		# check if states are correct
		state = frappe.db.get_value("Communication", communication.get("name"), "seen")
		if (action =='Read' and state == 0) or (action =='Unread' and state == 1):
			try:
				queue = frappe.db.sql("""select name, action, flag from `tabEmail Flag Queue`
					where communication = %(name)s""", {"name":communication.get("name")}, as_dict=True)
				for q in queue:
					# is same email with same flag
					if q.flag == flag:
						# to prevent flag local and server states being out of sync
						if q.action != action:
							frappe.delete_doc("Email Flag Queue", q.name)
						raise Found

				flag_queue = frappe.get_doc({
					"doctype": "Email Flag Queue",
					"communication": communication.get("name"),
					"action": action,
					"flag": flag
				})
				flag_queue.save(ignore_permissions=True);
				frappe.db.set_value("Communication", communication.get("name"), "seen", seen, 
					update_modified=False)
			except Found:
				pass
