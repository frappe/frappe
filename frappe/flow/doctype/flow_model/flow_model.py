# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import re
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document

MODEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_\-]*\/[A-Za-z0-9][A-Za-z0-9_\-:.\/]*$")

RESERVED_PARAM_KEYS = frozenset(
	{"model", "api_key", "api_base", "base_url", "messages", "stream", "tools", "tool_choice"}
)


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
		model_id: DF.Data
		params: DF.JSON | None
		provider: DF.Link | None
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		self._normalize()
		self._apply_provider()
		self._validate_model_id()
		self._validate_base_url()
		self._validate_params()
		self._validate_provider_known()
		self._resolve_context_window()

	def after_insert(self):
		if not self.enabled:
			return
		from flow.assistant import sync_builtin_assistant

		sync_builtin_assistant(model=self.name)

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

	def _validate_params(self):
		if not self.params:
			return
		try:
			parsed = json.loads(self.params)
		except (TypeError, ValueError):
			frappe.throw(_("Params must be valid JSON."), title=_("Invalid Params"))
		if not isinstance(parsed, dict):
			frappe.throw(_("Params must be a JSON object."), title=_("Invalid Params"))
		conflicting = sorted(RESERVED_PARAM_KEYS.intersection(parsed))
		if conflicting:
			frappe.throw(
				_("Params may not include reserved keys: {0}.").format(", ".join(conflicting)),
				title=_("Reserved Params"),
			)

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
	"""Max input tokens for `model_id` per litellm, or 0 if unknown/unmapped."""
	import litellm

	try:
		info = litellm.get_model_info(model_id)
	except Exception:
		return 0
	return int(info.get("max_input_tokens") or 0)


@frappe.whitelist()
def get_provider_models(provider: str | None = None) -> list[str]:
	if not provider:
		return []

	import litellm

	return sorted(litellm.models_by_provider.get(provider.strip().lower(), set()))
