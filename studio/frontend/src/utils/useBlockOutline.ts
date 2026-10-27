import { nextTick, ref } from "vue"
import { useEventListener } from "@vueuse/core"

/**
 * The ring a variants pill draws over the option its hovered row renders. The element is read
 * through a getter on every measure, so a row that swaps its option re-measures without being
 * pointed at the new element. `follow` keeps the ring on the element while the viewport scrolls
 * or resizes — the live page moves under it, while the editor canvas moves with its own
 * transform and re-measures on demand instead.
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
		// a pick swaps the option in the same tick; measure once the new element is there
		nextTick(measure)
	}

	if (follow) {
		useEventListener(window, "resize", measure)
		useEventListener(window, "scroll", measure, { capture: true, passive: true })
	}

	return { rect, outline, measure }
}
