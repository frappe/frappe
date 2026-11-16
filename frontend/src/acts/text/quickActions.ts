import type { ActText } from "./types";

export default {
	email: {
		description: "Open the email composer on this record's timeline. The person writes and sends the email.",
	},
	comment: {
		description: "Open the comment composer on this record's timeline. The person writes and posts the comment.",
	},
	attach: {
		description: "Open the upload dialog to attach files to this record. The person picks the files; an agent cannot.",
	},
	print: {
		description: "Open the print view of this record in a new browser tab.",
	},
	copy_link: {
		description: "Copy this record's link to the clipboard and show a toast. Use it only when the person asks for the link.",
	},
	follow: {
		description: "Follow the record to get its notifications, or stop following it.",
	},
} satisfies Record<string, ActText>;
