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


class AIModel(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		api_key: DF.Password
		base_url: DF.Data | None
		enabled: DF.Check
		model_id: DF.Data
		params: DF.JSON | None
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		self._normalize()
		self._validate_model_id()
		self._validate_base_url()
		self._validate_params()
		self._validate_provider_known()

	def _normalize(self):
		for field in ("title", "model_id", "base_url"):
			value = self.get(field)
			if isinstance(value, str):
				self.set(field, value.strip())
		if isinstance(self.api_key, str):
			self.api_key = self.api_key.strip()

	def _validate_model_id(self):
		if not MODEL_ID_PATTERN.match(self.model_id or ""):
			frappe.throw(
				_("Model ID must be in <code>provider/model</code> form (e.g. <code>anthropic/claude-sonnet-4-6</code>). Only lowercase provider names and alphanumerics, dashes, dots, colons or slashes in the model part are allowed."),
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

		kwargs = {
			"model": self.model_id,
			"api_key": self.get_password("api_key", raise_exception=False) or "",
			"messages": [{"role": "user", "content": "ping"}],
			"max_tokens": 1,
			"timeout": 15,
		}
		if self.base_url:
			kwargs["api_base"] = self.base_url

		try:
			litellm.completion(**kwargs)
		except Exception as e:
			frappe.throw(str(e)[:500] or type(e).__name__, title=_(type(e).__name__))

		return {"ok": True, "message": _("Connection OK")}
