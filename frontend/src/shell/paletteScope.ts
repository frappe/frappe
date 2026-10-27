// Tab on a doctype row narrows the palette to that doctype: its records, from the link search.
import { computed, ref, watch, type Ref } from "vue";
import { refDebounced } from "@vueuse/core";
import { useLinkSearch } from "@framework/ui/Link";
import { __ } from "@/i18n";
import { urlFor } from "@/router/routeFor";
import type { PaletteRow } from "./palette";
import type { PaletteContext } from "./paletteGroups";
import { openPlace } from "./palettePlaces";

const SHORTEST_QUERY = 2;
const PAUSE_MS = 200;
const RECORDS_CAP = 10;

/** The doctype the palette is narrowed to, and the records the query finds in it. */
export function usePaletteScope(query: Ref<string>, context: PaletteContext) {
	const doctype = ref<string | null>(null);
	const text = computed(() => query.value.trim());
	const settled = refDebounced(text, PAUSE_MS);
	const search = useLinkSearch(() => doctype.value ?? undefined, {}, RECORDS_CAP);

	watch([settled, doctype], () => {
		if (asks(settled.value)) search.search(settled.value);
	});

	const searching = computed(
		() => asks(text.value) && (settled.value !== text.value || search.loading.value)
	);

	const rows = computed<PaletteRow[]>(() => {
		const narrowed = doctype.value;
		if (!narrowed || !asks(text.value)) return [];
		if (searching.value)
			return [{ id: "searching", label: __("Searching…"), pending: true, run: () => {} }];
		if (search.error.value) return [];
		return (search.data.value ?? []).map((option) => {
			const href = urlFor(narrowed, option.value);
			return {
				id: `record:${narrowed}/${option.value}`,
				label: option.label,
				description: option.label === option.value ? option.description : option.value,
				icon: "lucide-file-text",
				href,
				run: () => openPlace(href, context),
			};
		});
	});

	/** What the empty list says in a scope: the query is too short, or the search failed. */
	const prompt = computed(() => {
		const narrowed = doctype.value;
		if (!narrowed) return null;
		if (!asks(text.value)) return __("Type to search {0}", [__(narrowed)]);
		if (search.error.value && !searching.value) return __("Could not search {0}", [__(narrowed)]);
		return null;
	});

	function asks(typed: string) {
		return !!doctype.value && typed.length >= SHORTEST_QUERY;
	}

	return {
		doctype,
		rows,
		prompt,
		enter(narrowTo: string) {
			doctype.value = narrowTo;
			query.value = "";
		},
		leave() {
			doctype.value = null;
			query.value = "";
		},
	};
}
