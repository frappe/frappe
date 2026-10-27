import { nextTick, ref } from "vue"
import { useEventListener } from "@vueuse/core"

/**
 * A viewport rect for an element, to draw an outline over it. The element comes from a getter
 * re-read on every measure, so a caller whose target is replaced never has to hand over the new
 * element. `follow` tracks scroll and resize, for a target that moves with the page; a target
 * inside its own transformed surface re-measures on demand instead.
 */
export function useBlockOutline(follow = false) {
	const rect = ref<DOMRect | null>(null)
	let getElement: (() => Element | null) | null = null

	function measure() {
		rect.value = getElement?.()?.getBoundingClientRect() ?? null
	}

	function outline(element: (() => Element | null) | null) {
		getElement = element
		if (!element) {
			rect.value = null
			return
		}
		// the target can be replaced in this same tick; measure once the new one is in the DOM
		nextTick(measure)
	}

	if (follow) {
		useEventListener(window, "resize", measure)
		useEventListener(window, "scroll", measure, { capture: true, passive: true })
	}

	return { rect, outline, measure }
}
