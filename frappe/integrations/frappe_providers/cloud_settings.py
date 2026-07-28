"""Cloud Settings: in-app billing, marketplace and domain controls for sites
created on Frappe Cloud / Atlas. The site talks to its bench's pilot admin over
HTTP using a site-scoped token both written into site_config on site creation."""

from urllib.parse import quote

import requests

import frappe
from frappe import _
from frappe.utils import cint

CLOUD_SETTINGS_ROLE = "System Manager"


class CloudMigrationConflictError(frappe.ValidationError):
	"""Another migration is unresolved, so this one cannot start. Distinct so the UI
	can offer the migrations page instead of a pointless retry."""


class PilotClient:
	"""Thin HTTP client for this site's bench pilot admin."""

	def __init__(self):
		self.endpoint = (frappe.conf.get("pilot_endpoint") or "").rstrip("/")
		self.token = frappe.conf.get("pilot_auth_token")
		# The site-scoped token and the bench's routes are both keyed by the real
		# site name, so this must be frappe.local.site (not a config override).
		self.site = frappe.local.site

	def get(self, path: str) -> dict | list:
		return self._request("GET", path)

	def post(self, path: str, data: dict | None = None) -> dict:
		return self._request("POST", path, data)

	def patch(self, path: str, data: dict | None = None) -> dict:
		return self._request("PATCH", path, data)

	def delete(self, path: str, data: dict | None = None) -> dict:
		return self._request("DELETE", path, data)

	def site_path(self, path: str) -> str:
		return f"sites/{quote(self.site, safe='')}/{path.lstrip('/')}"

	def domain_path(self, domain: str, suffix: str = "") -> str:
		"""Pilot addresses a single domain as a path segment, not a body field."""
		path = f"domains/{quote(domain, safe='')}"
		return self.site_path(f"{path}/{suffix.lstrip('/')}" if suffix else path)

	def _request(self, method: str, path: str, data: dict | None = None):
		try:
			response = requests.request(
				method,
				# Pilot's admin API is versioned under /api/v1.
				f"{self.endpoint}/api/v1/{path.lstrip('/')}",
				json=data,
				headers={"Authorization": f"Bearer {self.token}"},
				timeout=cint(frappe.conf.get("cloud_settings_timeout")) or 30,
			)
		except requests.RequestException as exc:
			frappe.throw(_("Could not reach your server: {0}").format(str(exc)), frappe.ValidationError)

		payload = self._parse(response)
		# Some endpoints (e.g. the app registry) return a bare JSON list.
		if response.ok and (isinstance(payload, list) or not payload.get("error")):
			return payload
		frappe.throw(
			self._error_message(payload) or response.text or _("Request to your server failed."),
			# The exception class reaches the browser as `exc_type`, which is how the
			# UI knows a conflict needs the "open migrations" action rather than a retry.
			CloudMigrationConflictError
			if self._error_code(payload) == "migration_conflict"
			else frappe.ValidationError,
		)

	@staticmethod
	def _error_code(payload) -> str:
		error = payload.get("error") if isinstance(payload, dict) else None
		return str(error.get("code") or "") if isinstance(error, dict) else ""

	@staticmethod
	def _parse(response):
		try:
			return response.json()
		except ValueError:
			return {}

	@staticmethod
	def _error_message(payload) -> str:
		"""Pilot reports an error as either a string or a nested object; always
		return a plain string. frappe.throw() feeds this to strip_html_tags(), which
		raises on a dict."""
		if not isinstance(payload, dict):
			return ""
		error = payload.get("error") or payload.get("message")
		if isinstance(error, dict):
			error = error.get("message") or error.get("detail") or error.get("error")
		return str(error) if error else ""


# --- access control -------------------------------------------------------


def is_cloud_settings_enabled() -> bool:
	"""A site is cloud-managed when its bench wrote pilot credentials into the
	site config. Self-hosted sites never have these, so the modal stays hidden."""
	if not (frappe.conf.get("pilot_endpoint") and frappe.conf.get("pilot_auth_token")):
		return False
	if frappe.session.user == "Guest":
		return False
	return CLOUD_SETTINGS_ROLE in frappe.get_roles()


