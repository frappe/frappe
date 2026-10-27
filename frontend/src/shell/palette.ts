// The command palette's in-page state, and the rows a page adds to its "This page" group.
// Never in the address: opening the palette adds no history entry.
import { ref, shallowReactive } from "vue";

/** One line in the palette: an act, a place or a record. */
export interface PaletteRow {
	/** Unique in the palette, such as `act:header.save` or `tab:activity`. */
	id: string;
	label: string;
	icon?: string;
	/** Gray text after the label: the doctype for a record, the app for a place or an app act. */
	description?: string;
	/** Words the search also matches, never drawn. */
	keywords?: string[];
	/** The act's key, drawn on the right; the palette does not bind it. */
	key?: string;
	/** A place or record's address; ties in the ranking go to the one opened last. */
	href?: string;
	/** A stand-in while rows load, such as "Searching…": drawn with a spinner, never picked. */
	pending?: boolean;
	/** A note that is not an act, such as a failed search: drawn gray, never picked. */
	disabled?: boolean;
	/** The doctype Tab narrows the search to, on a row that opens its list. */
	doctype?: string;
	run: () => unknown;
}

export const paletteOpen = ref(false);

export function openPalette() {
	paletteOpen.value = true;
}

const pageRowSources = shallowReactive(new Set<() => PaletteRow[]>());

/** A page's own rows for "This page", after its acts; the returned function takes them off. */
export function registerPageRows(source: () => PaletteRow[]): () => void {
	pageRowSources.add(source);
	return () => pageRowSources.delete(source);
}

export function pageRows(): PaletteRow[] {
	return [...pageRowSources].flatMap((source) => source());
}
