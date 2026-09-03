// Whether a container holds an icon slot open on rows without one; decided once per container.

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

// Asked of the renderer: a heading is whatever resolves to no destination.
function drawsIcon(item: NavigationItem, context: ItemContext): boolean {
	const rendering = renderingOf(item, context);
	return !!rendering && !("group" in rendering);
}
