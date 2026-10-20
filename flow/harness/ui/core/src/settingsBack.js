import { computed, inject, onBeforeUnmount, provide, shallowRef, watch } from "vue"

import { layout } from "./layout.js"

// A narrow frame's settings page has one way back, in its header. A section's own sub-page
// (a record's form) lends it its back, so the header leads to the section's list, not to settings.
export function provideSettingsBack() {
	const back = shallowRef(null) // { go }
	provide("settingsBack", back)
	return back
}

// `go` while `active()`; true when the header shows it, so the page leaves out its own button
export function useSettingsBack(active, go) {
	const back = inject("settingsBack", null)
	if (!back) return computed(() => false)
	const own = { go }
	const release = () => back.value === own && (back.value = null)
	watch(active, (on) => (on ? (back.value = own) : release()), { immediate: true })
	onBeforeUnmount(release)
	return computed(() => layout.narrow && back.value === own)
}
