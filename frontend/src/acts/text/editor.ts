import type { ActText } from "./types";

export default {
	save: {
		description:
			"Save the staged edits of the DocType, and write its files in developer mode. A refusal shows in the editor's banner, not in the result. Present only while there is something to save.",
	},
	reload_and_reapply: {
		description: "After a save conflict: load the DocType again and re-apply the person's staged edits on top. Present only after a conflict.",
	},
	write_files_again: {
		description: "After the DocType saved but its files failed to write: write the files again. Present only after that failure.",
	},
	open_list: {
		description: "Leave the editor for the list of the DocType being edited.",
	},
	undo: {
		description: "Take back the last staged edit. Present only while there is one to take back.",
	},
	redo: {
		description: "Put back the staged edit that undo took back. Present only after an undo.",
	},
	open_tab: {
		description: "Show one tab of the editor: the layout editor, the settings, or the preview of a record.",
		input: { type: "string", enum: ["editor", "settings", "preview"], description: "The tab." },
	},
	find: {
		description: "Open or close the finder, which searches the DocType's fields and settings by name. It reads nothing back.",
	},
	preview_record: {
		description: "Open the Preview tab with a record of this DocType, or an empty form with null. Use the act's options to find a record.",
		input: { type: ["string", "null"], description: "The record's name, or null for an empty form." },
	},
	set_mode: {
		description:
			"Switch the editor between Design, which changes the DocType itself, and Customize, which changes this site only. When staged edits are pending the person is asked what to do with them first, and the act waits.",
		input: { type: "string", enum: ["Design", "Customize"], description: "The mode to switch to." },
	},
} satisfies Record<string, ActText>;