def get_boot_context() -> dict:
	"""Safe Cloud Settings metadata for boot (no secrets)."""
	if not is_cloud_settings_enabled():
		return {"enabled": False}
	return _safe_context()


def _assert_access() -> None:
	if not is_cloud_settings_enabled():
		frappe.throw(
			_("You do not have access to Cloud Settings for this site."),
			frappe.PermissionError,
		)


def _safe_context() -> dict:
	return {
		"enabled": True,
		"provider": frappe.conf.get("cloud_provider") or "frappe_cloud",
		"site_name": frappe.local.site,
		"server_url": frappe.conf.get("cloud_server_url") or frappe.conf.get("pilot_endpoint"),
		"account_url": frappe.conf.get("cloud_account_url"),
		# URLs the desk browser loads the pilot-hosted Vue bundle from on demand.
		# Empty when unconfigured, in which case desk keeps the icon hidden.
		"bundle": _embed_bundle(),
	}


def _embed_bundle() -> dict:
	"""Browser-reachable URL for pilot's Cloud Settings embed bundle.

	Pilot builds and serves this bundle from its admin backend; the framework only
	points at it. By default we load it from `pilot_endpoint` — the admin's public
	URL the site already talks to, which also serves `/embed/cloud-settings/`. Set
	`cloud_settings_embed_url` only to override that (e.g. a CDN). `embed_version`
	busts the browser cache when pilot ships an update.

	One script and no stylesheet: the dialog renders inside a shadow root and
	adopts its own styles, so there is nothing for desk to link."""
	base = (frappe.conf.get("cloud_settings_embed_url") or frappe.conf.get("pilot_endpoint") or "").rstrip(
		"/"
	)
	if not base:
		return {}
	version = frappe.conf.get("cloud_settings_embed_version")
	query = f"?v={quote(str(version), safe='')}" if version else ""
	return {"js": f"{base}/embed/cloud-settings/cloud-settings.js{query}"}


# --- whitelisted endpoints ------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_context() -> dict:
	_assert_access()
	return _safe_context()


@frappe.whitelist(methods=["GET"])
def get_account_url() -> dict:
	"""Central's configured browser URL, looked up only when the user opens it."""
	_assert_access()
	client = PilotClient()
	response = client.get(client.site_path("account-url"))
	return response if isinstance(response, dict) else {}


@frappe.whitelist(methods=["GET"])
def get_domains() -> dict:
	_assert_access()
	client = PilotClient()
	response = client.get(client.site_path("domains"))
	primary = response.get("primary") or client.site
	custom = response.get("domains") or []
	return {
		"primary": primary,
		"domains": [_domain_row(client.site, primary, is_default=True)]
		+ [_domain_row(domain, primary) for domain in custom],
	}


@frappe.whitelist(methods=["POST"])
def get_domain_dns_records(domain: str) -> dict:
	_assert_access()
	client = PilotClient()
	response = client.get(client.domain_path(_clean_domain(domain), "dns-records"))
	records = (response or {}).get("records") or {}
	return {"records": [*records.get("cname", []), *records.get("a", [])]}


@frappe.whitelist(methods=["POST"])
def add_domain(domain: str) -> dict:
	_assert_access()
	client = PilotClient()
	return client.post(client.site_path("domains"), {"domain": _clean_domain(domain)})


@frappe.whitelist(methods=["POST"])
def remove_domain(domain: str) -> dict:
	_assert_access()
	client = PilotClient()
	return client.delete(client.domain_path(_clean_domain(domain)))


@frappe.whitelist(methods=["POST"])
def set_primary_domain(domain: str) -> dict:
	_assert_access()
	client = PilotClient()
	# Pilot models "make primary" as a PATCH on the domain resource, so the domain
	# is part of the path and therefore required.
	return client.patch(client.domain_path(_clean_domain(domain)), {"primary": True})


@frappe.whitelist(methods=["GET"])
def get_marketplace_apps() -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_marketplace

	return cloud_marketplace.list_apps(PilotClient())


