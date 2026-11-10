export default {
	name: "Form Builder Doctype",
	custom: 1,
	actions: [],
	doctype: "DocType",
	engine: "InnoDB",
	fields: [
		{
			fieldname: "data3",
			fieldtype: "Data",
			label: "Data 3",
		},
		{
			fieldname: "gender",
			fieldtype: "Link",
			label: "Gender",
			options: "Gender",
		},
		{
			fieldname: "tab",
			fieldtype: "Tab Break",
			label: "Tab 2",
		},
		{
			fieldname: "data",
			fieldtype: "Data",
			label: "Data",
		},
		{
			fieldname: "check",
			fieldtype: "Check",
			label: "Check",
		},
		{
			fieldname: "column_1",
			fieldtype: "Column Break",
		},
		{
			fieldname: "data1",
			fieldtype: "Data",
			label: "Data 1",
		},
		{
			fieldname: "section_1",
			fieldtype: "Section Break",
		},
		{
			fieldname: "data2",
			fieldtype: "Data",
			label: "Data 2",
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
