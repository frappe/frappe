export default `
from frappe import _


def get_data():
	return {
		"fieldname": "doctype_a_with_child_table_with_link_to_doctype_b",
		"non_standard_fieldnames": {
			"Doctype B With Child Table With Link To Doctype A": "doctype_a_with_child_table_with_link_to_doctype_b",
		},
		"internal_links": {
			"Doctype B With Child Table With Link To Doctype A": ["child_table", "doctype_b_with_child_table_with_link_to_doctype_a"],
		},
		"transactions": [
			{"label": _("Reference"), "items": ["Doctype B With Child Table With Link To Doctype A"]},
		],
	}
`;
