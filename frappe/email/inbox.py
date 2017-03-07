import frappe

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