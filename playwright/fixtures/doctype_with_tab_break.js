export default {
	name: "Form With Tab Break",
	custom: 1,
	actions: [],
	doctype: "DocType",
	engine: "InnoDB",
	fields: [
		{
			fieldname: "username",
			fieldtype: "Data",
			label: "Name",
			options: "Name",
		},
		{
			fieldname: "tab",
			fieldtype: "Tab Break",
			label: "Tab 2",
		},
		{
			fieldname: "Phone",
			fieldtype: "Data",
			label: "Phone",
			options: "Phone",
			reqd: 1,
		},
	],
	links: [
		{
			group: "Profile",
			link_doctype: "Contact",
			link_fieldname: "user",
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
	quick_entry: 1,
	autoname: "format: Test-{####}",
	sort_field: "creation",
	sort_order: "ASC",
	track_changes: 1,
};
