# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import re
from typing import Any
from urllib.parse import urlparse

import frappe
import requests
from frappe import _
from frappe.model.document import Document

MODEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_\-]*\/[A-Za-z0-9][A-Za-z0-9_\-:.\/]*$")


class FlowModel(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		api_key: DF.Password | None
		base_url: DF.Data | None
		context_window: DF.Int
		enabled: DF.Check
		extra_params: DF.JSON | None
		model_id: DF.Data
		provider: DF.Link | None
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		self._normalize()
		self._apply_provider()
		self._validate_model_id()
		self._validate_base_url()
		self._validate_extra_params()
		self._validate_provider_known()
		self._resolve_context_window()

	def after_insert(self):
		if not self.enabled:
			return
		from flow.assistant import ensure_builtin_assistant

		ensure_builtin_assistant(model=self.name)

	def _normalize(self):
		for field in ("title", "model_id", "base_url"):
			value = self.get(field)
			if isinstance(value, str):
				self.set(field, value.strip())
		if isinstance(self.api_key, str):
			self.api_key = self.api_key.strip()

	def _apply_provider(self):
		# A linked provider lets the user enter just the model; compose the
		# canonical provider/model id. Idempotent if the prefix is already present.
		if not self.provider:
			return
		prefix = f"{self.provider}/"
		if self.model_id and not self.model_id.startswith(prefix):
			self.model_id = prefix + self.model_id

	def _validate_model_id(self):
		if not MODEL_ID_PATTERN.match(self.model_id or ""):
			frappe.throw(
				_(
					"Model ID must be in <code>provider/model</code> form (e.g. <code>anthropic/claude-sonnet-4-6</code>). Only lowercase provider names and alphanumerics, dashes, dots, colons or slashes in the model part are allowed."
				),
				title=_("Invalid Model ID"),
			)

	def _validate_base_url(self):
		if not self.base_url:
			return
		parsed = urlparse(self.base_url)
		if parsed.scheme not in ("http", "https") or not parsed.netloc:
			frappe.throw(
				_("Base URL must be an absolute http(s) URL."),
				title=_("Invalid Base URL"),
			)

	def _validate_extra_params(self):
		self.extra_params = self.extra_params or None  # a JSON column rejects ""
		try:
			params = self.model_params()
		except ValueError:
			frappe.throw(_("Extra Params must be valid JSON."), title=_("Invalid Extra Params"))
		if not isinstance(params, dict):
			frappe.throw(_("Extra Params must be a JSON object."), title=_("Invalid Extra Params"))

	def model_params(self) -> dict[str, Any]:
		"""Extra Params as a dict, sent with every call to this model."""
		return frappe.parse_json(self.extra_params) if self.extra_params else {}

	def _resolve_context_window(self):
		# Always derived from the model — never user input. Keeps the last detected value when
		# litellm can't resolve the model, and 0 otherwise (callers fall back to a default).
		self.context_window = _detect_context_window(self.model_id) or self.context_window or 0

	def _validate_provider_known(self):
		try:
			import litellm
		except ImportError:
			return
		try:
			litellm.get_llm_provider(self.model_id)
		except Exception as e:
			frappe.throw(str(e)[:500], title=_("Invalid Model ID"))

	@frappe.whitelist()
	def test_connection(self):
		self.check_permission("write")

		try:
			import litellm
		except ImportError:
			frappe.throw(
				_("LiteLLM is not installed. Run <code>bench setup requirements</code>."),
				title=_("Missing Dependency"),
			)

		from flow.lib.model import resolve_provider_credentials

		provider_creds = resolve_provider_credentials(self.model_id)
		api_key = self.get_password("api_key", raise_exception=False) or provider_creds.get("api_key") or None
		base_url = self.base_url or provider_creds.get("base_url")

		kwargs = {
			**self.model_params(),
			"model": self.model_id,
			"api_key": api_key,
			"messages": [{"role": "user", "content": "ping"}],
			"max_tokens": 1,
			"timeout": 15,
		}
		if base_url:
			kwargs["api_base"] = base_url

		try:
			litellm.completion(**kwargs)
		except Exception as e:
			frappe.throw(str(e)[:500] or type(e).__name__, title=_(type(e).__name__))

		return {"ok": True, "message": _("Connection OK")}


def _detect_context_window(model_id: str) -> int:
	"""Max input tokens for `model_id` per litellm, else for the id behind its prefix
	(a gateway's custom_openai/openai/gpt-x), or 0 if neither is mapped."""
	import litellm

	for candidate in (model_id, model_id.partition("/")[2]):
		try:
			window = litellm.get_model_info(candidate).get("max_input_tokens")
		except Exception:
			continue
		if window:
			return int(window)
	return 0


@frappe.whitelist()
def get_provider_models(provider: str | None = None) -> list[str]:
	"""A provider's model IDs as they are saved: asked live, else from LiteLLM's catalog."""
	if not provider or not frappe.has_permission("Flow Model", "write"):
		return []
	provider = provider.strip().lower()
	try:
		models = _live_models(provider)
	except Exception:
		import litellm

		models = litellm.models_by_provider.get(provider, set())
	prefix = f"{provider}/"
	return sorted({model if model.startswith(prefix) else prefix + model for model in models})


def _live_models(provider: str) -> list[str]:
	"""The provider's /models list for its key and Base URL, like the harness's model picker."""
	from flow_harness.model.discovery import MODEL_ENDPOINTS

	doc = frappe.get_doc("Flow Provider", provider)
	api_key = doc.get_password("api_key", raise_exception=False) or ""
	base = (doc.base_url or "").rstrip("/")
	url = (base if base.endswith("/models") else f"{base}/models") if base else MODEL_ENDPOINTS[provider]
	if provider == "anthropic":
		headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
	elif provider == "gemini":
		headers = {"x-goog-api-key": api_key}
	else:
		headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
	response = requests.get(url, headers=headers, timeout=10)
	response.raise_for_status()
	data = response.json()
	ids = (row.get("id") or row.get("name") for row in data.get("data", data.get("models")))
	return [str(model_id).removeprefix("models/") for model_id in ids if model_id]
