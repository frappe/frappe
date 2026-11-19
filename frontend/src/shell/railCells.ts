// The rail's items as flat cells: one per row that can be drawn as a tile. The rail and the phone sheet draw them.
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { NavigationItem } from "@/boot";
import { __ } from "@/i18n";
import { labelOf, renderingOf } from "@/navigation/registry";
import type { ItemNode } from "@/navigation/tree";
import { useItemTree } from "@/navigation/useItemTree";
import type { ItemContext } from "@/navigation/types";
import { isActAvailable } from "./actRow";

export type Cell = { key: string; label: string; icon?: string; sidebar?: string } & (
	| { to: RouteLocationRaw }
	| { href: string; external?: boolean; ariaLabel?: string }
	| { act: string; value?: unknown }
);

export function useRailCells(items: () => NavigationItem[], context: () => ItemContext) {
	const tree = useItemTree(items, "the rail");

	// Depth-first and flat: a heading contributes its children and nothing else.
	const cells = computed(() => {
		const out: Cell[] = [];
		const walk = (nodes: ItemNode[]) => {
			for (const node of nodes) {
				const cell = cellOf(node.item);
				if (cell && !("act" in cell && !isActAvailable(cell.act))) out.push(cell);
				walk(node.children);
			}
		};
		walk(tree.value);
		return out;
	});

	function cellOf(item: NavigationItem): Cell | null {
		const rendering = renderingOf(item, context());
		if (!rendering || !("to" in rendering || "href" in rendering || "act" in rendering))
			return null;

		const cell = { key: item.key, label: labelOf(item, context()), icon: item.icon };
		if ("act" in rendering) return { ...cell, ...rendering };
		return "to" in rendering
			? { ...cell, to: rendering.to, sidebar: rendering.sidebar }
			: {
					...cell,
					href: rendering.href,
					external: rendering.external,
					// Built here, with the label, so it is redone whenever the label is: the cell's `v-memo` sees a new cell.
					ariaLabel: rendering.external
						? __("{0} (opens in a new tab)", [cell.label])
						: undefined,
					sidebar: rendering.sidebar,
			  };
	}

	return cells;
}
