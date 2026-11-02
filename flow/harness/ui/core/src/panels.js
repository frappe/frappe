import { computed, inject, ref } from "vue"

// Open state of a tool or thought row, kept by the message list so it outlives the row's component.
export function usePanelOpen(id) {
	const panels = inject("openPanels", null)
	if (!panels) return ref(false)
	return computed({
		get: () => panels.has(id()),
		set: (open) => {
			if (open) panels.add(id())
			else panels.delete(id())
		},
	})
}
