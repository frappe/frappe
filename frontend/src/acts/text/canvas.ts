import type { ActSchema } from "../schema/checkValue";
import type { ActText } from "./types";

const KEY_TYPES: Record<string, ActSchema> = {
	name: { type: "string", description: "The new container's name." },
	label: { type: "string", description: "The label the person sees." },
	index: { type: "integer", description: "The position among its siblings, counting from 0." },
	tab: { type: "string", description: "A tab's name." },
	section: { type: "string", description: "A section's name." },
	column: { type: "string", description: "A column's name; names repeat across sections, so send section too." },
	to_section: { type: "string", description: "The section to move the column into." },
	container: { type: "string", description: "The kind of container: \"tab\", \"section\" or \"column\"." },
	property: { type: "string", description: "The container property to set." },
	value: { description: "The new value." },
	fieldname: { type: "string", description: "A field's fieldname." },
};

/** The keys of one canvas edit, as the server's `CANVAS_ACTS` lists them. */
function keys(names: string[], required: string[] = [], optional = false): ActSchema {
	return {
		type: optional ? ["object", "null"] : "object",
		properties: Object.fromEntries(names.map((name) => [name, KEY_TYPES[name]])),
		required,
		additionalProperties: false,
	};
}

const staged = "The edit is staged, not saved: use editor.save to save.";
const staging = staged + " Data is true when staged, false when the editor refused it.";
const place = ["fieldname", "section", "column", "index", "tab"];

export default {
	add_tab: {
		description: "Add a tab to the layout open in the canvas. Leave out the value for a tab with the default name. The new tab is selected. " + staged,
		input: keys(["name", "label", "index"], [], true),
	},
	remove_tab: {
		description: "Remove a tab from the layout. Its content moves to the neighbouring one. " + staging,
		input: keys(["tab"], ["tab"]),
		output: { type: "boolean" },
	},
	move_tab: {
		description: "Move a tab to another position among the tabs. " + staging,
		input: keys(["tab", "index"], ["tab", "index"]),
		output: { type: "boolean" },
	},
	add_section: {
		description: "Add a section to a tab of the layout; with no value it goes into the open tab. The new section is selected. " + staged,
		input: keys(["tab", "name", "label", "index"], [], true),
	},
	remove_section: {
		description: "Remove a section from the layout. Its content moves to the neighbouring one. " + staging,
		input: keys(["section"], ["section"]),
		output: { type: "boolean" },
	},
	move_section: {
		description: "Move a section to a position, in the same tab or another one. " + staging,
		input: keys(["section", "tab", "index"], ["section"]),
		output: { type: "boolean" },
	},
	add_column: {
		description: "Add a column to a section. " + staging,
		input: keys(["section", "name", "index"], ["section"]),
		output: { type: "boolean" },
	},
	remove_column: {
		description: "Remove a column from a section. Its content moves to the neighbouring one. " + staging,
		input: keys(["column", "section"], ["column"]),
		output: { type: "boolean" },
	},
	move_column: {
		description: "Move a column to a position, in its section or another section. " + staging,
		input: keys(["column", "section", "to_section", "index"], ["column"]),
		output: { type: "boolean" },
	},
	set_container_property: {
		description: "Set one property of a tab, section or column, such as its label or a collapsible flag. " + staging,
		input: keys(["container", "section", "property", "value"], ["property"]),
		output: { type: "boolean" },
	},
	place_field: {
		description: "Place an unplaced field into a column of a section. " + staging,
		input: keys(place, ["fieldname"]),
		output: { type: "boolean" },
	},
	move_field: {
		description: "Move a placed field to another column, section or position. " + staging,
		input: keys(place, ["fieldname"]),
		output: { type: "boolean" },
	},
	unplace_field: {
		description: "Take a field off the layout; it stays on the DocType. " + staging,
		input: keys(["fieldname"], ["fieldname"]),
		output: { type: "boolean" },
	},
	select: {
		description: "Select a tab, section, column or field in the canvas, or clear the selection with null. It changes only what the field panel shows.",
		input: {
			type: ["object", "null"],
			properties: {
				kind: { type: "string", enum: ["tab", "section", "column", "field"] },
				tab: KEY_TYPES.tab,
				section: KEY_TYPES.section,
				column: KEY_TYPES.column,
				fieldname: KEY_TYPES.fieldname,
			},
			required: ["kind"],
		},
	},
} satisfies Record<string, ActText>;
