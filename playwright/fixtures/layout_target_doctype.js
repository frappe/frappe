export default {
	name: "Layout Target Doctype",
	custom: 1,
	actions: [],
	doctype: "DocType",
	engine: "InnoDB",
	fields: [
		{
			fieldname: "data1",
			fieldtype: "Data",
			label: "Data 1",
		},
		{
			fieldname: "data2",
			fieldtype: "Data",
			label: "Data 2",
		},
		{
			fieldname: "is_special",
			fieldtype: "Check",
			label: "Is Special",
		},
		{
			fieldname: "description",
			fieldtype: "Small Text",
			label: "Description",
		},
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
	sort_field: "creation",
	sort_order: "ASC",
	track_changes: 1,
};
