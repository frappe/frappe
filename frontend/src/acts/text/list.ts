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
	description: "The names of the rows, which the bulk bar sends; leave it out to act on the selected rows.",
};

export default {
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
		description: `Open the bulk dialog where the person picks users to assign to the selected records. ${selected}`,
		input: rows,
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
