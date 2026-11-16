import type { ActText } from "./types";

export default {
	delete_card: {
		description: "Delete one card's record after the person confirms in the Delete dialog. Cannot be undone.",
		input: {
			type: "object",
			description: "The card's row.",
			properties: { name: { type: "string", minLength: 1, description: "The record's name." } },
			required: ["name"],
		},
	},
} satisfies Record<string, ActText>;
