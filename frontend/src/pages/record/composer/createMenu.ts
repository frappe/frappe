// The `+` menu: the `create` of every tab on the strip whose right passes, in strip order. Each runs as the act `tabs.<name>`.
import type { RecordPageController } from "@/recordPage";
import type { TabCreateAction, TabItem } from "@/recordPage/types";

export interface CreateOption {
	label: string;
	icon: string;
	onClick: () => void;
}

export function createOptions(tabs: TabItem[], controller: RecordPageController): CreateOption[] {
	return tabs.flatMap(({ name, create }) =>
		create && named(name, create) && controller.allows(create)
			? [
					{
						label: create.label,
						icon: create.icon,
						onClick: () => void controller.perform(`tabs.${create.name}`),
					},
			  ]
			: []
	);
}

const warnedTabs = new Set<string>();

// The dispatcher finds an entry only by its name, so one with none would run nothing.
function named(tab: string, create: TabCreateAction) {
	if (create.name) return true;
	if (import.meta.env.DEV && !warnedTabs.has(tab)) {
		warnedTabs.add(tab);
		console.warn(`[record-page] tab '${tab}': its create has no name, so the + menu leaves it out.`);
	}
	return false;
}
