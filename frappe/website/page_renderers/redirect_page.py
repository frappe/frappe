import frappe
from frappe.website.utils import build_response


class RedirectPage:
	def __init__(self, path, http_status_code: int = 301) -> None:
		self.path = path
		self.http_status_code = http_status_code

	def can_render(self) -> bool:
		return True

	def render(self):
		return build_response(
			self.path,
			"",
			self.http_status_code,
			{
				"Location": frappe.flags.redirect_location or (frappe.local.response or {}).get("location"),
			},
		)
