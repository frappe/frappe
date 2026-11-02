// Ported from Builder - modified to support multiple targets per host (slot overlays)
import { useElementBounding } from "@vueuse/core"
import { effectScope, getCurrentScope, nextTick, onScopeDispose, reactive, watch, watchEffect } from "vue"
import { numberToPx } from "./helpers"
import type { CanvasProps } from "@/types/StudioCanvas"

export interface Tracker {
	update: () => void
	cleanup: () => void
}

type Target = HTMLElement | SVGElement

// All tracked targets share one MutationObserver on the canvas container. It is
// created when the first target registers and disconnected once the last one is
// removed, so it survives individual ComponentEditor remounts (a component-scoped
// observer would die with whichever editor happened to create it) without leaking
// stale updaters across the session.
const updateList = new Set<() => void>()
let observer: MutationObserver | null = null

function trackTarget(target: Target | Target[], host: HTMLElement, canvasProps: CanvasProps): Tracker {
	const targets = Array.isArray(target) ? target : [target]
	// detached scope so trackers created outside component context (slot overlays
	// built in nextTick) still dispose their watchers and listeners on cleanup
	const scope = effectScope(true)
	const boundsList = scope.run(() => targets.map((el) => reactive(useElementBounding(el))))!
	const update = () => boundsList.forEach((bounds) => bounds.update())

	updateList.add(update)
	const container = targets[0]?.closest(".canvas-container") as HTMLElement | null
	if (container && !observer) {
		startObserver(container)
	}

	scope.run(() => {
		watch(canvasProps, () => nextTick(update), { deep: true })

		watchEffect(() => {
			// span the union bounding box so a slot with multiple top-level blocks is fully covered
			const top = Math.min(...boundsList.map((bounds) => bounds.top))
			const left = Math.min(...boundsList.map((bounds) => bounds.left))
			const right = Math.max(...boundsList.map((bounds) => bounds.right))
			const bottom = Math.max(...boundsList.map((bounds) => bounds.bottom))
			host.style.width = numberToPx(right - left, false)
			host.style.height = numberToPx(bottom - top, false)
			host.style.top = numberToPx(top, false)
			host.style.left = numberToPx(left, false)
		})
	})

	const cleanup = () => {
		updateList.delete(update)
		scope.stop()
		if (updateList.size === 0 && observer) {
			observer.disconnect()
			observer = null
		}
	}

	// auto-cleanup with the owning component; explicit cleanup() stays for
	// trackers whose targets change while the component lives (slot overlays)
	if (getCurrentScope()) {
		onScopeDispose(cleanup)
	}

	return {
		update,
		cleanup,
	}
}

function startObserver(container: HTMLElement) {
	observer = new MutationObserver(() => {
		nextTick(() => updateList.forEach((fn) => fn()))
	})
	observer.observe(container, {
		attributes: true,
		childList: true,
		subtree: true,
		attributeFilter: ["style", "class"],
		characterData: true,
	})
}

export default trackTarget
