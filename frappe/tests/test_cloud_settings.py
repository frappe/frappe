from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.integrations.frappe_providers.cloud_settings import (
	add_domain,
	get_boot_context,
	get_domains,
	is_cloud_settings_enabled,
)

PILOT_CONF = {
	"pilot_endpoint": "https://pilot.example.com",
	"pilot_auth_token": "secret-token",
}


class TestCloudSettings(TestCase):
	def setUp(self):
		frappe.local.conf = frappe._dict()
		frappe.local.session = frappe._dict(user="Administrator")
		# The site name IS the scope of the pilot token and the bench routes.
		frappe.local.site = "ravibakes.frappe.cloud"

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

	def test_get_domains_calls_scoped_pilot_endpoint(self):
		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"frappe.integrations.frappe_providers.cloud_settings.requests.request",
				return_value=Response({"domains": ["shop.example.com"], "primary": "shop.example.com"}),
			) as request,
		):
			result = get_domains()

		request.assert_called_once()
		_, url = request.call_args.args[:2]
		self.assertEqual(url, "https://pilot.example.com/api/sites/ravibakes.frappe.cloud/domains")
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
				"frappe.integrations.frappe_providers.cloud_settings.requests.request",
				return_value=Response({"ok": True, "task_id": "task-1"}),
			) as request,
		):
			result = add_domain(" Shop.Example.Com ")

		self.assertEqual(result["task_id"], "task-1")
		self.assertEqual(request.call_args.args[0], "POST")
		self.assertEqual(request.call_args.kwargs["json"], {"domain": "shop.example.com"})


class TestCloudMarketplace(TestCase):
	CATALOG = [
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

	def setUp(self):
		frappe.local.site = "test.localhost"

	def _list(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient(
			{
				"apps/marketplace": self.CATALOG,
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
		self.assertEqual(client.posts[0], ("sites/test.localhost/get-and-install-app", {"app": "hrms"}))

	def test_uninstall_posts_to_site_scoped_route(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient({})
		cloud_marketplace.uninstall(client, "hrms")
		self.assertEqual(client.posts[0], ("sites/test.localhost/uninstall-app", {"app": "hrms"}))

	def test_update_all_runs_bench_update_task(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient({})
		cloud_marketplace.update(client, None)
		self.assertEqual(client.posts[0], ("tasks/run", {"command": "update"}))

	def test_update_selected_apps_filters_task(self):
		from frappe.integrations.frappe_providers import cloud_marketplace

		client = FakeClient({})
		cloud_marketplace.update(client, '["hrms", "erpnext"]')
		self.assertEqual(
			client.posts[0], ("tasks/run", {"command": "update", "apps": ["hrms", "erpnext"]})
		)


class TestCloudTask(TestCase):
	def setUp(self):
		frappe.local.session = frappe._dict(user="Administrator")
		frappe.local.site = "ravibakes.frappe.cloud"

	def test_get_task_proxies_to_bench(self):
		from frappe.integrations.frappe_providers.cloud_settings import get_task

		with (
			patch.dict(frappe.conf, PILOT_CONF),
			patch("frappe.get_roles", return_value=["System Manager"]),
			patch(
				"frappe.integrations.frappe_providers.cloud_settings.requests.request",
				# The bench nests task metadata under "task" alongside the log output.
				return_value=Response(
					{"output": ["…"], "task": {"task_id": "task-1", "status": "success", "exit_code": 0}}
				),
			) as request,
		):
			result = get_task("task-1")

		_, url = request.call_args.args[:2]
		self.assertEqual(url, "https://pilot.example.com/api/tasks/task-1")
		self.assertEqual(result["status"], "success")
		self.assertEqual(result["task_id"], "task-1")


class Response:
	ok = True
	text = ""

	def __init__(self, payload):
		self.payload = payload

	def json(self):
		return self.payload


class FakeClient:
	"""Stand-in for PilotClient: mirrors its list-wrapping and records posts."""

	def __init__(self, responses):
		self.responses = responses
		self.posts = []

	def site_path(self, path):
		return f"sites/test.localhost/{path.lstrip('/')}"

	def get(self, path):
		# Mirrors PilotClient: returns the raw decoded JSON (list or dict).
		return self.responses[path]

	def post(self, path, data=None):
		self.posts.append((path, data))
		return {"ok": True, "task_id": "task-1"}
