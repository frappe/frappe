// The list's scroll offset, kept in the history entry and in the session's memory for the
// query, and put back once the rows are there. Back reads the entry; a breadcrumb has none and
// reads the session.
import { watch } from "vue";
import { readListMemory, recallRows, rememberScroll, writeListMemory } from "./pageState";

const LANDING_FRAMES = 60;

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
	let frame = 0;

	watch(viewport, (element, _previous, onCleanup) => {
		if (!element) return;
		const remember = () => {
			if (landing) return;
			cancelAnimationFrame(frame);
			frame = requestAnimationFrame(() => {
				writeListMemory({ scrollTop: element.scrollTop });
				rememberScroll(session.doctype, session.query(), element.scrollTop);
			});
		};
		element.addEventListener("scroll", remember, { passive: true });
		onCleanup(() => {
			cancelAnimationFrame(frame);
			element.removeEventListener("scroll", remember);
		});
	});

	watch([viewport, ready], ([element, rowsLanded]) => {
		if (restored || !element || !rowsLanded) return;
		restored = true;
		const top =
			readListMemory().scrollTop ?? recallRows(session.doctype, session.query())?.scrollTop;
		if (top) land(element, top);
	});

	// Virtual rows grow the scroll height over a few frames; the offset lands once it fits, and
	// the clamped scrolls on the way are not remembered.
	function land(element: HTMLElement, top: number) {
		landing = true;
		let frames = LANDING_FRAMES;
		const attempt = () => {
			const fits = element.scrollHeight - element.clientHeight >= top;
			if (!fits && frames-- > 0) return requestAnimationFrame(attempt);
			element.scrollTop = top;
			landing = false;
		};
		attempt();
	}
}
