from frappe.desk.desktop import get_custom_doctype_list, get_custom_report_list
from frappe.desk.utils import is_item_allowed
from frappe.desk.widgets import WidgetType, desk_views


class ModuleCustomizations(WidgetType):
	"""The DocTypes and Reports a site made in a module, generated and never stored."""

	cache_ttl = 0

	def get_data(self, filters=None):
		module = self.config.get("module") or self.doc.module
		links = get_custom_doctype_list(module) + get_custom_report_list(module)
		items = [link for link in links if is_item_allowed(link["link_to"], link["link_type"], desk_views())]
		return {"items": items} if items else None
