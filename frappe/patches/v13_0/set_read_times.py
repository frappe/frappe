import frappe
from frappe.utils import strip_html_tags, markdown
from math import ceil

def execute():
	frappe.reload_doc("website", "doctype", "blog_post")

	for blog in frappe.get_all("Blog Post"):
		blog = frappe.get_doc("Blog Post", blog.name)
		frappe.db.set_value("Blog Post", blog.name, "read_time", get_read_time(blog), update_modified=False)

def get_read_time(blog):
	content = blog.content or blog.content_html
	if blog.content_type == "Markdown":
		content = markdown(blog.content_md)

	total_words = len(strip_html_tags(content or "").split())
	return ceil(total_words/250)