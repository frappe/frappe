# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Model credentials for the flow server."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def model_config(model: str, *, check_permission: bool = True) -> dict[str, Any]:
	"""The daemon's model, api_key, api_base and model_params for a Flow Model the user may use."""
	if check_permission and not frappe.has_permission("Flow Model", "read", model):
		frappe.throw(
			_("You don't have permission to use {0}. Use a different model instead.").format(model),
			frappe.PermissionError,
			title=_("Model Not Permitted"),
		)
	doc = frappe.get_doc("Flow Model", model)
	if not doc.enabled:
		frappe.throw(_("Flow Model {0} is disabled.").format(model), title=_("Disabled Model"))
	provider = resolve_provider_credentials(doc.model_id)
	config = {
		"model": doc.model_id,
		"api_key": doc.get_password("api_key", raise_exception=False) or provider.get("api_key"),
		"api_base": doc.base_url or provider.get("base_url"),
	}
	if model_params := doc.model_params():
		config["model_params"] = model_params
	return config


def resolve_provider_credentials(model_id: str) -> dict[str, Any]:
	"""Look up central Flow Provider credentials for a model's provider."""
	try:
		import litellm

		provider = litellm.get_llm_provider(model_id)[1]
	except Exception:
		return {}

	if not provider or not frappe.db.exists("Flow Provider", provider):
		return {}

	doc = frappe.get_doc("Flow Provider", provider)
	if not doc.enabled:
		return {}

	return {
		"api_key": doc.get_password("api_key", raise_exception=False) or None,
		"base_url": doc.base_url or None,
	}
