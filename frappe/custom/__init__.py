import frappe
from frappe import _

# The customizations that an app can hide while the site disables the app. Each doctype
# maps to the filter key that holds the doctype which the customization changes.
CUSTOMIZATION_DOCTYPES = {
	"Custom Field": "dt",
	"Property Setter": "doc_type",
	"Custom DocPerm": "parent",
}


def hide_customizations(customizations: dict[str, list[dict]]):
	"""
	Make Frappe ignore these customizations. The rows and their data stay in the database.

	Use `unhide_customizations` to apply them again. Use this function for a temporary
	state, for example when the site disables the app that owns them.

	:param customizations: A dict. It maps a customization doctype to a list of row filters.

	Example:

	```
	hide_customizations(
	    {
	        "Custom Field": [{"dt": "Address", "fieldname": "custom_a"}],
	        "Custom DocPerm": [{"parent": "Project", "role": "HR User"}],
	    }
	)
	```
	"""
	_set_is_app_disabled(customizations, 1)


def unhide_customizations(customizations: dict[str, list[dict]]):
	"""
	Apply the customizations again. This undoes `hide_customizations`.

	:param customizations: A dict. It maps a customization doctype to a list of row filters.
	"""
	_set_is_app_disabled(customizations, 0)


def _set_is_app_disabled(customizations: dict[str, list[dict]], value: int):
	changed_doctypes = set()

	for doctype, rows in customizations.items():
		target_key = CUSTOMIZATION_DOCTYPES.get(doctype)
		if not target_key:
			frappe.throw(_("{0} is not a customization doctype.").format(doctype))

		# This column is new. A site that did not migrate yet does not have it.
		if not frappe.db.has_column(doctype, "is_app_disabled"):
			frappe.throw(_("{0} has no is_app_disabled column. Run bench migrate first.").format(doctype))

		for filters in rows:
			# Without one doctype name the update can change the rows of other doctypes.
			if not isinstance(filters.get(target_key), str):
				frappe.throw(_("{0} must be a doctype name in a {1} filter.").format(target_key, doctype))

			frappe.db.set_value(doctype, filters, "is_app_disabled", value, update_modified=False)
			changed_doctypes.add(filters[target_key])

	# Clear only the doctypes that changed. This keeps a disable or an enable fast.
	for doctype in changed_doctypes:
		frappe.clear_cache(doctype=doctype)
