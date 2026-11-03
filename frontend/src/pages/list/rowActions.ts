// A list row's actions from the apps: each is one item on the `list` surface, named for its act,
// and the row's menu draws the ones that pass the target act's right and the item's own `when`.
import type { ActEntry } from "@/acts/dispatcher";
import { acts } from "@/acts/dispatcher";
import type { RowAction } from "@/contributions/types";
import type { ListActs } from "./listActs";

type Row = Record<string, unknown>;

export interface RowMenuOption {
	label: string;
	icon?: string;
	onClick: () => void;
}

export function rowActionEntries(actions: RowAction[]): ActEntry[] {
	return actions.map((action) => {
		const target = acts.find(action.act);
		return {
			item: {
				name: itemName(action),
				label: action.label ?? target?.label ?? action.act,
				icon: action.icon ?? target?.icon,
				palette: false,
				run: (_context: unknown, row: Row) =>
					acts.perform(action.act, action.value?.(row)),
			},
			hidden: !target,
		};
	});
}

/** The menu for one row: the actions drawn now whose `when` holds for it. */
export function rowMenuOptions(row: Row, actions: RowAction[], listActs: ListActs): RowMenuOption[] {
	return actions.flatMap((action) => {
		const drawn = listActs.drawn(itemName(action));
		if (!drawn || action.when?.(row) === false) return [];
		return [{ label: drawn.label!, icon: drawn.icon, onClick: () => listActs.perform(drawn, row) }];
	});
}

function itemName(action: RowAction) {
	return `row_${action.act}`;
}
