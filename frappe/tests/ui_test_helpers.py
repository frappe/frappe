import frappe
from frappe import _
from frappe.utils import add_to_date, now


def whitelist_for_tests(fn):
	if frappe.request and not (frappe.flags.in_test or getattr(frappe.local, "dev_server", 0)):
		frappe.throw("Cannot run UI tests. Use a development server with `bench start`")

	return frappe.whitelist()(fn)


@whitelist_for_tests
def create_if_not_exists(doc):
	"""Create records if they dont exist.
	Will check for uniqueness by checking if a record exists with these field value pairs

	:param doc: dict of field value pairs. can be a list of dict for multiple records.
	"""

	doc = frappe.parse_json(doc)

	if not isinstance(doc, list):
		docs = [doc]
	else:
		docs = doc

	names = []
	for doc in docs:
		doc = frappe._dict(doc)
		filters = doc.copy()
		filters.pop("doctype")
		name = frappe.db.exists(doc.doctype, filters)
		if not name:
			d = frappe.get_doc(doc)
			d.insert(ignore_permissions=True)
			name = d.name
		names.append(name)

	return names


@whitelist_for_tests
def create_todo_records():
	if frappe.db.get_all("ToDo", {"description": "this is first todo"}):
		return

	frappe.get_doc(
		{"doctype": "ToDo", "date": add_to_date(now(), days=7), "description": "this is first todo"}
	).insert()
	frappe.get_doc(
		{"doctype": "ToDo", "date": add_to_date(now(), days=-7), "description": "this is second todo"}
	).insert()
	frappe.get_doc(
		{"doctype": "ToDo", "date": add_to_date(now(), months=2), "description": "this is third todo"}
	).insert()
	frappe.get_doc(
		{"doctype": "ToDo", "date": add_to_date(now(), months=-2), "description": "this is fourth todo"}
	).insert()


@whitelist_for_tests
def create_communication_record():
	doc = frappe.get_doc(
		{
			"doctype": "Communication",
			"recipients": "test@gmail.com",
			"subject": "Test Form Communication 1",
			"communication_date": frappe.utils.now_datetime(),
		}
	)
	doc.insert()
	return doc


@whitelist_for_tests
def setup_workflow():
	from frappe.workflow.doctype.workflow.test_workflow import create_todo_workflow

	create_todo_workflow()
	create_todo_records()
	frappe.clear_cache()


@whitelist_for_tests
def create_contact_phone_nos_records():
	if frappe.db.get_all("Contact", {"first_name": "Test Contact"}):
		return

	doc = frappe.new_doc("Contact")
	doc.first_name = "Test Contact"
	for index in range(1000):
		doc.append("phone_nos", {"phone": "123456{}".format(index)})
	doc.insert()


@whitelist_for_tests
def create_doctype(name, fields):
	fields = frappe.parse_json(fields)
	if frappe.db.exists("DocType", name):
		return
	frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"fields": fields,
			"permissions": [{"role": "System Manager", "read": 1}],
			"name": name,
		}
	).insert()


@whitelist_for_tests
def create_child_doctype(name, fields):
	fields = frappe.parse_json(fields)
	if frappe.db.exists("DocType", name):
		return
	frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"istable": 1,
			"custom": 1,
			"fields": fields,
			"permissions": [{"role": "System Manager", "read": 1}],
			"name": name,
		}
	).insert()


@whitelist_for_tests
def create_contact_records():
	if frappe.db.get_all("Contact", {"first_name": "Test Form Contact 1"}):
		return

	insert_contact("Test Form Contact 1", "12345")
	insert_contact("Test Form Contact 2", "54321")
	insert_contact("Test Form Contact 3", "12345")


@whitelist_for_tests
def create_multiple_todo_records():
	if frappe.db.get_all("ToDo", {"description": "Multiple ToDo 1"}):
		return

	values = [("100{}".format(i), "Multiple ToDo {}".format(i)) for i in range(1, 1002)]

	frappe.db.bulk_insert("ToDo", fields=["name", "description"], values=set(values))


def insert_contact(first_name, phone_number):
	doc = frappe.get_doc({"doctype": "Contact", "first_name": first_name})
	doc.append("phone_nos", {"phone": phone_number})
	doc.insert()


