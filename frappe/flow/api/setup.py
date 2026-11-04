# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Flow's first run, from the /flow page or the launcher's panel: connect an AI service in one
step. The key is checked with the service before anything is saved, so a bad key is caught at
setup and not in the first chat; then the provider and its recommended models are saved, and the
first model becomes the Assistant's."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

import frappe
from frappe import _
from frappe.utils import escape_html, get_fullname, get_url

# Beside the site, a model server needs no key
OLLAMA_URL = "http://localhost:11434"
OLLAMA_PROVIDER = "ollama_chat"

# The models a connection starts with, the recommended first. The first of these the service
# lists is saved, with the next two; a newer model is a line here, or a model added in settings
PREFERRED = {
	"anthropic": [
		"claude-sonnet-5-5",
		"claude-opus-5-5",
		"claude-haiku-5-5",
		"claude-sonnet-4-6",
		"claude-sonnet-4-5",
	],
	"openai": ["gpt-5.5", "gpt-5.4-mini", "gpt-5.4", "gpt-5", "gpt-5-mini"],
	"gemini": ["gemini-3.1-pro-preview", "gemini-3.8-flash", "gemini-2.5-pro", "gemini-2.5-flash"],
	"openrouter": ["anthropic/claude-sonnet-5-5", "openai/gpt-5.5", "google/gemini-3.1-pro-preview"],
	"xai": ["grok-4", "grok-3-mini"],
	"groq": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"],
	"deepseek": ["deepseek-chat", "deepseek-reasoner"],
	"mistral": ["mistral-large-latest", "mistral-medium-latest"],
	"cerebras": ["gpt-oss-120b", "llama-3.3-70b"],
}
MODELS_PER_CONNECTION = 3
# what a service says when the account, not the key, is the problem
NO_CREDIT = ("credit balance", "insufficient_quota", "billing", "payment required", "quota")
ASK_ADMIN_CACHE = "flow_setup_asked"
# each model's last check, so the Models tab says beside a model why it doesn't answer
MODEL_CHECKS = "flow_model_checks"


@frappe.whitelist()
def setup_options() -> dict[str, Any]:
	"""What the first run offers beyond the listed services: a model server running beside the site."""
	_check_can_connect()
	return {"ollama": _ollama_models()}


@frappe.whitelist(methods=["POST"])
def connect(provider: str, api_key: str | None = None) -> dict[str, Any]:
	"""Check `api_key` with `provider`, then save both and the recommended models. A key the service
	refuses saves nothing and says why: `wrong_key`, `no_credit`, `unreachable` or `failed`."""
	_check_can_connect()
	provider = (provider or "").strip().lower()
	api_key = (api_key or "").strip() or None

	if provider == "ollama":
		provider, base_url, available = OLLAMA_PROVIDER, OLLAMA_URL, _ollama_models()
		if not available:
			return _refused("unreachable", _("Ollama isn't answering on this server any more."))
	else:
		from flow_harness.model.discovery import MODEL_ENDPOINTS

		if provider not in MODEL_ENDPOINTS:
			frappe.throw(_("Flow can't connect {0} here. Add it in Settings.").format(escape_html(provider)))
		if not api_key:
			frappe.throw(_("Paste the key first."))
		base_url = None
		try:
			available = _listed_models(MODEL_ENDPOINTS[provider], provider, api_key)
		except requests.HTTPError as e:
			if e.response is not None and e.response.status_code in (401, 403):
				return _refused("wrong_key", _("{0} didn't accept this key.").format(_label(provider)))
			available = []  # the list is a nicety: the check below decides
		except requests.RequestException:
			return _refused("unreachable", _("Couldn't reach {0} from this server.").format(_label(provider)))

	models = _pick(provider, available)
	if not models:
		return _refused("failed", _("{0} lists no models Flow can use.").format(_label(provider)))
	if refused := _check(f"{provider}/{models[0]}", api_key, base_url):
		return refused

	_save_provider(provider, api_key, base_url)
	# what its models said to the old key no longer stands
	for name in frappe.get_all("Flow Model", {"provider": provider}, pluck="name"):
		frappe.cache.hdel(MODEL_CHECKS, name)
	# a service connected before keeps its models as they were (a new key for it, say): one
	# switched off stays off. With every one off, connecting it means the recommended ones again
	if kept := frappe.get_all(
		"Flow Model", {"provider": provider, "enabled": 1}, pluck="name", order_by="creation asc"
	):
		return {"ok": True, "models": kept}
	names = [_save_model(provider, model) for model in models]
	return {"ok": True, "models": names}


