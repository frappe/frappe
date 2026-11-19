// Mod+K opens the palette on every page; the rich-text editor keeps its own Mod+K.
import { defineComponent } from "vue";
import { useKeyboardShortcut } from "frappe-ui";
import { __ } from "@/i18n";
import { openPalette } from "./palette";

/** Binds Mod+K while mounted. */
export const PaletteKey = defineComponent({
	name: "PaletteKey",
	setup() {
		useKeyboardShortcut({
			combo: "Mod+K",
			description: __("Search or run an action"),
			allowInInput: true,
			allowInDialog: true,
			preventDefault: false,
			handler: (event) => {
				if ((event.target as Element | null)?.closest?.(".ProseMirror")) return;
				event.preventDefault();
				openPalette();
			},
		});
		return () => null;
	},
});
