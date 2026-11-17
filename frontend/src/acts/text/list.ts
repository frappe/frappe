import type { ActText } from "./types";

const scope = {
	type: "string",
	enum: ["user", "site"],
	description: "\"user\" for the person's own default, \"site\" for everyone's.",
};
const selected = "It acts on the rows now selected, so select rows first.";
const rows = {
	type: ["array", "null"],
	items: { type: "string" },
	description: "Ignored: the act always uses the current selection. The bulk bar sends the selected row names; leave it out.",
};

const loadedRows = {
	type: "object",
	properties: {
		total: { type: "number", description: "How many records the filters match, not only the rows loaded." },
		rows: {
			type: "array",
			description: "The rows loaded, up to 20, in the list's order.",
			items: {
				type: "object",
				properties: {
					name: { type: "string", description: "The record's name, which list.select takes." },
					title: { type: "string", description: "The record's title, or its name when it has none." },
				},
			},
		},
	},
};

export default {
	set_filters: {
		description:
			"Replace the list's filters and reload the rows. Each filter is [fieldname, operator, value]: operators = != like not like in not in is is not > < >= <= between timespan; in, not in and between take a list; like matches text anywhere in the value. An empty list clears the filters. Returns the rows now loaded.",
		input: {
			type: "object",
			properties: {
				filters: {
					type: "array",
					description: "For example [[\"status\", \"=\", \"Paid\"], [\"grand_total\", \">\", 1000]].",
					items: { type: "array" },
				},
			},
			required: ["filters"],
			additionalProperties: false,
		},
		output: loadedRows,
	},
	set_sort: {
		description: "Replace the list's sort and reload the rows. The first entry sorts first. An empty list clears the sort. Returns the rows now loaded.",
		input: {
			type: "object",
			properties: {
				sort: {
					type: "array",
					description: "For example [{\"fieldname\": \"grand_total\", \"direction\": \"desc\"}].",
					items: {
						type: "object",
						properties: { fieldname: { type: "string", minLength: 1 }, direction: { type: "string", enum: ["asc", "desc"] } },
						required: ["fieldname", "direction"],
						additionalProperties: false,
					},
				},
			},
			required: ["sort"],
			additionalProperties: false,
		},
		output: loadedRows,
	},
	set_columns: {
		description: "Replace the columns the list shows, in this order. An empty list restores the default columns. A label you send is ignored: a column shows its field's own label. Returns the columns now shown.",
		input: {
			type: "object",
			properties: {
				columns: {
					type: "array",
					description: "For example [{\"fieldname\": \"status\"}, {\"fieldname\": \"modified\"}].",
					items: {
						type: "object",
						properties: {
							fieldname: { type: "string", minLength: 1 },
							label: { type: "string", description: "Ignored: a column shows its field's label." },
						},
						required: ["fieldname"],
						additionalProperties: false,
					},
				},
			},
			required: ["columns"],
			additionalProperties: false,
		},
		output: {
			type: "object",
			properties: {
				columns: {
					type: "array",
					description: "The columns now shown, in order.",
					items: { type: "object", properties: { fieldname: { type: "string" }, label: { type: "string" } } },
				},
			},
		},
	},
	set_page_size: {
		description: "Show this many rows at a time and reload. Loaded rows beyond it drop off, as when the person picks the size. Returns the rows now loaded.",
		input: {
			type: "object",
			properties: { size: { type: "integer", enum: [20, 100, 500, 2500] } },
			required: ["size"],
			additionalProperties: false,
		},
		output: loadedRows,
	},
	load_more: {
		description: "Load the next page of rows below the ones shown. Not available when every matching row is loaded. Returns the rows now loaded.",
		output: loadedRows,
	},
	select: {
		description: "Replace the selection with these rows. Every name must be a row loaded now (read state().rows); set the filters first to load others. The bulk acts then act on them.",
		input: {
			type: "object",
			properties: { names: { type: "array", description: "The names of the rows to select.", items: { type: "string", minLength: 1 } } },
			required: ["names"],
			additionalProperties: false,
		},
		output: {
			type: "object",
			properties: { selected: { type: "array", items: { type: "string" }, description: "The names now selected." } },
		},
	},
	create: {
		description: "Open the Create dialog for a new record of this list's DocType.",
	},
	favourite: {
		description: "Star this list, or remove the star.",
	},
	open_view: {
		description: "Switch this list to a saved view, such as the table or the cards.",
		input: {
			type: "object",
			properties: { key: { type: "string", minLength: 1, description: "The view's key." } },
			required: ["key"],
			additionalProperties: false,
		},
	},
	set_default_view: {
		description: "Make a view the one this list opens with.",
		input: {
			type: "object",
			properties: { key: { type: "string", minLength: 1, description: "The view's key." }, scope },
			required: ["key", "scope"],
			additionalProperties: false,
		},
	},
	clear_default_view: {
		description: "Remove the list's default view, so it opens with the standard one.",
		input: { type: "object", properties: { scope }, required: ["scope"], additionalProperties: false },
	},
	customize_quick_filter: {
		description: "Open the editor for the quick filters shown above the list.",
	},
	customize_form: {
		description: "Open the DocType editor in Customize mode for this list's DocType. Leaves this page.",
	},
	edit_doctype: {
		description: "Open the DocType editor in Design mode for this list's DocType. Leaves this page. Developer mode only.",
	},
	submit: {
		description: `Submit the selected draft records after the person confirms in the bulk status dialog. ${selected}`,
		input: rows,
	},
	cancel: {
		description: `Cancel the selected submitted records after the person confirms in the bulk status dialog. ${selected}`,
		input: rows,
	},
	assign: {
		description: `Assign the selected records to users at once, with no dialog: send the users' ids. Send no value to open the bulk dialog where the person picks the users. ${selected}`,
		input: {
			type: ["array", "null"],
			items: { type: "string", minLength: 1 },
			description: "The ids of the users to assign, such as \"jane@example.com\". Leave out to open the dialog.",
		},
		output: {
			type: ["object", "null"],
			properties: {
				assigned: { type: "array", items: { type: "string" }, description: "The records now assigned." },
				failed: { type: "array", description: "The records the server refused, each with its name and error." },
				background: { type: "boolean", description: "True when the server took the run to the background, so no record is listed yet." },
			},
		},
	},
	clear_assignment: {
		description: `Remove every assignment from the selected records after the person confirms. ${selected}`,
		input: rows,
	},
	apply_assignment_rule: {
		description: `Apply the DocType's assignment rules to the selected records after the person confirms. ${selected}`,
		input: rows,
	},
	add_tags: {
		description: `Open the bulk dialog where the person picks tags to add to the selected records. ${selected}`,
		input: rows,
	},
	remove_tags: {
		description: `Open the bulk dialog where the person picks tags to remove from the selected records. ${selected}`,
		input: rows,
	},
	follow: {
		description: `Follow the selected records, after the person confirms. ${selected}`,
		input: rows,
	},
	unfollow: {
		description: `Stop following the selected records, after the person confirms. ${selected}`,
		input: rows,
	},
	share: {
		description: `Open the bulk dialog where the person picks users to share the selected records with. ${selected}`,
		input: rows,
	},
	mark_seen: {
		description: `Mark the selected records as seen, after the person confirms. ${selected}`,
		input: rows,
	},
	mark_unseen: {
		description: `Mark the selected records as not seen, after the person confirms. ${selected}`,
		input: rows,
	},
	print: {
		description: `Open the print dialog for the selected records. The person picks the format and prints. ${selected}`,
		input: rows,
	},
	edit: {
		description: `Open the bulk edit dialog where the person sets one field on the selected records. ${selected}`,
		input: rows,
	},
	copy: {
		description: `Copy the names of the selected records to the clipboard. ${selected}`,
		input: rows,
	},
	export: {
		description: `Open the export dialog for the selected records. The person picks the fields and the file type. ${selected}`,
		input: rows,
	},
	delete: {
		description: `Delete the selected records after the person confirms in the Delete dialog. Cannot be undone. ${selected}`,
		input: rows,
	},
	favourite_records: {
		description: `Star the selected records. ${selected}`,
		input: rows,
	},
	unfavourite_records: {
		description: `Remove the star from the selected records. ${selected}`,
		input: rows,
	},
	unfavourite_matching: {
		description: "Remove the star from every record the current filters match, not only the loaded rows.",
	},
	toggle_row: {
		description: "Select or deselect the row under the pointer. It needs a pointer on a row, so an agent cannot use it.",
	},
	extend_row: {
		description: "Select every row from the last selected one to the row under the pointer. It needs a pointer on a row, so an agent cannot use it.",
	},
	open_bulk_menu: {
		description: `Open the menu of bulk actions. ${selected}`,
		input: rows,
	},
	clear_selection: {
		description: "Deselect every row.",
	},
} satisfies Record<string, ActText>;
