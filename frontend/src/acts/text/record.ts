import type { ActSchema } from "../schema/checkValue";
import type { ActText } from "./types";

const table: ActSchema = { type: "string", minLength: 1, description: "The fieldname of the child table." };
const idx: ActSchema = {
	type: "integer",
	description: "The row's number as the grid shows it: 1 is the first row. It changes when a row above is removed.",
};
const values: ActSchema = {
	type: "object",
	description: "The new value of each field, by fieldname. They are committed in the order given.",
};
const changes =
	"It fills the form and never saves; use header.save for that. Each value commits as if typed, so a Link is checked, fetched fields fill and the page's handlers run first. It checks every field first, and one that is unknown, hidden, read-only or a table fails the whole call with nothing written.";
const result =
	"It returns the fields that changed, fetched ones included, and the errors on screen, each by fieldname (`table.<idx>.<fieldname>` for a row's cell). A Link that is not found is an error there, not a failure.";

export default {
	set_values: {
		description: `Set fields of the open record. ${changes} ${result}`,
		input: { type: "object", properties: { values }, required: ["values"], additionalProperties: false },
	},
	add_child_row: {
		description: `Add a row at the end of a child table, with the child's defaults, and set \`values\` on it. ${changes} It returns \`idx\` of the new row, its values and the errors on screen.`,
		input: {
			type: "object",
			properties: { table, values: { ...values, description: "The new row's cells, by fieldname. Optional." } },
			required: ["table"],
			additionalProperties: false,
		},
	},
	set_child_values: {
		description: `Set fields of one row of a child table. ${changes} ${result}`,
		input: {
			type: "object",
			properties: { table, idx, values: { ...values, description: "The new value of each cell, by fieldname." } },
			required: ["table", "idx", "values"],
			additionalProperties: false,
		},
	},
	remove_child_row: {
		description:
			"Remove one row of a child table; the rows below move up by one, so read the rows again. It does not save, and it asks nothing. It returns `rows`, how many are left.",
		input: {
			type: "object",
			properties: { table, idx },
			required: ["table", "idx"],
			additionalProperties: false,
		},
	},
	post_comment: {
		description:
			"Post a comment on this record's timeline as the person, through the same send as the comment composer. Plain text: markup is shown as text and each line becomes a paragraph. No mentions or attachments. Returns the comment's name. The composer's draft stays as it is.",
		input: {
			type: "object",
			properties: { content: { type: "string", minLength: 1, description: "The comment's text." } },
			required: ["content"],
			additionalProperties: false,
		},
		output: {
			type: "object",
			properties: { comment: { type: "string", description: "The new comment's name." } },
			required: ["comment"],
		},
	},
} satisfies Record<string, ActText>;
