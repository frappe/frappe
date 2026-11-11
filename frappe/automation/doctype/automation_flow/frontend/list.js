export default {
	columns: [{ fieldname: "title" }, { fieldname: "document_type" }, { fieldname: "enabled" }],
	cells: {
		enabled: { switch: true },
	},
	rowActions: [
		{
			act: "shell.frappe.duplicate_automation_flow",
			fields: ["name"],
			value: (row) => row.name,
		},
	],
};
