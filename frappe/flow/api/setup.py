# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Connecting an AI service, from Flow's first run or its Models settings. The key is checked with
the service before it is saved, so a bad key is caught at setup and not in the first chat. No model
is added with it: each is picked, and asked one message when it is."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

import frappe
from frappe import _
from frappe.utils import escape_html, get_fullname, get_url, sbool

# Beside the site, a model server needs no key
OLLAMA_URL = "http://localhost:11434"
OLLAMA_PROVIDER = "ollama_chat"

# what a service says when the account, not the key, is the problem
NO_CREDIT = ("credit balance", "insufficient_quota", "billing", "payment required", "quota")
# and when it has no model by that name
NO_MODEL = ("not a valid model", "model_not_found", "does not exist", "invalid model", "unknown model")
ASK_ADMIN_CACHE = "flow_setup_asked"
# where a key is checked when the models list doesn't need one
KEY_URLS = {"openrouter": "https://openrouter.ai/api/v1/key"}


@frappe.whitelist()
def setup_options() -> dict[str, Any]:
	"""What the first run offers beyond the listed services: a model server running beside the site."""
	_check_can_connect()
	return {"ollama": _ollama_models()}


@frappe.whitelist(methods=["POST"])
def connect(provider: str, api_key: str | None = None) -> dict[str, Any]:
	"""Check `api_key` with `provider` by asking for its models, then save the provider. A key the
	service refuses saves nothing and says why: `wrong_key` or `unreachable`."""
	_check_can_connect()
	provider = (provider or "").strip().lower()
	api_key = (api_key or "").strip() or None

	if provider == "ollama":
		provider, base_url = OLLAMA_PROVIDER, OLLAMA_URL
		if not _ollama_models():
			return _refused("unreachable", _("Ollama isn't answering on this server any more."))
	else:
		from flow_harness.model.discovery import MODEL_ENDPOINTS

		if provider not in MODEL_ENDPOINTS:
			frappe.throw(_("Flow can't connect {0} here. Add it in Settings.").format(escape_html(provider)))
		if not api_key:
			frappe.throw(_("Paste the key first."))
		base_url = None
		try:
			_ask_with_key(KEY_URLS.get(provider, MODEL_ENDPOINTS[provider]), provider, api_key)
		except requests.HTTPError as e:
			# Gemini and xAI answer a bad key with 400. A 403 is a key the service knows that may not
			# list models (an OpenAI key restricted to chat): the first model added checks it
			if e.response is not None and e.response.status_code in (400, 401):
				return _refused("wrong_key", _("{0} didn't accept this key.").format(_label(provider)))
			# a service without a list to ask: the first model added checks the key
		except requests.RequestException:
			return _refused("unreachable", _("Couldn't reach {0} from this server.").format(_label(provider)))

	_save_provider(provider, api_key, base_url)
	return {"ok": True}


@frappe.whitelist()
def services() -> dict[str, Any]:
	"""The Models tab: each provider with its models, and the models that carry a key of their own.
	For those who may change models; the rest pick one in the chat."""
	frappe.has_permission("Flow Model", "write", throw=True)
	providers = frappe.get_list(
		"Flow Provider", fields=["name", "enabled", "base_url"], order_by="creation asc"
	)
	models = frappe.get_list(
		"Flow Model",
		fields=["name", "title", "model_id", "provider", "enabled", "embedding"],
		order_by="creation asc",
	)
	result = []
	for provider in providers:
		own = [model for model in models if model.provider == provider.name]
		result.append(
			{
				**provider,
				"label": _label(provider.name, provider.base_url),
				"models": own,
			}
		)
	listed = {provider.name for provider in providers}
	return {"services": result, "other": [model for model in models if model.provider not in listed]}


@frappe.whitelist(methods=["POST"])
def add_model(provider: str, model_id: str, for_chat: bool = False) -> dict[str, Any]:
	"""One of `provider`'s models, named as people know it, saved once it answers one message (one
	saved already is switched on). One that doesn't is not saved, and its `check` says why."""
	frappe.has_permission("Flow Model", "create", throw=True)
	model = model_id.strip().removeprefix(f"{provider}/")
	service = frappe.get_doc("Flow Provider", provider)
	service.check_permission("read")
	args = (f"{provider}/{model}", service.get_password("api_key", raise_exception=False), service.base_url)
	# one that doesn't chat may embed, whatever its name or LiteLLM knows of it; the first run
	# wants one to chat with
	refused, embedding = _check(*args), False
	if refused and refused["reason"] in ("not_offered", "failed") and not sbool(for_chat):
		embedding = not _check(*args, embedding=True)
	if refused and not embedding:
		return {"check": refused}
	name = _save_model(provider, model, embedding)
	saved = frappe.db.get_value("Flow Model", name, ["name", "title", "model_id", "enabled"], as_dict=True)
	return {**saved, "embedding": embedding, "check": {"ok": True}}


