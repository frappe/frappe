# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url

from .providers.geoapify import Geoapify
from .providers.here import Here
from .providers.nomatim import Nomatim


class GeolocationSettings(Document):
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

	pass


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

	return list(provider.autocomplete(txt))
