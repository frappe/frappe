// The `+` menu: the `create` of every tab on the strip, in strip order. Each runs as the act `tabs.<name>`.
import type { RecordPageController } from "@/recordPage";
import type { TabItem } from "@/recordPage/types";

export interface CreateOption {
	label: string;
	icon: string;
	onClick: () => void;
}

export function createOptions(tabs: TabItem[], controller: RecordPageController): CreateOption[] {
	return tabs.flatMap(({ create }) =>
		create
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
