import frappe
from frappe.studio.ai.session import AISession
from frappe.studio.doctype.studio_app.test_studio_app import make_studio_app, make_studio_page
from frappe.tests import IntegrationTestCase


def make_studio_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0]})
		user.insert(ignore_permissions=True)
		user.add_roles("Studio User")
	return email


class TestPermissions(IntegrationTestCase):
	def setUp(self):
		self.owner = make_studio_user("studio-owner@example.com")
		self.other = make_studio_user("studio-other@example.com")
		app = make_studio_app(app_name="chat-" + frappe.generate_hash(length=8))
		page = make_studio_page(app.name)
		self.session = AISession.get_or_create(page.name, user=self.owner)
		self.session.append_message("user", "hello")
		self.message = frappe.db.get_value("Studio AI Message", {"session": self.session.name})

	def test_a_chat_is_read_by_its_user_and_administrator_only(self):
		for doctype, name in (("Studio AI Session", self.session.name), ("Studio AI Message", self.message)):
			self.assertTrue(frappe.has_permission(doctype, "read", name, user=self.owner))
			self.assertTrue(frappe.has_permission(doctype, "read", name, user="Administrator"))
			self.assertFalse(frappe.has_permission(doctype, "read", name, user=self.other))
			self.assertFalse(frappe.has_permission(doctype, "write", name, user=self.other))

	def test_deleting_an_app_takes_every_chat_on_its_pages(self):
		app = frappe.db.get_value("Studio Page", self.session._doc.page, "studio_app")
		with self.set_user(self.other):
			frappe.delete_doc("Studio App", app)

		self.assertFalse(frappe.db.exists("Studio AI Session", self.session.name))
		self.assertFalse(frappe.db.exists("Studio AI Message", self.message))

	def test_lists_show_only_your_own_chats(self):
		for doctype, name in (("Studio AI Session", self.session.name), ("Studio AI Message", self.message)):
			self.assertIn(name, frappe.get_list(doctype, pluck="name", user=self.owner))
			self.assertIn(name, frappe.get_list(doctype, pluck="name", user="Administrator"))
			self.assertNotIn(name, frappe.get_list(doctype, pluck="name", user=self.other))
