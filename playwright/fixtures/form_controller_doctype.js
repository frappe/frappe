export default {
	name: "Form Controller Test",
	actions: [],
	custom: 1,
	doctype: "DocType",
	engine: "InnoDB",
	fields: [
		{
			fieldname: "title",
			fieldtype: "Data",
			label: "Title",
		},
		{
			fieldname: "mirror",
			fieldtype: "Data",
			label: "Mirror",
		},
	],
	links: [],
	module: "Custom",
	owner: "Administrator",
	permissions: [
		{
			create: 1,
			delete: 1,
			read: 1,
			role: "System Manager",
			write: 1,
		},
	],
	sort_field: "creation",
	sort_order: "DESC",
};
