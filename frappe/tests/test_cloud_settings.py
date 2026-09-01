from typing import ClassVar
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.integrations.frappe_providers.cloud_settings import (
	CloudMigrationConflictError,
	add_domain,
	get_boot_context,
	get_domain_dns_records,
	get_domains,
	is_cloud_settings_enabled,
	remove_domain,
	set_primary_domain,
)

PILOT_CONF = {
	"pilot_endpoint": "https://pilot.example.com",
	"pilot_auth_token": "secret-token",
}


class _CloudTestCase(TestCase):
	"""Save/restore frappe.local so these tests do not poison later CI shard files."""

	def setUp(self):
		self._local = {
			"conf": frappe.local.conf,
			"session": getattr(frappe.local, "session", None),
			"site": getattr(frappe.local, "site", None),
			"flags": getattr(frappe.local, "flags", None),
			"message_log": getattr(frappe.local, "message_log", None),
		}
		self.configure_local()

	def tearDown(self):
		for key, value in self._local.items():
			setattr(frappe.local, key, value)

	def configure_local(self):
		pass


class TestCloudSettings(_CloudTestCase):
	def configure_local(self):
		frappe.local.conf = frappe._dict()
		frappe.local.session = frappe._dict(user="Administrator")
		# The site name IS the scope of the pilot token and the bench routes.
		frappe.local.site = "ravibakes.frappe.cloud"
		# frappe.throw() reads these; keep them bound for bare unittest runs.
		frappe.local.flags = frappe._dict(mute_messages=True, print_messages=False)
		frappe.local.message_log = []

	def test_disabled_for_self_hosted_site(self):
		"""A self-hosted site has no pilot credentials, so the modal stays hidden."""
		with patch("frappe.get_roles", return_value=["System Manager"]):
			self.assertFalse(is_cloud_settings_enabled())
			self.assertEqual(get_boot_context(), {"enabled": False})

	def test_enabled_for_cloud_site_system_manager(self):
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
		):
			context = get_boot_context()

		self.assertTrue(context["enabled"])
		self.assertEqual(context["provider"], "frappe_cloud")
		self.assertEqual(context["site_name"], "ravibakes.frappe.cloud")
		self.assertEqual(context["server_url"], "https://pilot.example.com")
		self.assertNotIn("pilot_auth_token", context)

	def test_bundle_defaults_to_pilot_endpoint(self):
		"""With no explicit embed URL, the bundle loads from the admin backend the
		site already talks to (pilot_endpoint)."""
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
		):
			bundle = get_boot_context()["bundle"]

		self.assertEqual(bundle["js"], "https://pilot.example.com/embed/cloud-settings/cloud-settings.js")

	def test_bundle_embed_url_overrides_with_version(self):
		conf = {
			**PILOT_CONF,
			"cloud_settings_embed_url": "https://cdn.example.com/",
			"cloud_settings_embed_version": "16.0.1",
		}
		with (
			patch.dict(frappe.conf, conf),
			patch("frappe.get_roles", return_value=["System Manager"]),
		):
			bundle = get_boot_context()["bundle"]

		self.assertEqual(
			bundle["js"],
			"https://cdn.example.com/embed/cloud-settings/cloud-settings.js?v=16.0.1",
		)
		# The embed renders in a shadow root and adopts its own styles, so the
		# bundle is one script with no stylesheet for desk to link.
		self.assertNotIn("css", bundle)

	def test_disabled_without_system_manager_role(self):
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["Desk User"]),
		):
			self.assertFalse(is_cloud_settings_enabled())

	def test_disabled_for_guest(self):
		frappe.local.session = frappe._dict(user="Guest")
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
		):
			self.assertFalse(is_cloud_settings_enabled())

	def test_error_message_always_a_string(self):
		"""Pilot may nest the error as an object; _error_message must return a str so
		frappe.throw()/strip_html_tags() never crashes with 'got dict'."""
		from frappe.integrations.frappe_providers.cloud_settings import PilotClient

		self.assertEqual(PilotClient._error_message({"error": "flat"}), "flat")
		self.assertEqual(PilotClient._error_message({"error": {"message": "boom"}}), "boom")
		self.assertEqual(PilotClient._error_message({"message": {"detail": "d"}}), "d")
		self.assertEqual(PilotClient._error_message(["a", "b"]), "")
		self.assertEqual(PilotClient._error_message({}), "")

	def test_billing_uses_allowlisted_central_proxy(self):
		from frappe.integrations.frappe_providers import cloud_billing

		client = FakeClient(
			{
				"sites/test.localhost/central/central.billing.api.billing_api.get_billing_summary": {
					"currency": "INR",
					"plan": {"name": "Basic"},
				}
			}
		)

		result = cloud_billing.summary(client)

		self.assertEqual(result["plan"]["name"], "Basic")

	def test_billing_actions_use_matching_central_methods(self):
		from frappe.integrations.frappe_providers import cloud_billing

		client = FakeClient({})
		cloud_billing.save_profile(client, {"legal_name": "Acme"})
		cloud_billing.remove_payment_method(client, "pm-1")
		cloud_billing.create_topup_checkout(client, 500, "https://site.example/desk")

		self.assertEqual(
			client.posts,
			[
				(
					"sites/test.localhost/central/central.billing.api.billing_api.save_billing_profile",
					{"legal_name": "Acme"},
				),
				(
					"sites/test.localhost/central/central.billing.api.billing_api.remove_payment_method",
					{"payment_method": "pm-1"},
				),
				(
					"sites/test.localhost/central/central.billing.api.billing_api.create_topup_checkout",
					{"amount": 500, "redirect_url": "https://site.example/desk"},
				),
			],
		)

	def test_account_url_comes_from_pilots_central_configuration(self):
		from frappe.integrations.frappe_providers.cloud_settings import get_account_url

		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"requests.request",
				return_value=Response({"url": "http://central.localhost:8001"}),
			) as request,
		):
			result = get_account_url()

		self.assertEqual(result, {"url": "http://central.localhost:8001"})
		self.assertEqual(
			request.call_args.args[1],
			"https://pilot.example.com/api/v1/sites/ravibakes.frappe.cloud/account-url",
		)

	def test_plan_actions_use_centrals_eligible_catalog(self):
		from frappe.integrations.frappe_providers import cloud_billing

		client = FakeClient(
			{"sites/test.localhost/central/central.billing.api.billing_api.get_plan_options": {"plans": []}}
		)

		self.assertEqual(cloud_billing.get_plan_options(client), {"plans": []})
		cloud_billing.change_plan(client, "business")
		self.assertEqual(
			client.posts,
			[
				(
					"sites/test.localhost/central/central.billing.api.billing_api.change_plan",
					{"plan": "business"},
				)
			],
		)

	def test_get_domains_calls_scoped_pilot_endpoint(self):
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"requests.request",
				return_value=Response({"domains": ["shop.example.com"], "primary": "shop.example.com"}),
			) as request,
		):
			result = get_domains()

		request.assert_called_once()
		_, url = request.call_args.args[:2]
		self.assertEqual(url, "https://pilot.example.com/api/v1/sites/ravibakes.frappe.cloud/domains")
		self.assertEqual(
			request.call_args.kwargs["headers"],
			{"Authorization": "Bearer secret-token"},
		)
		self.assertEqual(result["primary"], "shop.example.com")
		self.assertEqual(result["domains"][0]["domain"], "ravibakes.frappe.cloud")
		self.assertTrue(result["domains"][0]["is_default"])
		self.assertTrue(result["domains"][1]["is_primary"])

	def test_add_domain_posts_to_pilot(self):
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"requests.request",
				return_value=Response({"ok": True, "task_id": "task-1"}),
			) as request,
		):
			result = add_domain(" Shop.Example.Com ")

		self.assertEqual(result["task_id"], "task-1")
		self.assertEqual(request.call_args.args[0], "POST")
		self.assertEqual(request.call_args.kwargs["json"], {"domain": "shop.example.com"})

	def test_migration_conflict_gets_its_own_exception_type(self):
		"""The class name reaches the browser as `exc_type`, which is how the UI knows
		to offer the migrations page instead of a pointless retry."""
		payload = {"error": {"code": "migration_conflict", "message": "Still needs_attention."}}
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"requests.request",
				return_value=Response(payload, ok=False),
			),
			self.assertRaises(CloudMigrationConflictError),
		):
			add_domain("shop.example.com")

	def test_other_pilot_errors_stay_generic(self):
		payload = {"error": {"code": "invalid_domain", "message": "Bad."}}
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"requests.request",
				return_value=Response(payload, ok=False),
			),
			self.assertRaises(frappe.ValidationError) as caught,
		):
			add_domain("shop.example.com")
		self.assertNotIsInstance(caught.exception, CloudMigrationConflictError)

	# Pilot addresses a single domain as a path segment. These three used to send
	# the domain in the body against a collection URL, which pilot answered with
	# "Method not allowed" — the DNS preview, remove and make-primary flows were
	# all dead. Assert the verb and URL shape so they cannot silently drift again.
	def _pilot_call(self, action, payload):
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"requests.request",
				return_value=Response(payload),
			) as request,
		):
			result = action()
		return result, request.call_args

	def test_dns_records_are_read_from_the_domain_resource(self):
		result, call = self._pilot_call(
			lambda: get_domain_dns_records(" Shop.Example.Com "),
			{"records": {"cname": [{"type": "CNAME"}], "a": [{"type": "A"}]}},
		)

		method, url = call.args[:2]
		self.assertEqual(method, "GET")
		self.assertEqual(
			url,
			"https://pilot.example.com/api/v1/sites/ravibakes.frappe.cloud"
			"/domains/shop.example.com/dns-records",
		)
		self.assertEqual([record["type"] for record in result["records"]], ["CNAME", "A"])

	def test_remove_domain_deletes_the_domain_resource(self):
		_, call = self._pilot_call(lambda: remove_domain("shop.example.com"), {"ok": True})

		method, url = call.args[:2]
		self.assertEqual(method, "DELETE")
		self.assertEqual(
			url,
			"https://pilot.example.com/api/v1/sites/ravibakes.frappe.cloud/domains/shop.example.com",
		)

	def test_set_primary_domain_patches_the_domain_resource(self):
		_, call = self._pilot_call(lambda: set_primary_domain("shop.example.com"), {"ok": True})

		method, url = call.args[:2]
		self.assertEqual(method, "PATCH")
		self.assertEqual(
			url,
			"https://pilot.example.com/api/v1/sites/ravibakes.frappe.cloud/domains/shop.example.com",
		)
		self.assertEqual(call.kwargs["json"], {"primary": True})


