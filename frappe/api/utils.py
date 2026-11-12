import frappe
from frappe import _


class FrappeValueError(ValueError):
	http_status_code = 417


def apply_controller_get_list(doctype: str, query):
	"""Let the doctype controller's static `get_list(query)` narrow a list query, as the list route does."""
	from frappe.model.document import get_controller

	controller = get_controller(doctype)
	if not hasattr(controller, "get_list"):
		return query

	try:
		return_value = controller.get_list(query)

		if return_value is None:
			return query

		# Validate that the returned value has a run method (is a QueryBuilder-like object)
		if not hasattr(return_value, "run"):
			frappe.throw(
				_("Custom get_list method for {0} must return a QueryBuilder object or None, got {1}").format(
					doctype, type(return_value).__name__
				)
			)

		return return_value

	except Exception as e:
		frappe.throw(_("Error in {0}.get_list: {1}").format(doctype, str(e) or type(e).__name__))
