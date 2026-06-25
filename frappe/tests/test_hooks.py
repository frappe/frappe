# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.cache_manager import clear_controller_cache
from frappe.desk.doctype.todo.todo import ToDo
from frappe.model.document import _accepts_method_argument
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.tests.test_api import FrappeAPITestCase


class TestHooks(IntegrationTestCase):
	def test_hooks(self):
		hooks = frappe.get_hooks()
		self.assertTrue(isinstance(hooks.get("app_name"), list))
		self.assertTrue(isinstance(hooks.get("doc_events"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue(
			"frappe.desk.notifications.clear_doctype_notifications"
			in hooks.get("doc_events").get("*").get("on_update")
		)

	def test_override_doctype_class(self):
		from frappe import hooks

		# Set hook
		hooks.override_doctype_class = {"ToDo": ["frappe.tests.test_hooks.CustomToDo"]}

		# Clear cache
		frappe.client_cache.delete_value("app_hooks")
		clear_controller_cache("ToDo")

		todo = frappe.get_doc(doctype="ToDo", description="asdf")
		self.assertTrue(isinstance(todo, CustomToDo))

	def test_has_permission(self):
		from frappe import hooks

		# Set hook
		address_has_permission_hook = hooks.has_permission.get("Address", [])
		if isinstance(address_has_permission_hook, str):
			address_has_permission_hook = [address_has_permission_hook]

		address_has_permission_hook.append("frappe.tests.test_hooks.custom_has_permission")

		hooks.has_permission["Address"] = address_has_permission_hook

		wildcard_has_permission_hook = hooks.has_permission.get("*", [])
		if isinstance(wildcard_has_permission_hook, str):
			wildcard_has_permission_hook = [wildcard_has_permission_hook]

		wildcard_has_permission_hook.append("frappe.tests.test_hooks.custom_has_permission")

		hooks.has_permission["*"] = wildcard_has_permission_hook

		# Clear cache
		frappe.client_cache.delete_value("app_hooks")

		# Init User and Address
		username = "test@example.com"
		user = frappe.get_doc("User", username)
		user.add_roles("System Manager")
		address = frappe.new_doc("Address")

		# Create Note
		note = frappe.new_doc("Note")
		note.public = 1

		# Test!
		self.assertTrue(frappe.has_permission("Address", doc=address, user=username))
		self.assertTrue(frappe.has_permission("Note", doc=note, user=username))

		address.flags.dont_touch_me = True
		self.assertFalse(frappe.has_permission("Address", doc=address, user=username))

		note.flags.dont_touch_me = True
		self.assertFalse(frappe.has_permission("Note", doc=note, user=username))

	def test_ignore_links_on_delete(self):
		email_unsubscribe = frappe.get_doc(
			{"doctype": "Email Unsubscribe", "email": "test@example.com", "global_unsubscribe": 1}
		).insert()

		event = frappe.get_doc(
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
		self.assertRaises(frappe.LinkExistsError, email_unsubscribe.delete)

		event.event_participants = []
		event.save()

		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Test ToDo",
				"reference_type": "Event",
				"reference_name": event.name,
			}
		)
		todo.insert()

		event.delete()

	def test_fixture_prefix(self):
		import os
		import shutil

		from frappe import hooks
		from frappe.utils.fixtures import export_fixtures

		app = "frappe"
		if os.path.isdir(frappe.get_app_path(app, "fixtures")):
			shutil.rmtree(frappe.get_app_path(app, "fixtures"))

		# use any set of core doctypes for test purposes
		hooks.fixtures = [
			{"dt": "User"},
			{"dt": "Contact"},
			{"dt": "Role"},
		]
		hooks.fixture_auto_order = False
		# every call to frappe.get_hooks loads the hooks module into cache
		# therefor the cache has to be invalidated after every manual overwriting of hooks
		# TODO replace with a more elegant solution if there is one or build a util function for this purpose
		if frappe._load_app_hooks in frappe.local.request_cache.keys():
			del frappe.local.request_cache[frappe._load_app_hooks]
		self.assertEqual([False], frappe.get_hooks("fixture_auto_order", app_name=app))
		self.assertEqual(
			[
				{"dt": "User"},
				{"dt": "Contact"},
				{"dt": "Role"},
			],
			frappe.get_hooks("fixtures", app_name=app),
		)

		export_fixtures(app)
		# use assertCountEqual (replaced assertItemsEqual), beacuse os.listdir might return the list in a different order, depending on OS
		self.assertCountEqual(
			["user.json", "contact.json", "role.json"], os.listdir(frappe.get_app_path(app, "fixtures"))
		)

		hooks.fixture_auto_order = True
		del frappe.local.request_cache[frappe._load_app_hooks]
		self.assertEqual([True], frappe.get_hooks("fixture_auto_order", app_name=app))

		shutil.rmtree(frappe.get_app_path(app, "fixtures"))
		export_fixtures(app)
		self.assertCountEqual(
			["1_user.json", "2_contact.json", "3_role.json"],
			os.listdir(frappe.get_app_path(app, "fixtures")),
		)

		hooks.fixtures = [
			{"dt": "User", "prefix": "my_prefix"},
			{"dt": "Contact"},
			{"dt": "Role"},
		]
		hooks.fixture_auto_order = False

		del frappe.local.request_cache[frappe._load_app_hooks]
		shutil.rmtree(frappe.get_app_path(app, "fixtures"))
		export_fixtures(app)
		self.assertCountEqual(
			["my_prefix_user.json", "contact.json", "role.json"],
			os.listdir(frappe.get_app_path(app, "fixtures")),
		)

		hooks.fixture_auto_order = True
		del frappe.local.request_cache[frappe._load_app_hooks]
		shutil.rmtree(frappe.get_app_path(app, "fixtures"))
		export_fixtures(app)
		self.assertCountEqual(
			["1_my_prefix_user.json", "2_contact.json", "3_role.json"],
			os.listdir(frappe.get_app_path(app, "fixtures")),
		)


class TestDocEventHandlerSignature(UnitTestCase):
	# `_accepts_method_argument` inspects a doc_events handler's signature to decide
	# whether it should be called as `handler(doc)` or `handler(doc, method, ...)`.

	def test_handler_without_method_arg(self):
		self.assertFalse(_accepts_method_argument(lambda doc: None))

	def test_handler_with_method_arg(self):
		self.assertTrue(_accepts_method_argument(lambda doc, method: None))

	def test_handler_with_method_default(self):
		self.assertTrue(_accepts_method_argument(lambda doc, method=None: None))

	def test_handler_with_var_positional(self):
		self.assertTrue(_accepts_method_argument(lambda *args: None))
		self.assertTrue(_accepts_method_argument(lambda doc, *args: None))

	def test_handler_with_keyword_only_args(self):
		self.assertFalse(_accepts_method_argument(lambda doc, *, key=None: None))


class TestDocEventHandlerDispatch(IntegrationTestCase):
	# Register doc_events handlers of each style and ensure `run_method` invokes
	# them with the expected arguments.

	def setUp(self):
		frappe.flags.doc_event_calls = []

	def _run_with_handlers(self, handlers):
		method = "on_test_doc_event"
		self.addCleanup(_reset_doc_events_cache)
		with self.patch_hooks({"doc_events": {"ToDo": {method: handlers}}}):
			frappe.local.doc_events_hooks = None
			frappe.new_doc("ToDo", description="doc event test").run_method(method)

	def test_doc_only_handler_called_without_method(self):
		self._run_with_handlers(["frappe.tests.test_hooks.handler_doc_only"])
		self.assertEqual(frappe.flags.doc_event_calls, [("doc_only", "ToDo", "<no-method>")])

	def test_doc_method_handler_called_with_method(self):
		self._run_with_handlers(["frappe.tests.test_hooks.handler_doc_method"])
		self.assertEqual(frappe.flags.doc_event_calls, [("doc_method", "ToDo", "on_test_doc_event")])

	def test_doc_method_default_handler_called_with_method(self):
		self._run_with_handlers(["frappe.tests.test_hooks.handler_doc_method_default"])
		self.assertEqual(frappe.flags.doc_event_calls, [("doc_method_default", "ToDo", "on_test_doc_event")])

	def test_var_positional_handler_called_with_method(self):
		self._run_with_handlers(["frappe.tests.test_hooks.handler_doc_varargs"])
		self.assertEqual(frappe.flags.doc_event_calls, [("doc_varargs", "ToDo", "on_test_doc_event")])

	def test_mixed_handlers_all_called_correctly(self):
		self._run_with_handlers(
			[
				"frappe.tests.test_hooks.handler_doc_only",
				"frappe.tests.test_hooks.handler_doc_method",
			]
		)
		self.assertEqual(
			frappe.flags.doc_event_calls,
			[
				("doc_only", "ToDo", "<no-method>"),
				("doc_method", "ToDo", "on_test_doc_event"),
			],
		)


class TestAPIHooks(FrappeAPITestCase):
	def test_auth_hook(self):
		with self.patch_hooks({"auth_hooks": ["frappe.tests.test_hooks.custom_auth"]}):
			site_url = frappe.utils.get_site_url(frappe.local.site)
			response = self.get(
				site_url + "/api/method/frappe.auth.get_logged_user",
				headers={"Authorization": "Bearer set_test_example_user"},
			)
			# Test!
			self.assertTrue(response.json.get("message") == "test@example.com")


def custom_has_permission(doc, ptype, user):
	if doc.flags.dont_touch_me:
		return False
	return True


def custom_auth():
	_auth_type, token = frappe.get_request_header("Authorization", "Bearer ").split(" ")
	if token == "set_test_example_user":
		frappe.set_user("test@example.com")


class CustomToDo(ToDo):
	pass


def _reset_doc_events_cache():
	frappe.local.doc_events_hooks = None


def handler_doc_only(doc):
	frappe.flags.doc_event_calls.append(("doc_only", doc.doctype, "<no-method>"))


def handler_doc_method(doc, method):
	frappe.flags.doc_event_calls.append(("doc_method", doc.doctype, method))


def handler_doc_method_default(doc, method=None):
	frappe.flags.doc_event_calls.append(("doc_method_default", doc.doctype, method))


def handler_doc_varargs(doc, *args):
	frappe.flags.doc_event_calls.append(("doc_varargs", doc.doctype, args[0] if args else "<no-method>"))
