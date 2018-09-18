from __future__ import unicode_literals
import frappe

def execute():
	submittable_docs = frappe.db.get_all("DocType", {"is_submittable": 1})
	for doc in submittable_docs:
		if frappe.db.exists("DocType", doc["name"]):
			meta = frappe.get_meta(doc["name"])
			if not meta.has_field("submission_date"):
				frappe.db.sql("""alter table `tab{0}` add column submission_date datetime(6)""".format(doc["name"]))
			if not meta.has_field("submitted_by"):
				frappe.db.sql("""alter table `tab{0}` add column submitted_by varchar(255)""".format(doc["name"]))
