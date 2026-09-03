// Whether a container holds an icon slot open on the rows that have no icon.
//
// Decided once for a whole container, so a list where only some rows carry an icon still
// reads as one list.

import { computed, type ComputedRef, type MaybeRefOrGetter, toValue } from "vue";
import type { NavigationItem } from "@/boot";
import { renderingOf } from "./registry";
import type { ItemContext } from "./types";

/** True when any row that would draw an icon has one. */
export function useIconSlot(
	items: MaybeRefOrGetter<NavigationItem[]>,
	context: MaybeRefOrGetter<ItemContext>
): ComputedRef<boolean> {
	return computed(() =>
		toValue(items).some((item) => item.icon && drawsIcon(item, toValue(context)))
	);
}

// Asked of the renderer rather than of `item_type`: a heading is whatever resolves to no
// destination, which is `NavigationRow`'s own rule and not a list of kinds.
function drawsIcon(item: NavigationItem, context: ItemContext): boolean {
	const rendering = renderingOf(item, context);
	return !!rendering && !("group" in rendering);
}
