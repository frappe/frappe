import { onMounted, onUnmounted } from "vue"
import { useRouter } from "vue-router"

export function useCanvasNavigationGuard(canvasContainer: { value: HTMLElement | null }) {
	/** Cancel navigation if it was triggered by an interaction inside the canvas eg: clicking on a router-link, sidebar item, etc. */
	const router = useRouter()
	let removeNavigationGuard: (() => void) | null = null
	let isCanvasInteraction = false

	onMounted(() => {
		const canvasContainerEl = canvasContainer.value as HTMLElement

		// Track whether a mousedown originated inside the canvas.
		// we use mousedown (which precedes click) to set the flag and reset it on mouseup
		canvasContainerEl.addEventListener("mousedown", () => {
			isCanvasInteraction = true
		}, true)

		canvasContainerEl.addEventListener("mouseup", () => {
			setTimeout(() => { isCanvasInteraction = false }, 0)
		}, true)

		removeNavigationGuard = router.beforeEach((to, from) => {
			if (to.fullPath === from.fullPath) return true
			if (isCanvasInteraction) return false
			return true
		})
	})

	onUnmounted(() => {
		removeNavigationGuard?.()
	})
}
