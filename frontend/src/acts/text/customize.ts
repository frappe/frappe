import type { ActText } from "./types";

export default {
	reset_all: {
		description: "Customize mode: open the Reset dialog that drops this site's customizations of the DocType. The person confirms in the dialog; the act waits.",
	},
	export: {
		description: "Customize mode: open the Export dialog that writes this site's customizations into an app. The person fills the dialog; the act waits.",
	},
} satisfies Record<string, ActText>;