@whitelist_for_tests
def create_form_tour():
	if frappe.db.exists("Form Tour", {"name": "Test Form Tour"}):
		return

	def get_docfield_name(filters):
		return frappe.db.get_value("DocField", filters, "name")

	tour = frappe.get_doc(
		{
			"doctype": "Form Tour",
			"title": "Test Form Tour",
			"reference_doctype": "Contact",
			"save_on_complete": 1,
			"steps": [
				{
					"title": "Test Title 1",
					"description": "Test Description 1",
					"has_next_condition": 1,
					"next_step_condition": "eval: doc.first_name",
					"field": get_docfield_name({"parent": "Contact", "fieldname": "first_name"}),
					"fieldname": "first_name",
					"fieldtype": "Data",
				},
				{
					"title": "Test Title 2",
					"description": "Test Description 2",
					"has_next_condition": 1,
					"next_step_condition": "eval: doc.last_name",
					"field": get_docfield_name({"parent": "Contact", "fieldname": "last_name"}),
					"fieldname": "last_name",
					"fieldtype": "Data",
				},
				{
					"title": "Test Title 3",
					"description": "Test Description 3",
					"field": get_docfield_name({"parent": "Contact", "fieldname": "phone_nos"}),
					"fieldname": "phone_nos",
					"fieldtype": "Table",
				},
				{
					"title": "Test Title 4",
					"description": "Test Description 4",
					"is_table_field": 1,
					"parent_field": get_docfield_name({"parent": "Contact", "fieldname": "phone_nos"}),
					"field": get_docfield_name({"parent": "Contact Phone", "fieldname": "phone"}),
					"next_step_condition": "eval: doc.phone",
					"has_next_condition": 1,
					"fieldname": "phone",
					"fieldtype": "Data",
				},
			],
		}
	)
	tour.insert()


@whitelist_for_tests
def create_data_for_discussions():
	web_page = create_web_page()
	create_topic_and_reply(web_page)


def create_web_page():
	web_page = frappe.db.exists("Web Page", {"route": "test-page-discussions"})
	if not web_page:
		web_page = frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "Test page for discussions",
				"route": "test-page-discussions",
				"published": True,
			}
		)
		web_page.save()

		web_page.append(
			"page_blocks",
			{
				"web_template": "Discussions",
				"web_template_values": frappe.as_json(
					{"title": "Discussions", "cta_title": "New Discussion", "docname": web_page.name}
				),
			},
		)
		web_page.save()

	return web_page


def create_topic_and_reply(web_page):
	topic = frappe.db.exists(
		"Discussion Topic", {"reference_doctype": "Web Page", "reference_docname": web_page.name}
	)

	if not topic:
		topic = frappe.get_doc(
			{
				"doctype": "Discussion Topic",
				"reference_doctype": "Web Page",
				"reference_docname": web_page.name,
				"title": "Test Topic",
			}
		)
		topic.save()

		reply = frappe.get_doc(
			{"doctype": "Discussion Reply", "topic": topic.name, "reply": "This is a test reply"}
		)

		reply.save()


@whitelist_for_tests
def update_webform_to_multistep():
	if not frappe.db.exists("Web Form", "update-profile-duplicate"):
		doc = frappe.get_doc("Web Form", "edit-profile")
		_doc = frappe.copy_doc(doc)
		_doc.is_multi_step_form = 1
		_doc.title = "update-profile-duplicate"
		_doc.route = "update-profile-duplicate"
		_doc.is_standard = False
		_doc.save()


@whitelist_for_tests
def update_child_table(name):
	doc = frappe.get_doc("DocType", name)
	if len(doc.fields) == 1:
		doc.append(
			"fields",
			{
				"fieldname": "doctype_to_link",
				"fieldtype": "Link",
				"in_list_view": 1,
				"label": "Doctype to Link",
				"options": "Doctype to Link",
			},
		)

		doc.save()


@whitelist_for_tests
def insert_translations():
	translation = [
		{
			"doctype": "Translation",
			"language": "de",
			"source_text": "Other",
			"translated_text": "Sonstiges",
		},
		{
			"doctype": "Translation",
			"language": "de",
			"source_text": "Genderqueer",
			"translated_text": "Nichtbinär",
		},
		{
			"doctype": "Translation",
			"language": "de",
			"source_text": "Non-Conforming",
			"translated_text": "Nicht konform",
		},
		{
			"doctype": "Translation",
			"language": "de",
			"source_text": "Prefer not to say",
			"translated_text": "Keine Angabe",
		},
	]

	for doc in translation:
		if not frappe.db.exists("doc"):
			frappe.get_doc(doc).insert()


@whitelist_for_tests
def create_blog_post():

	blog_category = frappe.get_doc(
		{"name": "general", "doctype": "Blog Category", "title": "general"}
	).insert(ignore_if_duplicate=True)

	blogger = frappe.get_doc(
		{
			"name": "attachment blogger",
			"doctype": "Blogger",
			"full_name": "attachment blogger",
			"short_name": "attachment blogger",
		}
	).insert(ignore_if_duplicate=True)

	doc = frappe.get_doc(
		{
			"name": "test-blog-attachment-post",
			"doctype": "Blog Post",
			"title": "test-blog-attachment-post",
			"blog_category": blog_category.name,
			"blogger": blogger.name,
			"content_type": "Rich Text",
		},
	).insert(ignore_if_duplicate=True)

	return doc
<<<<<<< HEAD
=======


