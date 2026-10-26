import { computed, inject, onBeforeUnmount, provide, shallowRef, watch } from "vue"

// A narrow frame's settings page has one way back, in its header. A section's own sub-page
// (a record's form) lends it its back, so the header leads to the section's list, not to settings.
// `narrow`: a ref, true while the shell is that page
export function provideSettingsBack(narrow) {
	const back = shallowRef(null) // { go }
	provide("settingsBack", { back, narrow })
	return back
}

// `go` while `active()`; true when the header shows it, so the page leaves out its own button
export function useSettingsBack(active, go) {
	const shell = inject("settingsBack", null)
	if (!shell) return computed(() => false)
	const { back, narrow } = shell
	const own = { go }
	const release = () => back.value === own && (back.value = null)
	watch(active, (on) => (on ? (back.value = own) : release()), { immediate: true })
	onBeforeUnmount(release)
	return computed(() => narrow.value && back.value === own)
}
