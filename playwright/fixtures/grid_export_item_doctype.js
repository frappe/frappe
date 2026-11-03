export default {
	name: "Grid Export Item",
	doctype: "DocType",
	module: "Custom",
	custom: 1,
	istable: 1,
	editable_grid: 1,
	fields: [
		{
			fieldname: "item_name",
			fieldtype: "Data",
			label: "Item Name",
			in_list_view: 1,
			reqd: 1,
		},
		{
			fieldname: "qty",
			fieldtype: "Int",
			label: "Qty",
			in_list_view: 1,
		},
		{
			fieldname: "rate",
			fieldtype: "Currency",
			label: "Rate",
			permlevel: 1,
		},
		{
			fieldname: "internal_note",
			fieldtype: "Data",
			label: "Internal Note",
			permlevel: 2,
		},
	],
	permissions: [],
};