@frappe.whitelist()
def services() -> dict[str, Any]:
	"""The Models tab: each provider with its models, its recommended one marked, and the models
	that carry a key of their own."""
	frappe.has_permission("Flow Model", "read", throw=True)
	providers = frappe.get_list(
		"Flow Provider", fields=["name", "enabled", "base_url"], order_by="creation asc"
	)
	models = frappe.get_list(
		"Flow Model", fields=["name", "title", "model_id", "provider", "enabled"], order_by="creation asc"
	)
	for model in models:
		model.check = frappe.cache.hget(MODEL_CHECKS, model.name)
	result = []
	for provider in providers:
		own = [model for model in models if model.provider == provider.name]
		ids = {model.model_id: model.name for model in own}
		recommended = next(
			(
				ids[f"{provider.name}/{pick}"]
				for pick in PREFERRED.get(provider.name, [])
				if f"{provider.name}/{pick}" in ids
			),
			None,
		)
		result.append(
			{
				**provider,
				"label": _label(provider.name, provider.base_url),
				"models": own,
				"recommended": recommended,
			}
		)
	listed = {provider.name for provider in providers}
	return {"services": result, "other": [model for model in models if model.provider not in listed]}


@frappe.whitelist(methods=["POST"])
def add_model(provider: str, model_id: str) -> dict[str, Any]:
	"""One of `provider`'s models, named as people know it (one already saved is switched on),
	and whether it answers: one that doesn't is saved switched off."""
	frappe.has_permission("Flow Model", "create", throw=True)
	name = _save_model(provider, model_id.strip().removeprefix(f"{provider}/"))
	check = _check_model(name)
	model = frappe.db.get_value("Flow Model", name, ["name", "title", "model_id", "enabled"], as_dict=True)
	return {**model, "check": check}


@frappe.whitelist(methods=["POST"])
def check_model(name: str) -> dict[str, Any]:
	"""Whether the model answers, asked as a chat would; one that doesn't is switched off."""
	frappe.has_permission("Flow Model", "write", throw=True)
	return _check_model(name)


@frappe.whitelist(methods=["POST"])
def ask_admin() -> dict[str, Any]:
	"""Someone who can't connect a service asks those who can, once a day at most."""
	frappe.has_permission("Flow Session", "read", throw=True)
	key = f"{ASK_ADMIN_CACHE}:{frappe.session.user}"
	admins = _admins()
	if not frappe.cache.get_value(key):
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		emails = [email for email in frappe.get_all("User", {"name": ("in", admins)}, pluck="email") if email]
		if emails:
			enqueue_create_notification(
				emails,
				{
					"type": "Alert",
					"subject": _(
						"{0} would like to use Flow. Connect an AI service to set it up for everyone."
					).format(frappe.bold(escape_html(get_fullname(frappe.session.user)))),
					"from_user": frappe.session.user,
					"link": get_url("/flow"),
				},
			)
		frappe.cache.set_value(key, 1, expires_in_sec=24 * 60 * 60)
	return {"admins": [get_fullname(user) for user in admins[:3]]}


def _check_can_connect() -> None:
	for doctype in ("Flow Provider", "Flow Model"):
		frappe.has_permission(doctype, "create", throw=True)


def _refused(reason: str, message: str) -> dict[str, Any]:
	return {"ok": False, "reason": reason, "message": message}


def _label(provider: str, base_url: str | None = None) -> str:
	"""A service as people name it; a server of one's own by its address."""
	if provider in ("custom_openai", "litellm_proxy"):
		return urlparse(base_url).netloc if base_url else _("OpenAI-compatible endpoint")
	return {
		"openai": "OpenAI",
		"xai": "xAI",
		"deepseek": "DeepSeek",
		"openrouter": "OpenRouter",
		OLLAMA_PROVIDER: "Ollama",
	}.get(provider, provider.capitalize())


def _listed_models(url: str, provider: str, api_key: str) -> list[str]:
	"""The service's /models list for the key, as the model picker asks it."""
	params: dict[str, Any] = {}
	if provider == "anthropic":
		headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
		params = {"limit": 1000}
	elif provider == "gemini":
		headers = {"x-goog-api-key": api_key}
		params = {"pageSize": 1000}
	else:
		headers = {"Authorization": f"Bearer {api_key}"}
	response = requests.get(url, headers=headers, params=params, timeout=10)
	response.raise_for_status()
	data = response.json()
	ids = (row.get("id") or row.get("name") for row in data.get("data", data.get("models")) or [])
	return [str(model_id).removeprefix("models/") for model_id in ids if model_id]


def _ollama_models() -> list[str]:
	"""The models an Ollama beside the site has pulled; none when it isn't running."""
	try:
		response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=0.5)
		response.raise_for_status()
		return [row["name"] for row in response.json().get("models", []) if row.get("name")]
	except (requests.RequestException, ValueError, KeyError):
		return []


