import type { ActText } from "./types";

export default {
	attach_file: {
		description: "Open the upload dialog of the Files tab. The person picks the files; an agent cannot.",
	},
} satisfies Record<string, ActText>;
