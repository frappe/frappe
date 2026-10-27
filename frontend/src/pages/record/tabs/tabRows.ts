// The palette's "Go to tab" rows: one per tab on the strip, moving the reader as `page.tabs.activate` does.
import { __ } from "@/i18n";
import type { RecordPageController } from "@/recordPage";
import { registerPageRows } from "@/shell/palette";

/** Registers the rows; the returned function takes them off again. */
export function registerTabRows({ tabs, page }: RecordPageController): () => void {
	return registerPageRows(() =>
		tabs.visible().map((tab) => ({
			id: `tab:${tab.name}`,
			label: __("Go to tab: {0}", [tab.label]),
			icon: tab.icon,
			run: () => page.tabs.activate(tab.name),
		}))
	);
}
