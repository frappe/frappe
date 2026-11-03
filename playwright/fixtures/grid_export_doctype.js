export default {
	name: "Grid Export Doctype",
	doctype: "DocType",
	module: "Custom",
	custom: 1,
	is_submittable: 1,
	fields: [
		{
			fieldname: "title",
			fieldtype: "Data",
			label: "Title",
		},
		{
			fieldname: "items",
			fieldtype: "Table",
			label: "Items",
			options: "Grid Export Item",
			allow_bulk_edit: 1,
		},
	],
	permissions: [
		{
			role: "System Manager",
			permlevel: 0,
			read: 1,
			write: 1,
			create: 1,
			delete: 1,
			submit: 1,
			cancel: 1,
		},
		{
			role: "System Manager",
			permlevel: 1,
			read: 1,
			write: 0,
		},
	],
};
