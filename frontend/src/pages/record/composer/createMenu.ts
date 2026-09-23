// The `+` menu: the `create` of every tab on the strip, in strip order.
import { errorMessage } from "@/recordPage";
import type { RecordPageApi, TabCreateAction, TabItem } from "@/recordPage/types";

export interface CreateOption {
	label: string;
	icon: string;
	onClick: () => void;
}

export function createOptions(tabs: TabItem[], page: RecordPageApi): CreateOption[] {
	return tabs.flatMap(({ create }) =>
		create
			? [
					{
						label: create.label,
						icon: create.icon,
						onClick: () => void run(create, page),
					},
			  ]
			: []
	);
}

async function run(create: TabCreateAction, page: RecordPageApi) {
	try {
		await create.run(page);
	} catch (error) {
		page.toast.error(errorMessage(error));
	}
}
