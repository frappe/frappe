from urllib.parse import quote_plus

import frappe
from frappe import _
from frappe.utils import cstr
from frappe.website.page_renderers.template_page import TemplatePage


class NotPermittedPage(TemplatePage):
	def __init__(self, path=None, http_status_code=None, exception=""):
		frappe.local.message = cstr(exception)
		super().__init__(path=path, http_status_code=http_status_code)
		self.http_status_code = 403

	def can_render(self):
		return True

	def render(self):
		frappe.local.message_title = _("Not Permitted")
		context = dict(indicator_color="red", fullpage=True)
		if frappe.session.user == "Guest":
			action = f"/login?redirect-to={quote_plus(frappe.request.path)}"
			if frappe.request.path.startswith("/desk/") or frappe.request.path == "/desk":
				action = "/login"
			context.update(primary_action=action, primary_label=_("Login"))
		else:
			from frappe.website.utils import get_home_page

			home = get_home_page()
			home = home if home.startswith("/") else "/" + home
			context.update(primary_action=home, primary_label=_("Home"))
		frappe.local.response["context"] = context
		self.set_standard_path("message")
		return super().render()
