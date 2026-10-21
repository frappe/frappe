import { onMounted, onUnmounted } from "vue"
import { useRouter } from "vue-router"

export function useCanvasNavigationGuard(canvasContainer: { value: HTMLElement | null }) {
	/** Cancel navigation if it was triggered by an interaction inside the canvas eg: clicking on a router-link, sidebar item, etc. */
	const router = useRouter()
	let removeNavigationGuard: (() => void) | null = null
	let isCanvasInteraction = false
	const resetCanvasInteraction = () => {
		setTimeout(() => { isCanvasInteraction = false }, 0)
	}

	onMounted(() => {
		const canvasContainerEl = canvasContainer.value as HTMLElement

		// Track whether a mousedown originated inside the canvas.
		// we use mousedown (which precedes click) to set the flag and reset it on mouseup
		canvasContainerEl.addEventListener("mousedown", () => {
			isCanvasInteraction = true
		}, true)

		// on the document, so a press released outside the canvas (e.g. onto a context menu) still resets the flag
		document.addEventListener("mouseup", resetCanvasInteraction, true)

		removeNavigationGuard = router.beforeEach((to, from) => {
			if (to.fullPath === from.fullPath) return true
			if (isCanvasInteraction) return false
			return true
		})
	})

	onUnmounted(() => {
		document.removeEventListener("mouseup", resetCanvasInteraction, true)
		removeNavigationGuard?.()
	})
}
