// Tab on a doctype row narrows the palette to that doctype: its records, titled as Records titles them.
import { computed, ref, watch, type Ref } from "vue";
import { __ } from "@/i18n";
import { urlFor } from "@/router/routeFor";
import type { PaletteRow } from "./palette";
import type { PaletteContext } from "./paletteGroups";
import { openPlace } from "./palettePlaces";
import { nameUnlessTitle, RecordSearch } from "./paletteRecords";

const SHORTEST_QUERY = 2;

/** The doctype the palette is narrowed to, and the records the query finds in it. */
export function usePaletteScope(query: Ref<string>, context: PaletteContext) {
	const doctype = ref<string | null>(null);
	const text = computed(() => query.value.trim());
	const search = new RecordSearch("frappe.shell.palette.search_doctype_records");

	watch([text, doctype], () => search.follow(doctype.value ? text.value : "", doctype.value));

	const rows = computed<PaletteRow[]>(() => {
		const narrowed = doctype.value;
		const found = search.found.value;
		if (!narrowed || !asks(text.value) || found === "failed") return [];
		if (found === "searching")
			return [{ id: "searching", label: __("Searching…"), pending: true, run: () => {} }];
		return found.map((record) => {
			const href = urlFor(narrowed, String(record.name));
			return {
				id: `record:${narrowed}/${record.name}`,
				label: String(record.label),
				description: nameUnlessTitle(record),
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
		if (search.found.value === "failed") return __("Could not search {0}", [__(narrowed)]);
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
