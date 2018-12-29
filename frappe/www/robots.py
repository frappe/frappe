import frappe
from frappe.website.utils import get_website_settings

no_sitemap = 1
base_template_path = "templates/www/robots.txt"

def get_context(context):
	robots_txt = (
		get_website_settings('robots_txt') or
		(frappe.local.conf.robots_txt and
		frappe.read_file(frappe.local.conf.robots_txt)) or '')

	return { 'robots_txt': robots_txt }