def create_test_user():
	if frappe.db.exists("User", UI_TEST_USER):
		return

	user = frappe.new_doc("User")
	user.email = UI_TEST_USER
	user.first_name = "Frappe"
	user.new_password = frappe.local.conf.admin_password
	user.send_welcome_email = 0
	user.time_zone = "Asia/Kolkata"
	user.flags.ignore_password_policy = True
	user.insert(ignore_if_duplicate=True)

	user.reload()

	blocked_roles = {"Administrator", "Guest", "All"}
	all_roles = set(frappe.get_all("Role", pluck="name"))

	for role in all_roles - blocked_roles:
		user.append("roles", {"role": role})

	user.save()


@whitelist_for_tests
def setup_tree_doctype():
	frappe.delete_doc_if_exists("DocType", "Custom Tree", force=True)

	frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"fields": [
				{"fieldname": "tree", "fieldtype": "Data", "label": "Tree"},
			],
			"permissions": [{"role": "System Manager", "read": 1}],
			"name": "Custom Tree",
			"is_tree": True,
			"naming_rule": "By fieldname",
			"autoname": "field:tree",
		}
	).insert()

	if not frappe.db.exists("Custom Tree", "All Trees"):
		frappe.get_doc({"doctype": "Custom Tree", "tree": "All Trees"}).insert()


@whitelist_for_tests
def setup_image_doctype():
	frappe.delete_doc_if_exists("DocType", "Custom Image", force=True)

	frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"fields": [
				{"fieldname": "image", "fieldtype": "Attach Image", "label": "Image"},
			],
			"permissions": [{"role": "System Manager", "read": 1}],
			"name": "Custom Image",
			"image_field": "image",
		}
	).insert()


@whitelist_for_tests
def setup_inbox():
	frappe.db.sql("DELETE FROM `tabUser Email`")

	user = frappe.get_doc("User", frappe.session.user)
	user.append("user_emails", {"email_account": "Email Linking"})
	user.save()


@whitelist_for_tests
def setup_default_view(view, force_reroute=None):
	frappe.delete_doc_if_exists("Property Setter", "Event-main-default_view")
	frappe.delete_doc_if_exists("Property Setter", "Event-main-force_re_route_to_default_view")

	frappe.get_doc(
		{
			"is_system_generated": 0,
			"doctype_or_field": "DocType",
			"doc_type": "Event",
			"property": "default_view",
			"property_type": "Select",
			"value": view,
			"doctype": "Property Setter",
		}
	).insert()

	if force_reroute:
		frappe.get_doc(
			{
				"is_system_generated": 0,
				"doctype_or_field": "DocType",
				"doc_type": "Event",
				"property": "force_re_route_to_default_view",
				"property_type": "Check",
				"value": "1",
				"doctype": "Property Setter",
			}
		).insert()


@whitelist_for_tests
def create_note():
	if not frappe.db.exists("Note", "Routing Test"):
		frappe.get_doc({"doctype": "Note", "title": "Routing Test"}).insert()


@whitelist_for_tests
def create_kanban():
	if not frappe.db.exists("Custom Field", "Note-kanban"):
		frappe.get_doc(
			{
				"is_system_generated": 0,
				"dt": "Note",
				"label": "Kanban",
				"fieldname": "kanban",
				"insert_after": "seen_by",
				"fieldtype": "Select",
				"options": "Open\nClosed",
				"doctype": "Custom Field",
			}
		).insert()

	if not frappe.db.exists("Kanban Board", "_Note _Kanban"):
		frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"name": "_Note _Kanban",
				"kanban_board_name": "_Note _Kanban",
				"reference_doctype": "Note",
				"field_name": "kanban",
				"private": 1,
				"show_labels": 0,
				"columns": [
					{
						"column_name": "Open",
						"status": "Active",
						"indicator": "Gray",
					},
					{
						"column_name": "Closed",
						"status": "Active",
						"indicator": "Gray",
					},
				],
			}
		).insert()


@whitelist_for_tests
def create_todo(description):
	frappe.get_doc({"doctype": "ToDo", "description": description}).insert()


@whitelist_for_tests
def create_admin_kanban():
	if not frappe.db.exists("Kanban Board", "Admin Kanban"):
		frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"name": "Admin Kanban",
				"owner": "Administrator",
				"kanban_board_name": "Admin Kanban",
				"reference_doctype": "ToDo",
				"field_name": "status",
				"private": 0,
				"show_labels": 0,
				"columns": [
					{
						"column_name": "Open",
						"status": "Active",
						"indicator": "Gray",
					},
					{
						"column_name": "Closed",
						"status": "Active",
						"indicator": "Gray",
					},
				],
			}
		).insert()


@whitelist_for_tests
def add_remove_role(action, user, role):
	user_doc = frappe.get_doc("User", user)
	if action == "remove":
		user_doc.remove_roles(role)
	else:
		user_doc.add_roles(role)
>>>>>>> 49143922c5 (chore: Kanban and ToDo UI test helpers)
