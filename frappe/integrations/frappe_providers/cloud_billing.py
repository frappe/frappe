"""Billing: plan, usage, credit and payment methods for the site.

Pilot forwards these calls to an allowlisted Central billing API using the bench's
credential. Formatting and business logic live in Central.
"""

from __future__ import annotations

METHOD_PREFIX = "central.billing.api.billing_api"


def summary(client) -> dict:
	"""Full billing summary: plan + live usage, estimate, credit and payment state."""
	return client.get(_path(client, "get_billing_summary"))


def get_plan_options(client) -> dict:
	"""Plans Central currently permits this site's server to switch to."""
	return client.get(_path(client, "get_plan_options"))


def change_plan(client, plan: str) -> dict:
	return client.post(_path(client, "change_plan"), {"plan": plan})


def get_profile(client) -> dict:
	return client.get(_path(client, "get_billing_profile"))


def save_profile(client, fields: dict) -> dict:
	return client.post(_path(client, "save_billing_profile"), fields)


def get_gateways(client) -> list:
	"""The gateways the team can pay through (Pay-through choices)."""
	return client.get(_path(client, "get_payment_gateways"))


def add_payment_method(
	client, method_type: str, contact: str | None = None, gateway: str | None = None
) -> dict:
	return client.post(
		_path(client, "add_payment_method"),
		{"method_type": method_type, "contact": contact, "gateway": gateway},
	)


def confirm_payment_method(client, payload: dict) -> dict:
	return client.post(_path(client, "confirm_payment_method"), payload)


def remove_payment_method(client, payment_method: str) -> dict:
	return client.post(_path(client, "remove_payment_method"), {"payment_method": payment_method})


def create_payment_method_checkout(client, redirect_url: str, gateway: str | None = None) -> dict:
	"""Start adding a card via hosted setup checkout; returns the checkout URL to open."""
	return client.post(
		_path(client, "create_payment_method_checkout"),
		{"redirect_url": redirect_url, "gateway": gateway},
	)


def confirm_payment_method_checkout(client, reference: str) -> dict:
	return client.post(_path(client, "confirm_payment_method_checkout"), {"reference": reference})


def reconcile_payment_setup(client) -> dict:
	"""Activate any card whose hosted setup finished while the user was away."""
	return client.post(_path(client, "reconcile_payment_setup"), {})


def create_topup_checkout(client, amount, redirect_url: str) -> dict:
	"""Start a wallet top-up via hosted checkout; returns the checkout URL to open."""
	return client.post(
		_path(client, "create_topup_checkout"),
		{"amount": amount, "redirect_url": redirect_url},
	)


def checkout_status(client, reference: str) -> dict:
	return client.post(_path(client, "get_checkout_status"), {"reference": reference})


def _path(client, method: str) -> str:
	return client.site_path(f"central/{METHOD_PREFIX}.{method}")
