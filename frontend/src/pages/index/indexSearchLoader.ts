// Loads the index's search on the first keystroke, so `/apps` pays for none of the palette's code.
import { effectScope, inject, ref, shallowRef, watch, type Ref } from "vue";
import { useRouter } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import type { IndexSearch } from "./indexSearch";

/**
 * The palette's rows for `query`, once something is typed and the chunk is in (`null` before),
 * and whether the last try to load the chunk failed.
 */
export function useIndexSearch(query: Ref<string>, boot: Boot) {
	const search = shallowRef<IndexSearch | null>(null);
	const failed = ref(false);
	const scope = effectScope();
	const context = { boot, router: useRouter(), addresses: inject<Addresses>("addresses")! };
	let loading = false;
	// A failed load is tried again on the next keystroke.
	watch(query, async (typed) => {
		if (!typed.trim() || search.value || loading) return;
		loading = true;
		failed.value = false;
		try {
			const { indexSearch } = await import("./indexSearch");
			if (scope.active) search.value = scope.run(() => indexSearch(query, context))!;
		} catch (error) {
			console.error("[frappe] the index could not load its search", error);
			failed.value = true;
		} finally {
			loading = false;
		}
	});
	return { search, failed };
}
