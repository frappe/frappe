# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Model credentials for the flow server."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

# Grove, Frappe Cloud's AI gateway, keyed by site config: the provider of its models
SITE_PROVIDER = "grove"
ENABLED_CACHE_KEY = "flow_enabled"


def is_enabled() -> bool:
	"""Whether Flow can chat on this site: an enabled chat model with its own key or address, or
	whose provider is enabled, or a Grove key in site config that Flow's first open turns into
	them. The same for every user; callers check the user's access to Flow themselves."""
	state = frappe.cache.get_value(ENABLED_CACHE_KEY, generator=_enabled_state)
	return state["ready"] or (not state["has_grove"] and bool(_first_key(frappe.conf)))


def _enabled_state() -> dict[str, bool]:
	providers = set(frappe.get_all("Flow Provider", filters={"enabled": 1}, pluck="name"))
	models = frappe.get_all(
		"Flow Model",
		filters={"enabled": 1, "embedding": 0},
		fields=["provider", "model_id", "api_key", "base_url"],
	)
	return {
		"ready": any(
			model.api_key or model.base_url or _model_provider(model) in providers for model in models
		),
		"has_grove": bool(frappe.db.exists("Flow Provider", SITE_PROVIDER)),
	}


def _model_provider(model) -> str:
	return model.provider or model.model_id.partition("/")[0]


def clear_enabled_cache() -> None:
	"""Clears now and again once the transaction ends, so a read in between can't keep the old answer."""
	_delete_enabled_cache()
	frappe.db.after_commit.add(_delete_enabled_cache)
	frappe.db.after_rollback.add(_delete_enabled_cache)


def _delete_enabled_cache() -> None:
	frappe.cache.delete_value(ENABLED_CACHE_KEY)


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
	provider = resolve_provider_credentials(doc.model_id, doc.provider)
	config = {
		"model": doc.model_id,
		"api_key": doc.get_password("api_key", raise_exception=False) or provider.get("api_key"),
		"api_base": doc.base_url or provider.get("base_url"),
	}
	if model_params := doc.model_params():
		config["model_params"] = model_params
	return config


def resolve_provider_credentials(model_id: str, provider: str | None = None) -> dict[str, Any]:
	"""Look up central Flow Provider credentials for a model's provider. A Grove model's come
	from site config."""
	if provider == SITE_PROVIDER:
		if not frappe.db.get_value("Flow Provider", SITE_PROVIDER, "enabled"):
			frappe.throw(
				_("Grove is turned off. Turn it on, or pick another model, in Settings → Models."),
				title=_("Grove Turned Off"),
			)
		return site_credentials()
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


def site_key() -> dict[str, str] | None:
	"""The first `ai_keys` entry Frappe Cloud writes into site config: {gateway_url, api_key}.
	Site config is cached for up to a minute, so a key not in it yet is read from the file."""
	return _first_key(frappe.conf) or _first_key(frappe.get_site_config())


def _first_key(conf: dict) -> dict[str, str] | None:
	entry = (conf.get("ai_keys") or [None])[0]
	if isinstance(entry, dict) and entry.get("gateway_url") and entry.get("api_key"):
		return entry
	return None


def site_credentials() -> dict[str, Any]:
	"""The site key and its gateway; the flow server picks the gateway's API for each model."""
	key = site_key()
	if not key:
		frappe.throw(
			_("This site no longer has a Grove key. Connect another provider in Settings → Models."),
			title=_("No Grove Key"),
		)
	return {"api_key": key["api_key"], "base_url": key["gateway_url"]}


def litellm_route(model_id: str, api_base: str | None) -> tuple[str, str | None]:
	"""The model and base for calling LiteLLM here, outside the flow server: a Grove model's are
	behind its gateway's API, picked as the flow server picks it."""
	if not model_id.startswith(f"{SITE_PROVIDER}/"):
		return model_id, api_base
	from flow_harness.model.providers.grove import grove_route

	return grove_route(model_id, api_base)
