// A list row's actions from `page.rowActions`: each is an act `row_<name>` on the renderer's surface,
// and the row's menu draws the ones that pass the act's right and the item's own `when`.
import type { ActEntry } from "@/acts/dispatcher";
import type { ListPageApi, ListRow, ListRowAction } from "@/listPage/types";
import type { ListActs } from "./listActs";

export interface RowMenuOption {
	label: string;
	icon?: string;
	onClick: () => void;
}

export function rowActionEntries(actions: ListRowAction[]): ActEntry[] {
	return actions.map((action) => ({
		item: {
			name: itemName(action),
			label: action.label ?? action.name,
			icon: action.icon,
			right: action.right,
			palette: false,
			run: (page: ListPageApi, row: ListRow) => action.run(page, row),
		},
		hidden: false,
	}));
}

/** The menu for one row: the actions drawn now whose `when` holds for it. */
export function rowMenuOptions(row: ListRow, actions: ListRowAction[], listActs: ListActs): RowMenuOption[] {
	return actions.flatMap((action) => {
		const drawn = listActs.drawn(itemName(action));
		if (!drawn || !applies(action, row, listActs.context())) return [];
		return [{ label: drawn.label!, icon: drawn.icon, onClick: () => listActs.perform(drawn, row) }];
	});
}

function itemName(action: ListRowAction) {
	return `row_${action.name}`;
}

// A `when` that throws on a row hides the action there; it must not break the list's render.
function applies(action: ListRowAction, row: ListRow, page: ListPageApi) {
	try {
		return action.when?.(page, row) !== false;
	} catch {
		return false;
	}
}
