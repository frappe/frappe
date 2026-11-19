// The tree a container draws, with the once-per-key cycle report; `buildTree` stays pure.
// Once per container and key: keys are unique per container, and a panel's container changes.

import { computed, type ComputedRef, type MaybeRefOrGetter, toValue } from "vue";
import type { NavigationItem } from "@/boot";
import { buildTree, type ItemNode } from "./tree";

/**
 * The tree for one container's rows, rebuilt whenever they change. `container` names it in
 * a cycle report: `the rail`, `the <address> sidebar`.
 */
export function useItemTree(
	items: MaybeRefOrGetter<NavigationItem[]>,
	container: MaybeRefOrGetter<string>
): ComputedRef<ItemNode[]> {
	const reported = new Set<string>();

	return computed(() =>
		buildTree(toValue(items), (key) => {
			const id = JSON.stringify([toValue(container), key]);
			if (reported.has(id)) return;
			reported.add(id);
			console.error(
				`[frappe] navigation item '${key}' in ${toValue(container)} is its own ancestor; ` +
					`it is drawn at the top level.`
			);
		})
	);
}
