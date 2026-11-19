// Where a scroller sits, for the edge fades and the jump button.
import { ref, watch, type Ref } from "vue";
import { useEventListener, useResizeObserver } from "@vueuse/core";

const EDGE = 1;

export function useScrollEdges(scroller: Ref<HTMLElement | null>) {
	const atTop = ref(true);
	const atBottom = ref(true);
	const overflowing = ref(false);
	const pastHalf = ref(false);

	function measure() {
		const element = scroller.value;
		if (!element) return;
		const scrollable = element.scrollHeight - element.clientHeight;
		overflowing.value = scrollable > EDGE;
		atTop.value = element.scrollTop <= EDGE;
		atBottom.value = element.scrollTop >= scrollable - EDGE;
		pastHalf.value = element.scrollTop > scrollable / 2;
	}

	useEventListener(scroller, "scroll", measure);
	useResizeObserver(scroller, measure);
	watch(scroller, measure, { flush: "post" });

	return { atTop, atBottom, overflowing, pastHalf, measure };
}
