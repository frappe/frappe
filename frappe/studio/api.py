import frappe
from frappe.model import display_fieldtypes, no_value_fields, table_fields


@frappe.whitelist()
def get_doctype_fields(doctype: str) -> list[dict]:
	fields = frappe.get_meta(doctype).fields
	# find the name field
	name_field = next((field for field in fields if field.fieldname == "name"), None)
	if not name_field:
		name_field = frappe._dict(
			{
				"fieldname": "name",
				"fieldtype": "Data",
				"label": "ID",
			}
		)
		fields.append(name_field)

	return [
		field
		for field in fields
		if field.fieldtype not in ((set(no_value_fields) | set(display_fieldtypes)) - set(table_fields))
	]


@frappe.whitelist()
def get_whitelisted_methods(doctype: str) -> list[str]:
	from frappe import is_whitelisted
	from frappe.model.base_document import get_controller

	controller = get_controller(doctype)
	whitelisted_methods = []

	for method in controller.__dict__:
		if callable(getattr(controller, method)):
			try:
				is_whitelisted(getattr(controller, method))
				whitelisted_methods.append(method)
			except Exception:
				# not whitelisted
				continue

	return whitelisted_methods


@frappe.whitelist()
def check_app_permission() -> bool:
	if frappe.session.user == "Administrator":
		return True
	if frappe.has_permission("Studio App", ptype="write") and frappe.has_permission(
		"Studio Page", ptype="write"
	):
		return True
	return False


@frappe.whitelist()
def get_app_components(app_name: str) -> set[str]:
	pages = frappe.get_all(
		"Studio Page",
		filters=dict(studio_app=app_name, published=1),
		pluck="blocks",
	)
	components = set()

	def add_blocks(block: dict):
		components.add(block.get("componentName"))
		for child in block.get("children", []):
			add_blocks(child)

	for blocks in pages:
		if isinstance(blocks, str):
			blocks = frappe.parse_json(blocks)
		root_block = blocks[0]
		add_blocks(root_block)

	return components
