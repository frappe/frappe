import frappe
from frappe.query_builder.functions import Substring


def execute():
	site_url = frappe.utils.get_url()
	File = frappe.qb.DocType("File")

	(
		frappe.qb.update(File)
		.set(
			File.file_url,
			Substring(
				File.file_url,
				# MariaDB starts counting from 1
				len(site_url) + 1,
				# PyPika requires a length, so providing a "safe" value
				# Max. characters in a TEXT column in MariaDB / Postgres is 65,535
				9999999,
			),
		)
		.where(File.is_folder == 0)
		.where(File.file_url.like(f"{site_url}%/files/%"))
	).run()