class TestCloudMarketplace(_CloudTestCase):
	CATALOG: ClassVar[list[dict]] = [
		{
			"name": "erpnext",
			"title": "ERPNext",
			"category": "Applications",
			"version": "15.2.0",
			"is_installable": True,
			"stars": 50,
		},
		{
			"name": "crm",
			"title": "Frappe CRM",
			"category": "Applications",
			"version": "1.5.0",
			"is_installable": True,
			"stars": 80,
		},
		{
			"name": "builder",
			"title": "Frappe Builder",
			"category": "Developer Tools",
			"version": "1.0.0",
			"is_installable": False,
			"required_version": "16",
		},
	]

	def configure_local(self):
		frappe.local.site = "test.localhost"

	def _list(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient(
			{
				"sites/test.localhost/marketplace": self.CATALOG,
				"sites/test.localhost/apps": {"apps": [{"name": "erpnext", "version": "15.0.0"}]},
			}
		)
		return cloud_marketplace.list_apps(client)

	def test_list_apps_merges_catalog_with_installed(self):
		result = self._list()
		apps = {app["name"]: app for app in result["apps"]}

		self.assertTrue(apps["erpnext"]["installed"])
		self.assertTrue(apps["erpnext"]["has_update"])
		self.assertEqual(apps["erpnext"]["installed_version"], "15.0.0")
		self.assertEqual(apps["erpnext"]["latest_version"], "15.2.0")
		self.assertFalse(apps["crm"]["installed"])
		self.assertFalse(apps["builder"]["installable"])
		self.assertEqual(apps["builder"]["required_version"], "16")
		self.assertEqual(result["update_count"], 1)
		self.assertEqual(set(result["categories"]), {"Applications", "Developer Tools"})

	def test_installed_apps_sort_first(self):
		self.assertEqual(self._list()["apps"][0]["name"], "erpnext")

	def test_install_posts_to_site_scoped_route(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient({})
		cloud_marketplace.install(client, " hrms ")
		self.assertEqual(client.posts[0], ("sites/test.localhost/apps", {"app": "hrms"}))

	def test_uninstall_deletes_site_scoped_app(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient({})
		cloud_marketplace.uninstall(client, "hrms")
		self.assertEqual(client.deletes[0], ("sites/test.localhost/apps/hrms", None))

	def test_update_all_posts_to_site_scoped_action(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient({})
		cloud_marketplace.update(client, None)
		self.assertEqual(client.posts[0], ("sites/test.localhost/actions/update-apps", {}))

	def test_update_selected_apps_posts_site_scoped_filter(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient({})
		cloud_marketplace.update(client, '["hrms", "erpnext"]')
		self.assertEqual(
			client.posts[0],
			("sites/test.localhost/actions/update-apps", {"apps": ["hrms", "erpnext"]}),
		)


class TestCloudTask(_CloudTestCase):
	def configure_local(self):
		frappe.local.session = frappe._dict(user="Administrator")
		frappe.local.site = "ravibakes.frappe.cloud"

	def test_get_task_proxies_to_bench(self):
		from frappe.integrations.frappe_providers.cloud_settings import get_task

		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"requests.request",
				# The bench nests task metadata under "task" alongside the log output.
				return_value=Response(
					{"output": ["…"], "task": {"task_id": "task-1", "status": "success", "exit_code": 0}}
				),
			) as request,
		):
			result = get_task("task-1")

		_, url = request.call_args.args[:2]
		self.assertEqual(url, "https://pilot.example.com/api/v1/sites/ravibakes.frappe.cloud/tasks/task-1")
		self.assertEqual(result["status"], "success")
		self.assertEqual(result["task_id"], "task-1")


class Response:
	text = ""

	def __init__(self, payload, ok=True):
		self.payload = payload
		self.ok = ok

	def json(self):
		return self.payload


class FakeClient:
	"""Stand-in for PilotClient: mirrors its list-wrapping and records posts."""

	def __init__(self, responses):
		self.responses = responses
		self.posts = []
		self.deletes = []

	def site_path(self, path):
		return f"sites/test.localhost/{path.lstrip('/')}"

	def get(self, path):
		# Mirrors PilotClient: returns the raw decoded JSON (list or dict).
		return self.responses[path]

	def post(self, path, data=None):
		self.posts.append((path, data))
		return {"ok": True, "task_id": "task-1"}

	def delete(self, path, data=None):
		self.deletes.append((path, data))
		return {"ok": True, "task_id": "task-1"}
