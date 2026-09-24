// The `+` menu: the `create` of every tab on the strip, in strip order.
import { errorMessage, type RecordPageController } from "@/recordPage";
import type { TabCreateAction, TabItem } from "@/recordPage/types";

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
						onClick: () => void run(create, controller),
					},
			  ]
			: []
	);
}

async function run(create: TabCreateAction, controller: RecordPageController) {
	const { page } = controller;
	try {
		await controller.hold(() => create.run(page));
	} catch (error) {
		page.toast.error(errorMessage(error));
	}
}
