"""Billing: plan, usage, credit and payment methods for the site. The bench pilot
proxies these from Frappe Cloud Central (which resolves the team + asset from the
pilot credential); this layer just forwards to the bench's `sites/<site>/billing/*`
routes. Formatting and business logic live in Central."""

from __future__ import annotations


def summary(client) -> dict:
    """Full billing summary: plan + live usage, estimate, credit and payment state."""
    data = client.get(client.site_path("billing/summary"))
    data["available"] = True
    return data


def get_profile(client) -> dict:
    return client.get(client.site_path("billing/profile"))


def save_profile(client, fields: dict) -> dict:
    return client.post(client.site_path("billing/profile"), fields)


def get_gateways(client) -> list:
    """The gateways the team can pay through (Pay-through choices)."""
    return client.get(client.site_path("billing/gateways"))


def add_payment_method(client, method_type: str, contact: str | None = None,
                       gateway: str | None = None) -> dict:
    return client.post(
        client.site_path("billing/payment-method"),
        {"method_type": method_type, "contact": contact, "gateway": gateway},
    )


def confirm_payment_method(client, payload: dict) -> dict:
    return client.post(client.site_path("billing/payment-method/confirm"), payload)


def remove_payment_method(client, payment_method: str) -> dict:
    return client.post(client.site_path("billing/payment-method/remove"), {"payment_method": payment_method})


def create_payment_method_checkout(client, redirect_url: str, gateway: str | None = None) -> dict:
    """Start adding a card via hosted setup checkout; returns the checkout URL to open."""
    return client.post(
        client.site_path("billing/payment-method/checkout"),
        {"redirect_url": redirect_url, "gateway": gateway},
    )


def confirm_payment_method_checkout(client, reference: str) -> dict:
    return client.post(client.site_path("billing/payment-method/checkout/confirm"), {"reference": reference})


def reconcile_payment_setup(client) -> dict:
    """Activate any card whose hosted setup finished while the user was away."""
    return client.post(client.site_path("billing/reconcile-setup"), {})


def create_topup_checkout(client, amount, redirect_url: str) -> dict:
    """Start a wallet top-up via hosted checkout; returns the checkout URL to open."""
    return client.post(
        client.site_path("billing/topup-checkout"),
        {"amount": amount, "redirect_url": redirect_url},
    )


def checkout_status(client, reference: str) -> dict:
    return client.post(client.site_path("billing/checkout-status"), {"reference": reference})