@frappe.whitelist(methods=["POST"])
def install_app(app: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_marketplace

	return cloud_marketplace.install(PilotClient(), app)


@frappe.whitelist(methods=["POST"])
def uninstall_app(app: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_marketplace

	return cloud_marketplace.uninstall(PilotClient(), app)


@frappe.whitelist(methods=["POST"])
def update_apps(apps: str | None = None) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_marketplace

	return cloud_marketplace.update(PilotClient(), apps)


@frappe.whitelist(methods=["GET"])
def get_task(task_id: str) -> dict:
	"""Status of a background task the bench started (install/uninstall/update),
	so the UI can track it to completion. Returns {} if the task is unknown."""
	_assert_access()
	task_id = (task_id or "").strip()
	if not task_id:
		frappe.throw(_("Task id is required."), frappe.ValidationError)
	try:
		client = PilotClient()
		# Site-scoped task route: a site token can read its own install/uninstall
		# tasks but not bench-wide ones.
		response = client.get(client.site_path(f"tasks/{quote(task_id, safe='')}"))
	except frappe.ValidationError:
		# Unknown / expired / not-ours task — don't surface it as a toast; the UI
		# treats an unknowable task as "still running in the background".
		frappe.clear_last_message()
		return {}
	# The bench nests the task metadata under "task" (alongside its output log).
	if isinstance(response, dict) and isinstance(response.get("task"), dict):
		return response["task"]
	return response if isinstance(response, dict) else {}


@frappe.whitelist(methods=["GET"])
def get_billing() -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.summary(PilotClient())


@frappe.whitelist(methods=["GET"])
def get_plan_options() -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.get_plan_options(PilotClient())


@frappe.whitelist(methods=["POST"])
def change_plan(plan: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.change_plan(PilotClient(), plan)


@frappe.whitelist(methods=["GET"])
def get_billing_profile() -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.get_profile(PilotClient())


@frappe.whitelist(methods=["POST"])
def save_billing_profile(**fields) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.save_profile(PilotClient(), fields)


@frappe.whitelist(methods=["GET"])
def get_payment_gateways() -> list:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.get_gateways(PilotClient())


@frappe.whitelist(methods=["POST"])
def add_payment_method(
	method_type: str = "Card", contact: str | None = None, gateway: str | None = None
) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.add_payment_method(PilotClient(), method_type, contact, gateway)


@frappe.whitelist(methods=["POST"])
def confirm_payment_method(**payload) -> dict:
	"""Finalize a payment method the gateway SDK tokenised (e.g. the Razorpay
	Checkout callback: payment_method + razorpay_payment_id/order_id/signature)."""
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.confirm_payment_method(PilotClient(), payload)


@frappe.whitelist(methods=["POST"])
def create_payment_method_checkout(redirect_url: str, gateway: str | None = None) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.create_payment_method_checkout(PilotClient(), redirect_url, gateway)


@frappe.whitelist(methods=["POST"])
def confirm_payment_method_checkout(reference: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.confirm_payment_method_checkout(PilotClient(), reference)


@frappe.whitelist(methods=["POST"])
def remove_payment_method(payment_method: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.remove_payment_method(PilotClient(), payment_method)


@frappe.whitelist(methods=["POST"])
def reconcile_payment_setup() -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.reconcile_payment_setup(PilotClient())


@frappe.whitelist(methods=["POST"])
def create_topup_checkout(amount: float, redirect_url: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.create_topup_checkout(PilotClient(), amount, redirect_url)


@frappe.whitelist(methods=["POST"])
def get_checkout_status(reference: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.checkout_status(PilotClient(), reference)


# --- helpers --------------------------------------------------------------


def _clean_domain(domain: str) -> str:
	domain = (domain or "").strip().lower()
	if not domain:
		frappe.throw(_("Domain is required."), frappe.ValidationError)
	return domain


def _domain_row(domain: str, primary: str, is_default: bool = False) -> dict:
	return {
		"domain": domain,
		"is_default": is_default,
		"is_primary": domain == primary,
	}
