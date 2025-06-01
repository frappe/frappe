import nts


def execute():
	email_unsubscribe = [
		{"email": "admin@example.com", "global_unsubscribe": 1},
		{"email": "guest@example.com", "global_unsubscribe": 1},
	]

	for unsubscribe in email_unsubscribe:
		if not nts.get_all("Email Unsubscribe", filters=unsubscribe):
			doc = nts.new_doc("Email Unsubscribe")
			doc.update(unsubscribe)
			doc.insert(ignore_permissions=True)
