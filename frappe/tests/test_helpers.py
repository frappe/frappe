import frappe


def create_test_blog_post():
	test_blog_doc = frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Test Blog Post",
			"allow_guest_to_view": 1,
			"module": "Custom",
			"custom": 1,
			"title_field": "title",
			"autoname": "field:title",
			"naming_rule": "By fieldname",
			"make_attachments_public": 1,
			"owner": "Administrator",
			"fields": [
				{
					"fieldname": "blog_category",
					"fieldtype": "Link",
					"in_list_view": 1,
					"in_standard_filter": 1,
					"label": "Test Blog Category",
					"options": "Test Blog Category",
					"reqd": 1,
				},
				{
					"fieldname": "blogger",
					"fieldtype": "Link",
					"in_list_view": 1,
					"in_standard_filter": 1,
					"label": "Test Blogger",
					"options": "Test Blogger",
					"reqd": 1,
				},
				{
					"description": "Description for listing page, in plain text, only a couple of lines. (max 200 characters)",
					"fieldname": "blog_intro",
					"fieldtype": "Small Text",
					"label": "Blog Intro",
				},
				{
					"depends_on": "eval:doc.content_type === 'Rich Text'",
					"fieldname": "content",
					"fieldtype": "Text Editor",
					"ignore_xss_filter": 1,
					"in_global_search": 1,
					"label": "Content",
				},
				{
					"fieldname": "title",
					"fieldtype": "Data",
					"in_global_search": 1,
					"label": "Title",
					"no_copy": 1,
					"reqd": 1,
				},
				{
					"default": "0",
					"fieldname": "published",
					"fieldtype": "Check",
					"hidden": 1,
					"label": "Published",
				},
			],
			"permissions": [
				{
					"create": 1,
					"delete": 1,
					"email": 1,
					"print": 1,
					"read": 1,
					"report": 1,
					"role": "Website Manager",
					"share": 1,
					"write": 1,
				},
				{
					"create": 1,
					"email": 1,
					"print": 1,
					"read": 1,
					"report": 1,
					"role": "Blogger",
					"share": 1,
					"write": 1,
				},
			],
		}
	)
	test_blog_doc.insert(ignore_if_duplicate=True, ignore_links=True)
	create_test_blog_records()


def create_test_blog_records():
	test_blog_records = [
		{
			"blog_category": "_Test Blog Category",
			"blog_intro": "Test Blog Intro",
			"blogger": "_Test Blogger",
			"content": "Test Blog Content",
			"doctype": "Test Blog Post",
			"title": "_Test Blog Post",
			"published": 1,
		},
		{
			"blog_category": "_Test Blog Category 1",
			"blog_intro": "Test Blog Intro",
			"blogger": "_Test Blogger",
			"content": "Test Blog Content",
			"doctype": "Test Blog Post",
			"title": "_Test Blog Post 1",
			"published": 1,
		},
		{
			"blog_category": "_Test Blog Category 1",
			"blog_intro": "Test Blog Intro",
			"blogger": "_Test Blogger 1",
			"content": "Test Blog Content",
			"doctype": "Test Blog Post",
			"title": "_Test Blog Post 2",
			"published": 0,
		},
		{
			"blog_category": "_Test Blog Category 1",
			"blog_intro": "Test Blog Intro",
			"blogger": "_Test Blogger 2",
			"content": "Test Blog Content",
			"doctype": "Test Blog Post",
			"title": "_Test Blog Post 3",
			"published": 0,
		},
	]

	for r in test_blog_records:
		frappe.get_doc(r).insert(ignore_if_duplicate=True, ignore_links=True)


def create_test_blog_category():
	frappe.get_doc(
		{
			"doctype": "DocType",
			"autoname": "field:title",
			"name": "Test Blog Category",
			"module": "Custom",
			"custom": 1,
			"make_attachments_public": 1,
			"naming_rule": "By fieldname",
			"fields": [
				{
					"fieldname": "title",
					"fieldtype": "Data",
					"in_list_view": 1,
					"label": "Title",
					"no_copy": 1,
					"reqd": 1,
				},
				{
					"default": "1",
					"fieldname": "published",
					"fieldtype": "Check",
					"in_list_view": 1,
					"label": "Published",
				},
				{
					"depends_on": "published",
					"fieldname": "route",
					"fieldtype": "Data",
					"label": "Route",
					"read_only": 1,
					"unique": 1,
				},
			],
			"permissions": [
				{
					"create": 1,
					"delete": 1,
					"email": 1,
					"print": 1,
					"read": 1,
					"report": 1,
					"role": "Website Manager",
					"share": 1,
					"write": 1,
				},
				{"email": 1, "print": 1, "read": 1, "role": "Blogger"},
			],
		}
	).insert(ignore_if_duplicate=True, ignore_links=True)
	create_blog_category_records()


def create_blog_category_records():
	test_blog_category_records = [
		{"doctype": "Test Blog Category", "parent_website_route": "blog", "title": "_Test Blog Category"},
		{"doctype": "Test Blog Category", "parent_website_route": "blog", "title": "_Test Blog Category 1"},
		{"doctype": "Test Blog Category", "parent_website_route": "blog", "title": "_Test Blog Category 2"},
	]
	for r in test_blog_category_records:
		frappe.get_doc(r).insert(ignore_if_duplicate=True, ignore_links=True)


def create_test_blogger():
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Test Blogger",
			"module": "Custom",
			"custom": 1,
			"autoname": "field:short_name",
			"make_attachments_public": 1,
			"naming_rule": "By fieldname",
			"fields": [
				{"default": "0", "fieldname": "disabled", "fieldtype": "Check", "label": "Disabled"},
				{
					"description": "Will be used in url (usually first name).",
					"fieldname": "short_name",
					"fieldtype": "Data",
					"label": "Short Name",
					"reqd": 1,
					"unique": 1,
				},
				{
					"fieldname": "full_name",
					"fieldtype": "Data",
					"in_list_view": 1,
					"label": "Full Name",
					"reqd": 1,
				},
				{"fieldname": "user", "fieldtype": "Link", "label": "User", "options": "User"},
				{"fieldname": "bio", "fieldtype": "Small Text", "label": "Bio"},
				{"fieldname": "avatar", "fieldtype": "Attach Image", "label": "Avatar"},
			],
			"permissions": [
				{
					"create": 1,
					"delete": 1,
					"email": 1,
					"export": 1,
					"print": 1,
					"read": 1,
					"report": 1,
					"role": "Website Manager",
					"share": 1,
					"write": 1,
				},
				{"email": 1, "print": 1, "read": 1, "role": "Blogger", "share": 1, "write": 1},
			],
		}
	).insert(ignore_if_duplicate=True, ignore_links=True)
	create_test_blogger_records()


def create_test_blogger_records():
	test_blogger_records = [
		{"doctype": "Test Blogger", "full_name": "_Test Blogger", "short_name": "_Test Blogger"},
		{"doctype": "Test Blogger", "full_name": "_Test Blogger 1", "short_name": "_Test Blogger 1"},
		{"doctype": "Test Blogger", "full_name": "_Test Blogger 2", "short_name": "_Test Blogger 2"},
	]
	for r in test_blogger_records:
		frappe.get_doc(r).insert(ignore_if_duplicate=True, ignore_links=True)


def setup_for_tests():
	frappe.set_user("Administrator")
	frappe.delete_doc_if_exists("DocType", "Test Blog Post")
	frappe.delete_doc_if_exists("DocType", "Test Blog Category")
	frappe.delete_doc_if_exists("DocType", "Test Blogger")
	create_test_blog_category()
	create_test_blogger()
	create_test_blog_post()
