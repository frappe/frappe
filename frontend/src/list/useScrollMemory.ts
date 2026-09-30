// The list's scroll offset, kept in the history entry and in the session's memory for the
// query, and put back once the rows are there. Back reads the entry; a breadcrumb has none and
// reads the session.
import { watch } from "vue";
import { landScroll, onScrollSettled } from "@framework/ui/utils/scrollLanding";
import { readListMemory, recallRows, rememberScroll, writeListMemory } from "./pageState";

export interface ScrollSession {
	doctype: string;
	/** The filters and sort as one string, the rows memory's key. */
	query: () => string;
}

export function useScrollMemory(
	viewport: () => HTMLElement | null,
	ready: () => boolean,
	session: ScrollSession
): void {
	let restored = false;
	let landing = false;

	watch(viewport, (element, _previous, onCleanup) => {
		if (!element) return;
		const remember = () => {
			if (landing) return;
			writeListMemory({ scrollTop: element.scrollTop });
			rememberScroll(session.doctype, session.query(), element.scrollTop);
		};
		onCleanup(onScrollSettled(element, remember));
	});

	// Virtual rows grow the scroll height over a few frames; the clamped scrolls on the way are not remembered.
	watch([viewport, ready], ([element, rowsLanded]) => {
		if (restored || !element || !rowsLanded) return;
		restored = true;
		const top =
			readListMemory().scrollTop ?? recallRows(session.doctype, session.query())?.scrollTop;
		if (!top) return;
		landing = true;
		void landScroll(element, top).then(() => (landing = false));
	});
}
