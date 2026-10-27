// Tab on a doctype row narrows the palette to that doctype: its records, from the link search.
import { computed, ref, watch, type Ref } from "vue";
import { useDebounceFn } from "@vueuse/core";
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
	const search = useLinkSearch(() => doctype.value ?? undefined, {}, RECORDS_CAP);
	const pausing = ref(false);

	const searchSoon = useDebounceFn(() => {
		pausing.value = false;
		if (asking()) search.search(text());
	}, PAUSE_MS);

	watch([query, doctype], () => {
		pausing.value = asking();
		if (pausing.value) searchSoon();
	});

	const searching = computed(() => asking() && (pausing.value || search.loading.value));

	const rows = computed<PaletteRow[]>(() => {
		const narrowed = doctype.value;
		if (!narrowed || !asking() || search.error.value) return [];
		if (searching.value)
			return [{ id: "searching", label: __("Searching…"), pending: true, run: () => {} }];
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

	function text() {
		return query.value.trim();
	}

	function asking() {
		return !!doctype.value && text().length >= SHORTEST_QUERY;
	}

	return {
		doctype,
		rows,
		/** What the empty list says while the query is too short to search. */
		prompt: computed(() =>
			doctype.value && !asking() ? __("Type to search {0}", [__(doctype.value)]) : null
		),
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
