import type { ActText } from "./types";

export default {
	all_apps: {
		description: "Leave this page for the list of all apps at /apps. Unsaved changes on a record are not asked about.",
	},
	customize_sidebar: {
		description: "Open the dialog that edits the navigation sidebar. The person edits it; the act returns when the dialog opens.",
	},
	copy_link: {
		description: "Copy the link to this page to the clipboard and show a toast. Use it only when the person asks for the link.",
	},
	toggle_sidebar: {
		description: "Collapse the sidebar when it is open, or expand it when it is collapsed.",
	},
	open_settings: {
		description:
			"Open the settings dialog, optionally at one pane or block. Use the act's options to list the panes. Leave out the value for the first pane.",
		input: {
			type: ["object", "null"],
			properties: {
				prefix: { type: "string", description: "The settings group, such as \"desk\"." },
				pane: { type: "string", description: "The pane inside the group, such as \"profile\"." },
				block: { type: "string", description: "The block inside the pane." },
			},
			additionalProperties: false,
		},
	},
	about: {
		description: "Open the About dialog, which shows the app versions. Read-only.",
	},
	my_settings: {
		description: "Open the settings dialog at the person's own profile.",
	},
	theme: {
		description: "Set the color scheme of this browser: light, dark or follow the system.",
		input: { type: "string", enum: ["light", "dark", "system"], description: "The color scheme." },
	},
	back: {
		description:
			"Go back to the page before this one in the tab, as the browser's Back button does. Returns the path it arrived at. On a record with unsaved changes the person is asked to discard them first; if they keep editing, the act fails and the page stays. Fails when the tab has no earlier page.",
		output: {
			type: "object",
			properties: { path: { type: "string", description: "The path of the page now shown." } },
		},
	},
	desk_v1: {
		description: "Leave desk v2 for the classic desk at /app. Unsaved changes on a record are lost without a question.",
	},
	log_out: {
		description: "Ask the person to confirm, then log out and leave the page. Do not use it unless the person asked to log out.",
	},
	create: {
		description:
			"Open the Create dialog for a new record of a DocType, with optional starting values. The person fills the rest and saves. Data is the created record, or null when the person closed the dialog.",
		input: {
			type: ["string", "object"],
			minLength: 1,
			description: "A DocType name, or an object with the DocType and starting values.",
			properties: {
				doctype: { type: "string", minLength: 1, description: "The DocType's name, such as \"ToDo\"." },
				values: { type: "object", description: "Starting values by fieldname." },
			},
			required: ["doctype"],
			additionalProperties: false,
		},
		output: { type: ["object", "null"] },
	},
	open: {
		description:
			"Open a record, the list of a DocType, or a saved view of that list, in this tab. Leave out name to open the list. When the page has unsaved changes the person is asked to discard them, and the act waits.",
		input: {
			type: "object",
			properties: {
				doctype: { type: "string", minLength: 1, description: "The DocType's name, such as \"Sales Invoice\"." },
				name: { type: ["string", "null"], description: "The record's name. Leave it out, or send null, for the list." },
				view: { type: "string", description: "The key of a saved view of the list. Used only without name." },
			},
			required: ["doctype"],
			additionalProperties: false,
		},
		output: {
			type: "object",
			properties: {
				opened: { type: "boolean" },
				path: { type: "string" },
			},
		},
	},
} satisfies Record<string, ActText>;
