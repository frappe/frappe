import { inject, onMounted, onBeforeUnmount } from "vue"
import { useRouter } from "vue-router"
import { useDebounceFn } from "@vueuse/core"

import { reloadCustomVueComponents } from "@/utils/customVueComponents"
import useComponentStore from "@/stores/componentStore"

// Refresh the preview when the open page changes in the DB — an editor save, an AI edit, or a disk
// edit synced by the watcher (studio_doc_update from studio/realtime.py). Debounced so a burst of
// autosaves coalesces into one refresh.
export function useLivePreview(refreshPage: () => Promise<void>) {
	const socket = inject<any>("socket")
	const router = useRouter()

	const refresh = useDebounceFn(async (pageName: string) => {
		if (router.currentRoute.value.meta.pageName !== pageName) return
		await refreshPage()
	}, 300)

	const onDocUpdate = (info: any) => {
		if (info?.doctype === "Studio Component") {
			useComponentStore().reloadComponent(info.name)
		} else if (info?.doctype === "Studio Page" && info?.name === router.currentRoute.value.meta.pageName) {
			refresh(info.name)
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
}
