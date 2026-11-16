import type { ActSchema } from "../schema/checkValue";
import type { ActText } from "./types";

const fieldname: ActSchema = { type: "string", minLength: 1, description: "A field's fieldname." };
const staged = "The edit is staged, not saved: use editor.save to save.";
const stagedBool = `${staged} Data is true when staged, false when the editor refused it.`;

export default {
	add_field: {
		description: `Add a field to the DocType. Leave out the value to open the editor's own add-a-field row instead. The new field is selected. ${staged}`,
		input: {
			type: ["object", "null"],
			properties: {
				label: { type: "string", minLength: 1, description: "The label the person sees." },
				fieldname: { type: "string", description: "Leave it out to derive it from the label." },
				fieldtype: { type: "string", description: "The field type, such as \"Data\" or \"Link\"." },
				options: { type: "string", description: "The options, such as a Link's DocType." },
				properties: { type: "object", description: "More field properties by name." },
				tab: { type: "string", description: "A tab's name, to place the field." },
				section: { type: "string", description: "A section's name, to place the field." },
				column: { type: "string", description: "A column's name, to place the field." },
				index: { type: "integer", description: "The position in the column." },
			},
			required: ["label"],
		},
	},
	set_field_property: {
		description: `Set one property of a field, or several as one undo step. ${staged}`,
		input: {
			type: "object",
			properties: {
				fieldname,
				property: { type: "string", description: "The property's name, such as \"reqd\"." },
				value: { description: "The new value." },
				properties: { type: "object", description: "Several properties by name, instead of property and value." },
			},
			required: ["fieldname"],
		},
	},
	fetch_field: {
		description: `Add a read-only field that copies a field of a Link field's record, right after the Link. The new field is selected. ${staged}`,
		input: {
			type: "object",
			properties: {
				link: { ...fieldname, description: "The fieldname of the Link field." },
				source: {
					type: "object",
					description: "The field of the linked DocType to copy.",
					properties: {
						fieldname: { type: "string", minLength: 1 },
						label: { type: "string" },
						fieldtype: { type: "string" },
						options: { type: "string" },
					},
					required: ["fieldname"],
				},
			},
			required: ["link", "source"],
			additionalProperties: false,
		},
	},
	reset_field_property: {
		description: `Customize mode only: put one property of a field back to the app's value. ${stagedBool}`,
		input: {
			type: "object",
			properties: { fieldname, property: { type: "string", minLength: 1, description: "The property's name." } },
			required: ["fieldname", "property"],
			additionalProperties: false,
		},
		output: { type: "boolean" },
	},
	rename_field: {
		description: `Change a field's fieldname. ${staged}`,
		input: {
			type: "object",
			properties: { fieldname, new_fieldname: { type: "string", minLength: 1, description: "The new fieldname." } },
			required: ["fieldname", "new_fieldname"],
			additionalProperties: false,
		},
	},
	delete_field: {
		description: `Remove a field from the DocType. It asks no delete confirm itself, so use it only when the person asked for it. ${staged}`,
		input: { type: "object", properties: { fieldname }, required: ["fieldname"], additionalProperties: false },
	},
	add_child_table: {
		description: `Add a Table field with a new child DocType, or one that exists. ${stagedBool}`,
		input: {
			type: "object",
			properties: {
				name: { type: "string", minLength: 1, description: "The child DocType's name." },
				table_field: { type: "string", minLength: 1, description: "The fieldname of the new Table field." },
				label: { type: "string", description: "The Table field's label." },
				link: { type: "string", description: "The fieldname of the field to place the Table after." },
			},
			required: ["name", "table_field"],
			additionalProperties: false,
		},
		output: { type: "boolean" },
	},
	open_child: {
		description: "Open the editor of the child DocType behind a Table field.",
		input: { type: "string", minLength: 1, description: "The Table field's fieldname." },
	},
	reorder_field: {
		description: `Move a field to a position among the fields; a Table field's grid column moves too. ${stagedBool}`,
		input: {
			type: "object",
			properties: { fieldname, index: { type: "integer", description: "The new position." } },
			required: ["fieldname", "index"],
			additionalProperties: false,
		},
		output: { type: "boolean" },
	},
} satisfies Record<string, ActText>;