def _pick(provider: str, available: list[str]) -> list[str]:
	"""The recommended models the service lists; without its list, the recommendations as they are."""
	preferred = PREFERRED.get(provider, [])
	if not available:
		return preferred[:MODELS_PER_CONNECTION]
	listed = set(available)
	picked = [model for model in preferred if model in listed]
	# a service with none of ours (a local server) starts on what it has
	return (picked or available)[:MODELS_PER_CONNECTION]


def _check(model_id: str, api_key: str | None, base_url: str | None) -> dict[str, Any] | None:
	"""A one-message call to the model: None when it answers, else why it didn't."""
	import litellm

	provider = model_id.partition("/")[0]
	kwargs: dict[str, Any] = {
		"model": model_id,
		"api_key": api_key,
		"messages": [{"role": "user", "content": "ping"}],
		"max_tokens": 16,
		"timeout": 20,
	}
	if base_url:
		kwargs["api_base"] = base_url
	try:
		litellm.completion(**kwargs)
	except litellm.AuthenticationError:
		return _refused("wrong_key", _("{0} didn't accept this key.").format(_label(provider)))
	except (litellm.APIConnectionError, litellm.Timeout, litellm.ServiceUnavailableError):
		return _refused("unreachable", _("Couldn't reach {0} from this server.").format(_label(provider)))
	except (litellm.NotFoundError, litellm.PermissionDeniedError):
		return _refused(
			"not_offered", _("{0} doesn't offer this model to your key.").format(_label(provider))
		)
	except Exception as e:
		text = str(e).lower()
		if any(sign in text for sign in NO_CREDIT):
			return _refused("no_credit", _("This {0} account is out of credit.").format(_label(provider)))
		if "max_tokens" in text or "max tokens" in text:
			return None  # it answered, only longer than the check allows
		return _refused("failed", str(e)[:300] or type(e).__name__)
	return None


def _check_model(name: str) -> dict[str, Any]:
	"""Check a saved model with the key it would use: its own, else its service's. One that doesn't
	answer is switched off (one that couldn't be reached may answer later, so it stays as it is)."""
	from frappe.flow.lib.model import resolve_provider_credentials

	model = frappe.get_doc("Flow Model", name)
	service = resolve_provider_credentials(model.model_id)
	refused = _check(
		model.model_id,
		model.get_password("api_key", raise_exception=False) or service.get("api_key"),
		model.base_url or service.get("base_url"),
	)
	if refused and refused["reason"] != "unreachable" and model.enabled:
		frappe.db.set_value("Flow Model", name, "enabled", 0)
	result = refused or {"ok": True}
	frappe.cache.hset(MODEL_CHECKS, name, result)
	return result


def _save_provider(provider: str, api_key: str | None, base_url: str | None) -> None:
	doc = (
		frappe.get_doc("Flow Provider", provider)
		if frappe.db.exists("Flow Provider", provider)
		else frappe.new_doc("Flow Provider", provider=provider)
	)
	doc.update({"enabled": 1, "api_key": api_key, "base_url": base_url})
	doc.save()


def _save_model(provider: str, model: str) -> str:
	"""The Flow Model for `model`, saved once: a second connection keeps the first one's."""
	model_id = f"{provider}/{model}"
	if name := frappe.db.get_value("Flow Model", {"model_id": model_id}):
		frappe.db.set_value("Flow Model", name, "enabled", 1)
		return name
	title = _title(model)
	if frappe.db.exists("Flow Model", title):
		title = f"{title} ({_label(provider)})"
	doc = frappe.new_doc("Flow Model", title=title, provider=provider, model_id=model, enabled=1)
	doc.insert()
	return doc.name


def _title(model: str) -> str:
	"""claude-sonnet-5-5 → Claude Sonnet 5.5, gpt-5.4-mini → GPT-5.4 mini, llama3.3:70b as it is."""
	name = model.rpartition("/")[2]
	if ":" in name:
		return name
	name = re.sub(r"(?<=\d)-(?=\d(?:\D|$))", ".", name)  # 5-5 → 5.5
	if name.startswith("gpt-"):
		head, _sep, rest = name[4:].partition("-")
		return f"GPT-{head} {rest.replace('-', ' ')}".strip()
	return " ".join(part if part[:1].isdigit() else part.capitalize() for part in name.split("-"))


def _admins() -> list[str]:
	"""Enabled users who may connect a service."""
	users = frappe.get_all(
		"Has Role",
		filters={"role": "System Manager", "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	return frappe.get_all(
		"User",
		filters={"name": ("in", users), "enabled": 1, "user_type": "System User"},
		pluck="name",
		order_by="creation asc",
	)
