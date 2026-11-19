// The leading built-ins stay in view above the scrolling sections: their height is where the
// section headers pin, and their line shows while rows pass beneath them.
import { computed, ref, watch, type Ref } from "vue";
import { useElementSize, useEventListener } from "@vueuse/core";
import { rowsUnder } from "./pinnedCover";
import { scrollParent } from "./scrollParent";

export function usePinnedBlock(block: Ref<HTMLElement | null>) {
	const scroller = computed(() => scrollParent(block.value));
	const { height: blockHeight } = useElementSize(block, undefined, { box: "border-box" });
	const { height: columnHeight } = useElementSize(scroller);
	// On a short column the block would leave too little room for the sections to scroll in.
	const pinning = computed(() => blockHeight.value > 0 && blockHeight.value <= columnHeight.value / 2);
	const height = computed(() => (pinning.value ? blockHeight.value : 0));
	const covering = ref(false);

	// A header pinned right below sits on the same layer, later, so it draws over this line.
	function measure() {
		covering.value = pinning.value && !!block.value && rowsUnder(block.value);
	}

	useEventListener(scroller, "scroll", measure, { passive: true });
	watch([scroller, pinning], measure, { flush: "post" });

	return { pinning, height, covering };
}
