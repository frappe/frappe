import type { ActSchema } from "../schema/checkValue";
import type { ActText } from "./types";

const staged = "The edit is staged, not saved: use editor.save to save.";

/** One edit, or a list of edits staged as one undo step. */
function edits(properties: Record<string, ActSchema>, required: string[]): ActSchema {
	return {
		type: ["object", "array"],
		description: "One edit, or a list of edits.",
		properties,
		required,
		items: { type: "object", properties, required },
	};
}

const rule: Record<string, ActSchema> = {
	role: { type: "string", minLength: 1, description: "The role's name." },
	permlevel: { type: "integer", description: "The permission level; 0 when left out." },
	if_owner: { type: "integer", enum: [0, 1], description: "1 for the rule that applies only to the creator's records." },
};

export default {
	set_doctype_property: {
		description: `Set a DocType setting, such as is_submittable or title_field. ${staged}`,
		input: edits({ property: { type: "string", minLength: 1 }, value: { description: "The new value." } }, ["property"]),
	},
	reset_doctype_property: {
		description: `Put a DocType setting back to the app's value. ${staged}`,
		input: edits({ property: { type: "string", minLength: 1 } }, ["property"]),
	},
	set_naming_series: {
		description: `Set the list of naming series, and which one is the default. ${staged}`,
		input: edits(
			{
				options: { type: "array", items: { type: "string", minLength: 1 }, description: "Each series once." },
				default: { type: "string", description: "One of the options; the first when left out." },
			},
			["options"]
		),
	},
	add_permission: {
		description: `Add a permission rule for a role; it starts with read only. ${staged}`,
		input: edits(rule, ["role"]),
	},
	remove_permission: {
		description: `Remove the permission rule of a role. ${staged}`,
		input: edits(rule, ["role"]),
	},
	set_permission: {
		description: `Tick or untick one right of a role's rule; rights it needs or leads to follow. ${staged}`,
		input: edits(
			{ ...rule, right: { type: "string", minLength: 1, description: "A right, such as \"write\" or \"submit\"." }, value: { type: ["boolean", "integer"] } },
			["role", "right"]
		),
	},
	set_if_owner: {
		description: `Limit a role's rule to the records its people created, or lift the limit. ${staged}`,
		input: edits({ ...rule, value: { type: ["boolean", "integer"] } }, ["role"]),
	},
	reset_permissions: {
		description: `Put the permission rules back to the app's. ${staged}`,
		input: edits({}, []),
	},
} satisfies Record<string, ActText>;