@frappe.whitelist(methods=["POST"])
def remove_provider(provider: str) -> None:
	"""A provider and its models, all or none: a model still in use stops it whole."""
	for name in frappe.get_all("Flow Model", {"provider": provider}, pluck="name"):
		frappe.delete_doc("Flow Model", name)
	frappe.delete_doc("Flow Provider", provider)


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
					"subject": _("{0} would like to use Flow. Connect a model provider to set it up.").format(
						frappe.bold(escape_html(get_fullname(frappe.session.user)))
					),
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


def _ask_with_key(url: str, provider: str, api_key: str) -> None:
	"""Ask the service at `url` with the key; raises when it refuses."""
	params: dict[str, Any] = {}
	if provider == "anthropic":
		headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
		params = {"limit": 1000}
	elif provider == "gemini":
		headers = {"x-goog-api-key": api_key}
		params = {"pageSize": 1000}
	else:
		headers = {"Authorization": f"Bearer {api_key}"}
	requests.get(url, headers=headers, params=params, timeout=10).raise_for_status()


def _ollama_models() -> list[str]:
	"""The models an Ollama beside the site has pulled; none when it isn't running."""
	try:
		response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=0.5)
		response.raise_for_status()
		return [row["name"] for row in response.json().get("models", []) if row.get("name")]
	except (requests.RequestException, ValueError, KeyError):
		return []


def _check(
	model_id: str, api_key: str | None, base_url: str | None, embedding: bool = False
) -> dict[str, Any] | None:
	"""A one-message call to the model, or one input to embed: None when it answers, else why it
	didn't."""
	import litellm

	provider, _sep, model = model_id.partition("/")
	kwargs: dict[str, Any] = {"model": model_id, "api_key": api_key, "timeout": 20}
	if base_url:
		kwargs["api_base"] = base_url
	try:
		if embedding:
			litellm.embedding(**kwargs, input=["ping"])
		else:
			litellm.completion(**kwargs, messages=[{"role": "user", "content": "ping"}], max_tokens=16)
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
		if any(sign in text for sign in NO_MODEL):
			return _refused("not_offered", _("{0} has no model called {1}.").format(_label(provider), model))
		return _refused("failed", _reason(e))
	return None


def _reason(e: Exception) -> str:
	"""A service's own message, not LiteLLM's wrapping of it: the JSON's `message`, else the text
	without its exception names."""
	text = str(e)
	if found := re.search(r'"message"\s*:\s*"([^"]+)"', text):
		return found.group(1)[:300]
	return re.sub(r"^litellm\.\w+:\s*(\w+\s+-\s+)?", "", text)[:300] or type(e).__name__


def _save_provider(provider: str, api_key: str | None, base_url: str | None) -> None:
	doc = (
		frappe.get_doc("Flow Provider", provider)
		if frappe.db.exists("Flow Provider", provider)
		else frappe.new_doc("Flow Provider", provider=provider)
	)
	doc.update({"enabled": 1, "api_key": api_key, "base_url": base_url})
	doc.save()


def _save_model(provider: str, model: str, embedding: bool = False) -> str:
	"""The Flow Model for `model`, saved once: a second connection keeps the first one's."""
	model_id = f"{provider}/{model}"
	if name := frappe.db.get_value("Flow Model", {"model_id": model_id}):
		frappe.has_permission("Flow Model", "write", doc=name, throw=True)
		frappe.db.set_value("Flow Model", name, {"enabled": 1, "embedding": embedding})
		return name
	title = _title(model)
	if frappe.db.exists("Flow Model", title):
		title = f"{title} ({_label(provider)})"
	doc = frappe.new_doc(
		"Flow Model", title=title, provider=provider, model_id=model, enabled=1, embedding=embedding
	)
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
