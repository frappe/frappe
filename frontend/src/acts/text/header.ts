import type { ActText } from "./types";

export default {
	favourite: {
		description: "Star this page's record, or this list when on a list page, or remove the star. Returns nothing; read the page state for the new star.",
	},
	favourite_row: {
		description: "The record page's menu row for the star: the same as favourite.",
	},
	follow_row: {
		description: "Follow the record to get its notifications, or stop following it. Present only on DocTypes that track changes.",
	},
	save: {
		description:
			"Save the record open on this page; a new record is inserted. When a required field is empty the person sees the Required fields dialog and the act waits for it. When someone else saved the record first the person is asked what to do. Data is true when the record saved. When it did not, the error says why: a vetoed or refused save or a server error. When the person closes the Required fields dialog the act ends declined.",
		output: { type: "boolean" },
	},
	amend: {
		description: "Amend a cancelled record: open a new draft that copies it. Present only on a cancelled record.",
	},
	assign: {
		description:
			"Assign the record open on this page to one more user. It keeps the assignments there. Use the act's options to find a user by name. A user who is assigned already is refused.",
		input: {
			type: "string",
			minLength: 1,
			description: "The user's ID, the User record's name, such as \"jane@example.com\".",
		},
	},
	rename: {
		description:
			"Open the Rename dialog for this record. The person types the new name, and may tick Merge with an existing record, which asks a second, danger confirm; saying no to it ends the call declined. The act waits for the person.",
	},
	copy_url: {
		description: "Copy this record's URL to the clipboard and show a toast. Use it only when the person asks for the link.",
	},
	copy_id: {
		description: "Copy this record's ID, its name, to the clipboard and show a toast. Use it only when the person asks for it.",
	},
	duplicate: {
		description: "Open a new, unsaved record that starts as a copy of this one. Save it with save.",
	},
	customize_form: {
		description: "Open the DocType editor in Customize mode for this record's DocType. Leaves this page.",
	},
	edit_doctype: {
		description: "Open the DocType editor in Design mode for this record's DocType. Leaves this page. Developer mode only.",
	},
	edit_layout: {
		description: "Open the DocType editor at the layout this record shows. Leaves this page.",
	},
	submit: {
		description:
			"Submit the record, which locks it. The person is asked to confirm first and the act waits for the answer. If the person says no, the call ends declined. Present only on a saved draft of a submittable DocType with no workflow.",
	},
	cancel: {
		description:
			"Cancel a submitted record. The person is asked to confirm in a danger dialog and the act waits for the answer. If the person says no, the call ends declined. When linked records block it, the person sees which ones.",
	},
	delete: {
		description: "Delete this record after the person confirms in a danger dialog. If the person says no, the call ends declined. Leaves the page for the list. Cannot be undone.",
	},
	new: {
		description: "Open the Create dialog for a new record of this list's DocType.",
	},
} satisfies Record<string, ActText>;
