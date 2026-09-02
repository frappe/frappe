// The tree a container draws, with the cycle report attached.
//
// A composable rather than a call to `buildTree`, because the reporting is what has to be
// shared and it is the part with state in it. `buildTree` stays pure — it is recomputed on
// every render of a reactive list, so a logger inside it would fire per frame — and the
// "once per key" set has to live somewhere that outlives one computation.
//
// One set per instance, which is one set per container. A key identifies a row within ONE
// container (`registry.ts` learned this the hard way, on the depth guard), so a rail and a
// sidebar may each hold a row called `accounts` and a shared set would report the second as
// a repeat of the first and say nothing.

import { computed, type ComputedRef, type MaybeRefOrGetter, toValue } from "vue";
import type { NavigationItem } from "@/boot";
import { buildTree, type ItemNode } from "./tree";

export function useItemTree(
	items: MaybeRefOrGetter<NavigationItem[]>,
	container: MaybeRefOrGetter<string>
): ComputedRef<ItemNode[]> {
	const reported = new Set<string>();

	return computed(() =>
		buildTree(toValue(items), (key) => {
			// A list that is wrong stays wrong, so the line would repeat on every save without
			// saying anything new.
			if (reported.has(key)) return;
			reported.add(key);
			console.error(
				`[frappe] navigation item '${key}' in ${toValue(container)} is its own ancestor; ` +
					`it is drawn at the top level.`
			);
		})
	);
}
