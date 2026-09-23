// Drives the Get Fields picker. Every branch the picker has to tell apart gets a field
// here, so one seeded DocType covers them all.
export default {
	name: "Web Form Source",
	custom: 1,
	actions: [],
	doctype: "DocType",
	engine: "InnoDB",
	fields: [
		// a DocType opens with a Tab Break; a rebuild has to drop it, or page 1 comes out blank
		{ fieldname: "details_tab", fieldtype: "Tab Break", label: "Details" },
		{ fieldname: "title", fieldtype: "Data", label: "Title", reqd: 1 },
		{ fieldname: "kind", fieldtype: "Select", label: "Kind", options: "Alpha\nBeta" },
		// the condition is kept only when `kind` is ticked in the same update
		{
			fieldname: "alpha_note",
			fieldtype: "Data",
			label: "Alpha Note",
			depends_on: "eval:doc.kind == 'Alpha'",
		},
		// a bare condition names a field, the same way layout.js reads it
		{ fieldname: "bare_note", fieldtype: "Data", label: "Bare Note", depends_on: "kind" },
		// the other accessor form a condition can use to read the same field
		{
			fieldname: "bracket_note",
			fieldtype: "Data",
			label: "Bracket Note",
			depends_on: "eval:doc['kind'] == 'Alpha'",
		},
		// fn: runs a Desk form script method, which a portal page does not have
		{
			fieldname: "scripted_note",
			fieldtype: "Data",
			label: "Scripted Note",
			depends_on: "fn:is_visible",
		},
		{
			fieldname: "flagged",
			fieldtype: "Check",
			label: "Flagged",
			mandatory_depends_on: "eval:doc.kind == 'Beta'",
			read_only_depends_on: "eval:doc.kind == 'Alpha'",
		},
		// hidden here, so the picker can only offer to remove a row that names it
		{ fieldname: "secret_note", fieldtype: "Data", label: "Secret Note", hidden: 1 },
		// a fieldtype no Web Form renders, so the picker can only offer to remove it
		{ fieldname: "run_action", fieldtype: "Button", label: "Run Action" },
		// a tab past the first one is a real page boundary, so a rebuild keeps it
		{ fieldname: "more_tab", fieldtype: "Tab Break", label: "More" },
		// only reaches the picker with the fieldtype spelled the way the DocType spells it
		{
			fieldname: "roles",
			fieldtype: "Table MultiSelect",
			label: "Roles",
			options: "Has Role",
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
	autoname: "format:WFS-{####}",
	sort_field: "creation",
	sort_order: "ASC",
};
