import frappe
from frappe.model.naming import make_autoname
from frappe.utils import sha256_hash


def execute():
	token_table = frappe.qb.DocType("OAuth Bearer Token")
	tokens = frappe.get_all(
		"OAuth Bearer Token",
		fields=["name", "access_token", "refresh_token"],
	)

	for token in tokens:
		new_name = make_autoname("hash", "OAuth Bearer Token")
		while frappe.db.exists("OAuth Bearer Token", new_name):
			new_name = make_autoname("hash", "OAuth Bearer Token")

		query = (
			frappe.qb.update(token_table)
			.set(token_table.name, new_name)
			.set(
				token_table.access_token,
				sha256_hash(token.access_token) if token.access_token else token.access_token,
			)
			.where(token_table.name == token.name)
		)
		if token.refresh_token:
			query = query.set(token_table.refresh_token, sha256_hash(token.refresh_token))

		query.run()
