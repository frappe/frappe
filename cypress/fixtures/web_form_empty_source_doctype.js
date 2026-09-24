// nothing here survives get_fields_for_doctype: Heading and Button carry no value and a
// Section Break is layout, so the picker has nothing to offer
export default {
	name: "Web Form Empty Source",
	custom: 1,
	actions: [],
	doctype: "DocType",
	engine: "InnoDB",
	fields: [
		{ fieldname: "details_section", fieldtype: "Section Break", label: "Details" },
		{ fieldname: "details_heading", fieldtype: "Heading", label: "Details" },
		{ fieldname: "run_action", fieldtype: "Button", label: "Run Action" },
	],
	modified_by: "Administrator",
	module: "Custom",
	owner: "Administrator",
	permissions: [
		{
			create: 1,
			delete: 1,
			email: 1,
			print: 1,
			read: 1,
			role: "System Manager",
			share: 1,
			write: 1,
		},
	],
	autoname: "format:WFE-{####}",
	sort_field: "creation",
	sort_order: "ASC",
};
