import { computed, onBeforeUnmount, provide, ref, watch } from "vue"

// Both chat shells float the composer over the list, which pads by its height.
export function provideComposerHeight(composer) {
	const height = ref(120)
	provide("composerHeight", height)
	// how far above the list's foot the box sits: a wide new chat holds it under the mark
	provide("composerLift", ref(0))
	// what is being typed, for the new chat's mark to read
	provide("composerDraft", computed(() => composer.value?.text ?? ""))
	let observer
	watch(
		() => composer.value?.$el,
		(el) => {
			observer?.disconnect()
			if (!el || typeof ResizeObserver === "undefined") return
			const measure = () => (height.value = el.offsetHeight)
			measure()
			observer = new ResizeObserver(measure)
			observer.observe(el)
		},
	)
	onBeforeUnmount(() => observer?.disconnect())
}
