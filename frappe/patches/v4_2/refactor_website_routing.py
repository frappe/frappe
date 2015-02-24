from __future__ import unicode_literals
import frappe

def execute():
	# clear all static web pages
	frappe.delete_doc("DocType", "Website Route", force=1)
	frappe.delete_doc("Page", "sitemap-browser", force=1)
	frappe.db.sql("drop table if exists `tabWebsite Route`")
