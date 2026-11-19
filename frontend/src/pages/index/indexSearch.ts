// The palette's rows for what the index's box holds, drawn under the tiles. Its own chunk,
// loaded on the first keystroke, so `/apps` costs nothing more until someone types.
import { computed, onScopeDispose, ref, watch, type Ref } from "vue";
import type { PaletteRow } from "@/shell/palette";
import { askFlow } from "@/shell/paletteFlow";
import {
	PaletteSearch,
	desk,
	type DrawnGroup,
	type PaletteContext,
	type PaletteSource,
} from "@/shell/paletteGroups";
import { create, goToPlaces } from "@/shell/palettePlaces";
import { records } from "@/shell/paletteRecords";
import type { SelectionSection } from "./selection";

// No Recent or This page: the index draws its own Recent, and no page acts here.
const INDEX_SOURCE: PaletteSource = {
	groups: [desk, goToPlaces, create, records],
	pinned: [askFlow],
};

export type IndexSearch = ReturnType<typeof indexSearch>;

/** The rows for `query` and their selection sections; it follows `query` until its effect scope stops. */
export function indexSearch(query: Ref<string>, context: PaletteContext) {
	const search = new PaletteSearch(context, INDEX_SOURCE);
	const settled = ref(false);
	// Each keystroke, as each palette open: a held reply costs no request, a failed one is asked again.
	watch(
		query,
		(text) => {
			search.follow(text);
			search.load().then(() => (settled.value = true));
		},
		{ immediate: true }
	);
	onScopeDispose(() => search.follow(""));

	// Ask Flow is offered for any text, so it is no match: "No results" still shows above it.
	const found = computed<DrawnGroup[]>(() => search.groups(query.value));
	const groups = computed<DrawnGroup[]>(() => {
		const pinned = search.pinned(query.value);
		return [...found.value, ...(pinned.length ? [{ label: "", rows: pinned }] : [])];
	});
	const sections = computed<SelectionSection[]>(() =>
		groups.value.map((group) => ({
			items: group.rows.filter(pickable).map((row) => ({ key: resultKey(row), run: row.run })),
			columns: 1,
		}))
	);
	return { groups, found, sections, settled };
}

export function resultKey(row: PaletteRow): string {
	return `result:${row.id}`;
}

/** "Searching…" and a failed search are drawn, never picked. */
export function pickable(row: PaletteRow): boolean {
	return !row.pending && !row.disabled;
}
