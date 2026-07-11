import frappe
from frappe.model.naming import make_autoname
from frappe.utils import sha256_hash

BATCH_SIZE = 1000


def is_sha256_hash(value: str) -> bool:
	return len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def hash_token(token: str | None) -> str | None:
	if not token:
		return None
	if is_sha256_hash(token):
		return token
	return sha256_hash(token)


def execute():
	token_table = frappe.qb.DocType("OAuth Bearer Token")
	start = 0
	while tokens := frappe.get_all(
		"OAuth Bearer Token",
		fields=["name", "access_token", "refresh_token"],
		order_by="creation asc, name asc",
		offset=start,
		limit=BATCH_SIZE,
	):
		for token in tokens:
			new_name = token.name
			if token.name == token.access_token or sha256_hash(token.name) == token.access_token:
				new_name = make_autoname("hash", "OAuth Bearer Token")
				while frappe.db.exists("OAuth Bearer Token", new_name):
					new_name = make_autoname("hash", "OAuth Bearer Token")

			(
				frappe.qb.update(token_table)
				.set(token_table.name, new_name)
				.set(token_table.access_token, hash_token(token.access_token))
				.set(token_table.refresh_token, hash_token(token.refresh_token))
				.where(token_table.name == token.name)
			).run()

		start += len(tokens)

	delete_duplicate_refresh_tokens()


def delete_duplicate_refresh_tokens():
	frappe.db.multisql(
		{
			"mariadb": """
				DELETE FROM `tabOAuth Bearer Token`
				WHERE name IN (
					SELECT name FROM (
						SELECT name, ROW_NUMBER() OVER (
							PARTITION BY refresh_token ORDER BY creation DESC, name DESC
						) AS row_num
						FROM `tabOAuth Bearer Token`
						WHERE refresh_token IS NOT NULL
					) duplicate_tokens
					WHERE row_num > 1
				)
			""",
			"postgres": """
				DELETE FROM "tabOAuth Bearer Token"
				WHERE name IN (
					SELECT name FROM (
						SELECT name, ROW_NUMBER() OVER (
							PARTITION BY refresh_token ORDER BY creation DESC, name DESC
						) AS row_num
						FROM "tabOAuth Bearer Token"
						WHERE refresh_token IS NOT NULL
					) AS duplicate_tokens
					WHERE row_num > 1
				)
			""",
		}
	)
