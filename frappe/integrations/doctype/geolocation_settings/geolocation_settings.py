# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import requests

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url

from .providers.geoapify import Geoapify
from .providers.here import Here
from .providers.nomatim import Nomatim


class GeolocationSettings(Document):
	_DOCTYPE_NAME = "Geolocation Settings"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		api_key: DF.Password | None
		base_url: DF.Data | None
		enable_address_autocompletion: DF.Check
		provider: DF.Literal["Geoapify", "Nomatim", "HERE"]
	# end: auto-generated types

	def validate(self):
		if not self.enable_address_autocompletion:
			return

		required = ["provider"]
		if self.provider in ("Geoapify", "HERE"):
			required.append("api_key")
		elif self.provider == "Nomatim":
			required.append("base_url")

		for fieldname in required:
			if not self.get(fieldname):
				frappe.throw(
					_("{0} is required").format(frappe.bold(_(self.meta.get_label(fieldname)))),
					frappe.MandatoryError,
				)


@frappe.whitelist()
def autocomplete(txt: str) -> list[dict]:
	if not txt:
		return []

	settings = frappe.get_single("Geolocation Settings")
	if not settings.enable_address_autocompletion:
		return []

	if settings.provider == "Geoapify":
		provider = Geoapify(settings.get_password("api_key"), frappe.local.lang)
	elif settings.provider == "Nomatim":
		provider = Nomatim(
			base_url=settings.base_url,
			referer=get_url(),
			lang=frappe.local.lang,
		)
	elif settings.provider == "HERE":
		provider = Here(settings.get_password("api_key"), frappe.local.lang)
	else:
		frappe.throw(_("This geolocation provider is not supported yet."))

	try:
		return list(provider.autocomplete(txt))
	except requests.RequestException as e:
		# the exception text carries the provider URL, which includes the API key
		status = getattr(e.response, "status_code", None)
		frappe.log_error(title="Address autocomplete failed", message=f"{type(e).__name__} (status {status})")
		raise frappe.ValidationError(_("Address autocomplete failed")) from None
