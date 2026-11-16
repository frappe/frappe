import type { ActText } from "./types";

export default {
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
