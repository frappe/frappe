import { onBeforeUnmount, provide, ref, watch } from "vue"

// Both chat shells float the composer over the list, which pads by its height.
export function provideComposerHeight(composer) {
	const height = ref(120)
	provide("composerHeight", height)
	let observer
	watch(() => composer.value?.$el, (el) => {
		observer?.disconnect()
		if (!el || typeof ResizeObserver === "undefined") return
		const measure = () => (height.value = el.offsetHeight)
		measure()
		observer = new ResizeObserver(measure)
		observer.observe(el)
	})
	onBeforeUnmount(() => observer?.disconnect())
}
