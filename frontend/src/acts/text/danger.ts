import type { ActText } from "./types";

const dialog = "A value applies the change at once, with no dialog. Pending edits first ask the person to save them.";

export default {
	change_kind: {
		description: `Change the DocType's kind. Without a value the Change kind dialog opens and the act waits for the person. ${dialog}`,
		input: {
			type: ["object", "null"],
			properties: { kind: { type: "string", enum: ["regular", "submittable", "tree", "child", "single"] } },
			required: ["kind"],
			additionalProperties: false,
		},
	},
	rename_doctype: {
		description: `Rename the DocType, which renames its table and records' links. Without a value the Rename dialog opens and the act waits for the person. ${dialog}`,
		input: {
			type: ["object", "null"],
			properties: { name: { type: "string", minLength: 1, description: "The new DocType name." } },
			required: ["name"],
			additionalProperties: false,
		},
	},
	move_doctype: {
		description: `Move the DocType to another module. Without a value the Module dialog opens and the act waits for the person. ${dialog}`,
		input: {
			type: ["object", "null"],
			properties: { module: { type: "string", minLength: 1, description: "The module's name." } },
			required: ["module"],
			additionalProperties: false,
		},
	},
	make_standard: {
		description: `Make a custom DocType a standard one that ships with an app. Without a value the Module dialog opens and the act waits for the person. ${dialog}`,
		input: {
			type: ["object", "null"],
			properties: { module: { type: "string", minLength: 1, description: "The module of the app that will own it." } },
			required: ["module"],
			additionalProperties: false,
		},
	},
	delete_doctype: {
		description: "Delete the DocType and all its records, after the person confirms in the Delete dialog. Cannot be undone. Pending edits first ask the person to save them.",
	},
} satisfies Record<string, ActText>;
