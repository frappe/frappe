// How much of an action row fits: how many leading items wear their label, and how many
// stay in the row at all. What is left over belongs in an overflow menu.
import { nextTick, ref, watch, type Ref } from "vue";
import { useResizeObserver } from "@vueuse/core";

// The row must span its container, never shrink-wrap its content: otherwise naming an
// item resizes the row, and the observer refits forever.
export function useFittedActions(
	row: Ref<HTMLElement | null>,
	total: () => number,
	fitting: () => boolean
) {
	const labelled = ref(fitting() ? total() : 0);
	const visible = ref(total());
	let attempt = 0;

	// Labels go first, then whole items, so the row degrades before it hides anything.
	async function fit() {
		const element = row.value;
		if (!element) return;
		const token = ++attempt;
		labelled.value = fitting() ? total() : 0;
		visible.value = total();
		await nextTick();
		if (!fitting()) return;
		await shrink(element, labelled, 1, token);
		await shrink(element, visible, 1, token);
	}

	// Each drop is measured against real layout; nextTick is a microtask, so the browser
	// never paints an oversized row.
	async function shrink(element: HTMLElement, count: Ref<number>, floor: number, token: number) {
		while (token === attempt && count.value > floor && overflowing(element)) {
			count.value--;
			await nextTick();
		}
	}

	useResizeObserver(row, fit);
	// The row is a source: the observer's first measure has no ref to watch at setup.
	watch([row, total, fitting], fit, { flush: "post" });

	return { labelled, visible, fit };
}

function overflowing(element: HTMLElement) {
	return element.scrollWidth > element.clientWidth;
}
