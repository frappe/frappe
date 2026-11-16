// The `dialog` surface: what a caller does to the form dialog in front. `confirm` and `danger` have none.
import type { ActEntry, ActItem } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { frontHandle } from "./dialogs/readableDialogs";

const hasHandle = () => !!frontHandle();

export function dialogEntries(): ActEntry[] {
	const items: ActItem[] = [
		{
			name: "set_values",
			label: __("Fill dialog"),
			palette: false,
			when: hasHandle,
			run: (_context, value: { values?: Record<string, any> }) => frontHandle()?.setValues(value?.values ?? {}),
		},
		{ name: "submit", label: __("Submit dialog"), palette: false, when: hasHandle, run: () => frontHandle()?.submit() },
		{ name: "close", label: __("Close dialog"), palette: false, when: hasHandle, run: () => frontHandle()?.close() },
	];
	return items.map((item) => ({ item, hidden: false }));
}
