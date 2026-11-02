import { onBeforeUnmount, provide, ref, watch } from "vue"

// Both chat shells float the composer over the list, which pads by its height; a new chat's
// start row, over the box, counts too.
export function provideComposerHeight(composer) {
	const height = ref(120)
	provide("composerHeight", height)
	let observer
	watch([() => composer.value?.$el, () => composer.value?.startRow], ([el, row]) => {
		observer?.disconnect()
		if (!el || typeof ResizeObserver === "undefined") return
		const measure = () =>
			(height.value = row ? Math.round(el.getBoundingClientRect().bottom - row.getBoundingClientRect().top) : el.offsetHeight)
		measure()
		observer = new ResizeObserver(measure)
		observer.observe(el)
		if (row) observer.observe(row)
	})
	onBeforeUnmount(() => observer?.disconnect())
}
