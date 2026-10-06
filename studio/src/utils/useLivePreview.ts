import { ref, inject, onMounted, onBeforeUnmount } from "vue"
import { useRouter } from "vue-router"
import { useDebounceFn } from "@vueuse/core"

import { reloadCustomVueComponents } from "@/globals"
import useComponentStore from "@/stores/componentStore"

// Re-render the preview when the open page changes in the DB — an editor save, an AI edit, or a disk
// edit synced by the watcher (studio_doc_update from studio/realtime.py). Returns a revision that
// bumps once the page has been re-prepared, so it remounts; debounced so a burst of autosaves
// coalesces into one reload.
export function useLivePreview() {
	const socket = inject<any>("socket")
	const router = useRouter()
	const revision = ref(0)

	const reloadPage = useDebounceFn(async () => {
		const { path, query, hash } = router.currentRoute.value
		const failure = await router.replace({ path, query, hash, force: true })
		if (!failure) revision.value++
	}, 300)

	const onDocUpdate = (info: any) => {
		if (info?.doctype === "Studio Component") {
			useComponentStore().reloadComponent(info.name)
		} else if (info?.doctype === "Studio Page" && info?.name === router.currentRoute.value.meta.pageName) {
			reloadPage()
		}
	}

	// a custom .vue component was added/removed/renamed in a studio folder (Vite emits this in dev;
	// content edits hot-reload on their own). Re-register so the preview picks it up.
	const onCustomComponentsChanged = () => reloadCustomVueComponents((window as any).frappe_app)

	onMounted(() => {
		socket?.on("studio_doc_update", onDocUpdate)
		import.meta.hot?.on("studio:custom-components-changed", onCustomComponentsChanged)
	})
	onBeforeUnmount(() => {
		socket?.off("studio_doc_update", onDocUpdate)
		import.meta.hot?.off("studio:custom-components-changed", onCustomComponentsChanged)
	})
	return revision
}
