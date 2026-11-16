import type { ActSchema } from "../schema/checkValue";
import type { ActText } from "./types";

const type: ActSchema = { type: "string", enum: ["Details", "Side Panel", "Quick Entry", "New Record"], description: "The layout's type." };
const ref: ActSchema = {
	type: "object",
	description: "A layout: its type, and its id when the type has several.",
	properties: { type, id: { type: "string" } },
	required: ["type"],
};
const staged = "The edit is staged, not saved: use editor.save to save.";

export default {
	open: {
		description: "Show another layout of the DocType in the canvas.",
		input: ref,
	},
	add: {
		description: `Add a layout of a type, shown when its condition holds. It opens in the canvas. ${staged}`,
		input: {
			type: "object",
			properties: {
				type,
				title: { type: "string", minLength: 1, description: "The layout's title." },
				condition: { type: "string", description: "The condition under which the layout shows." },
				start: { type: "string", enum: ["copy", "empty"], description: "Start from a copy of the default layout, or empty." },
			},
			required: ["type", "title", "condition", "start"],
			additionalProperties: false,
		},
	},
	rename: {
		description: `Change a layout's title. ${staged}`,
		input: {
			type: "object",
			properties: { layout: ref, title: { type: "string", minLength: 1 } },
			required: ["layout", "title"],
			additionalProperties: false,
		},
	},
	set_condition: {
		description: `Change the condition under which a layout shows. ${staged}`,
		input: {
			type: "object",
			properties: { layout: ref, condition: { type: "string" } },
			required: ["layout", "condition"],
			additionalProperties: false,
		},
	},
	delete: {
		description: `Delete a layout. The default layout of a type cannot be deleted. It asks no delete confirm itself, so use it only when the person asked for it. ${staged}`,
		input: { type: "object", properties: { layout: ref }, required: ["layout"], additionalProperties: false },
	},
	reset_to_app: {
		description: `Customize mode only: put the layouts of a type back to the app's. It asks no delete confirm itself, so use it only when the person asked for it. ${staged}`,
		input: { type: "object", properties: { type }, required: ["type"], additionalProperties: false },
	},
} satisfies Record<string, ActText>;
