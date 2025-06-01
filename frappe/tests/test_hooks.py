# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts
from nts.cache_manager import clear_controller_cache
from nts.desk.doctype.todo.todo import ToDo
from nts.tests.test_api import ntsAPITestCase
from nts.tests.utils import ntsTestCase, patch_hooks


class TestHooks(ntsTestCase):
	def test_hooks(self):
		hooks = nts.get_hooks()
		self.assertTrue(isinstance(hooks.get("app_name"), list))
		self.assertTrue(isinstance(hooks.get("doc_events"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue(
			"nts.desk.notifications.clear_doctype_notifications"
			in hooks.get("doc_events").get("*").get("on_update")
		)

	def test_override_doctype_class(self):
		from nts import hooks

		# Set hook
		hooks.override_doctype_class = {"ToDo": ["nts.tests.test_hooks.CustomToDo"]}

		# Clear cache
		nts.cache.delete_value("app_hooks")
		clear_controller_cache("ToDo")

		todo = nts.get_doc(doctype="ToDo", description="asdf")
		self.assertTrue(isinstance(todo, CustomToDo))

	def test_has_permission(self):
		from nts import hooks

		# Set hook
		address_has_permission_hook = hooks.has_permission.get("Address", [])
		if isinstance(address_has_permission_hook, str):
			address_has_permission_hook = [address_has_permission_hook]

		address_has_permission_hook.append("nts.tests.test_hooks.custom_has_permission")

		hooks.has_permission["Address"] = address_has_permission_hook

		wildcard_has_permission_hook = hooks.has_permission.get("*", [])
		if isinstance(wildcard_has_permission_hook, str):
			wildcard_has_permission_hook = [wildcard_has_permission_hook]

		wildcard_has_permission_hook.append("nts.tests.test_hooks.custom_has_permission")

		hooks.has_permission["*"] = wildcard_has_permission_hook

		# Clear cache
		nts.cache.delete_value("app_hooks")

		# Init User and Address
		username = "test@example.com"
		user = nts.get_doc("User", username)
		user.add_roles("System Manager")
		address = nts.new_doc("Address")

		# Create Note
		note = nts.new_doc("Note")
		note.public = 1

		# Test!
		self.assertTrue(nts.has_permission("Address", doc=address, user=username))
		self.assertTrue(nts.has_permission("Note", doc=note, user=username))

		address.flags.dont_touch_me = True
		self.assertFalse(nts.has_permission("Address", doc=address, user=username))

		note.flags.dont_touch_me = True
		self.assertFalse(nts.has_permission("Note", doc=note, user=username))

	def test_ignore_links_on_delete(self):
		email_unsubscribe = nts.get_doc(
			{"doctype": "Email Unsubscribe", "email": "test@example.com", "global_unsubscribe": 1}
		).insert()

		event = nts.get_doc(
			{
				"doctype": "Event",
				"subject": "Test Event",
				"starts_on": "2022-12-21",
				"event_type": "Public",
				"event_participants": [
					{
						"reference_doctype": "Email Unsubscribe",
						"reference_docname": email_unsubscribe.name,
					}
				],
			}
		).insert()
		self.assertRaises(nts.LinkExistsError, email_unsubscribe.delete)

		event.event_participants = []
		event.save()

		todo = nts.get_doc(
			{
				"doctype": "ToDo",
				"description": "Test ToDo",
				"reference_type": "Event",
				"reference_name": event.name,
			}
		)
		todo.insert()

		event.delete()


class TestAPIHooks(ntsAPITestCase):
	def test_auth_hook(self):
		with patch_hooks({"auth_hooks": ["nts.tests.test_hooks.custom_auth"]}):
			site_url = nts.utils.get_site_url(nts.local.site)
			response = self.get(
				site_url + "/api/method/nts.auth.get_logged_user",
				headers={"Authorization": "Bearer set_test_example_user"},
			)
			# Test!
			self.assertTrue(response.json.get("message") == "test@example.com")


def custom_has_permission(doc, ptype, user):
	if doc.flags.dont_touch_me:
		return False


def custom_auth():
	auth_type, token = nts.get_request_header("Authorization", "Bearer ").split(" ")
	if token == "set_test_example_user":
		nts.set_user("test@example.com")


class CustomToDo(ToDo):
	pass
