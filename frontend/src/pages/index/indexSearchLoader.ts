// Loads the index's search on the first keystroke, so `/apps` pays for none of the palette's code.
import { effectScope, inject, shallowRef, watch, type Ref } from "vue";
import { useRouter } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import type { IndexSearch } from "./indexSearch";

/** The palette's rows for `query`, once something is typed and the chunk is in; `null` before. */
export function useIndexSearch(query: Ref<string>, boot: Boot): Ref<IndexSearch | null> {
	const search = shallowRef<IndexSearch | null>(null);
	const scope = effectScope();
	const context = { boot, router: useRouter(), addresses: inject<Addresses>("addresses")! };
	const stop = watch(query, async (typed) => {
		if (!typed.trim()) return;
		stop();
		const { indexSearch } = await import("./indexSearch");
		if (scope.active) search.value = scope.run(() => indexSearch(query, context))!;
	});
	return search;
}
