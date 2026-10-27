// The command palette's in-page state, and the rows a page adds to its "This page" group.
// Never in the address: opening the palette adds no history entry.
import { ref, shallowReactive } from "vue";

/** One line in the palette: an act, a place or a record. */
export interface PaletteRow {
	/** Unique in the palette, such as `act:header.save` or `tab:activity`. */
	id: string;
	label: string;
	/** Gray text before the label, such as "Ask Flow:". */
	lead?: string;
	icon?: string;
	/** An avatar in place of the icon: the picture's address, or `null` for the label's initials. */
	image?: string | null;
	/** Gray text after the label: the doctype for a record, the app for a place or an app act. */
	description?: string;
	/** Words the search also matches, never drawn. */
	keywords?: string[];
	/** The act's key, drawn on the right; the palette does not bind it. */
	key?: string;
	/** Gray text on the right of a row with no key, such as "New chat in Flow". */
	hint?: string;
	/** A place or record's address; ties in the ranking go to the one opened last. */
	href?: string;
	/** A stand-in while rows load, such as "Searching…": drawn with a spinner, never picked. */
	pending?: boolean;
	/** A note that is not an act, or a choice that cannot be picked: drawn gray, never picked. */
	disabled?: boolean;
	/** The doctype Tab narrows the search to, on a row that opens its list. */
	doctype?: string;
	/** Picking it keeps the palette open, as an act's argument step does. */
	stays?: boolean;
	run: () => unknown;
}

export const paletteOpen = ref(false);

/** The act whose argument step the palette shows, by its full name; `null` on the first step. */
export const paletteArgument = ref<string | null>(null);

export function openPalette() {
	paletteArgument.value = null;
	paletteOpen.value = true;
}

/** Opens the palette at the argument step of the act `name`, or moves an open one there. */
export function openArgumentStep(name: string) {
	paletteArgument.value = name;
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
