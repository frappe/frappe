"""Cloud Settings: in-app billing, marketplace and domain controls for sites
created on Frappe Cloud / Atlas. The site talks to its bench's pilot admin over
HTTP using a site-scoped token both written into site_config on site creation."""

from urllib.parse import quote

import requests

import frappe
from frappe import _
from frappe.utils import cint

CLOUD_SETTINGS_ROLE = "System Manager"


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

	def delete(self, path: str, data: dict | None = None) -> dict:
		return self._request("DELETE", path, data)

	def site_path(self, path: str) -> str:
		return f"sites/{quote(self.site, safe='')}/{path.lstrip('/')}"

	def _request(self, method: str, path: str, data: dict | None = None):
		try:
			response = requests.request(
				method,
				f"{self.endpoint}/api/{path.lstrip('/')}",
				json=data,
				headers={"Authorization": f"Bearer {self.token}"},
				timeout=cint(frappe.conf.get("cloud_settings_timeout")) or 30,
			)
		except requests.RequestException as exc:
			frappe.throw(_("Could not reach your server: {0}").format(exc), frappe.ValidationError)

		payload = self._parse(response)
		# Some endpoints (e.g. the app registry) return a bare JSON list.
		if response.ok and (isinstance(payload, list) or not payload.get("error")):
			return payload
		message = payload.get("error") or payload.get("message") or response.text
		frappe.throw(message or _("Request to your server failed."), frappe.ValidationError)

	@staticmethod
	def _parse(response):
		try:
			return response.json()
		except ValueError:
			return {}


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
	}


# --- whitelisted endpoints ------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_context() -> dict:
	_assert_access()
	return _safe_context()


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
	response = client.post(client.site_path("domains/dns-records"), {"domain": _clean_domain(domain)})
	records = response.get("records") or {}
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
	return client.delete(client.site_path("domains"), {"domain": _clean_domain(domain)})


@frappe.whitelist(methods=["POST"])
def set_primary_domain(domain: str | None = None) -> dict:
	_assert_access()
	client = PilotClient()
	return client.post(client.site_path("domains/primary"), {"domain": _clean_optional_domain(domain)})


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
		response = PilotClient().get(f"tasks/{quote(task_id, safe='')}")
	except frappe.ValidationError:
		# Unknown / expired task — don't surface the reachability error as a toast.
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
def add_payment_method(method_type: str = "Card", contact: str | None = None,
					   gateway: str | None = None) -> dict:
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
def create_payment_method_checkout(gateway: str | None = None) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	# The gateway returns the browser here after setup — always this site, never a
	# caller-supplied URL (which would be an open redirect).
	return cloud_billing.create_payment_method_checkout(PilotClient(), _return_url(), gateway)


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
def create_topup_checkout(amount: float) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	# Return URL is this site's own — never caller-supplied (open-redirect defence).
	return cloud_billing.create_topup_checkout(PilotClient(), amount, _return_url())


@frappe.whitelist(methods=["POST"])
def get_checkout_status(reference: str) -> dict:
	_assert_access()
	from frappe.integrations.frappe_providers import cloud_billing

	return cloud_billing.checkout_status(PilotClient(), reference)


# --- helpers --------------------------------------------------------------


def _return_url() -> str:
	"""This site's own desk URL — the fixed post-checkout return target. Built here so
	a caller can never point the gateway's redirect at an external page."""
	return frappe.utils.get_url("/app")


def _clean_domain(domain: str) -> str:
	domain = (domain or "").strip().lower()
	if not domain:
		frappe.throw(_("Domain is required."), frappe.ValidationError)
	return domain


def _clean_optional_domain(domain: str | None) -> str:
	return (domain or "").strip().lower()


def _domain_row(domain: str, primary: str, is_default: bool = False) -> dict:
	return {
		"domain": domain,
		"is_default": is_default,
		"is_primary": domain == primary,
	}
