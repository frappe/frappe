import { inject, onMounted, onBeforeUnmount } from "vue"

import { fetchApp } from "@/utils/helpers"
import useStudioStore from "@/stores/studioStore"
import useComponentStore from "@/stores/componentStore"

// Keep the open editor in sync with changes made outside it. Three sources, two transports:
//   - page/app/component JSON synced from disk -> backend socket (studio_doc_update)
//   - custom .vue components hot-reloaded by Vite (dev only)
// Call once at the editor root (App.vue). Sibling of useLivePreview, which does this for the render.
export function useLiveEditor() {
	const store = useStudioStore()
	const socket = inject<any>("socket")

	// 1. JSON changed on disk and was synced to the DB. Only external (disk) edits refresh the
	// editor — its own saves are already live on the canvas, and rebuilding would drop selection.
	async function onDiskSync({ doctype, name, studio_app, source }: DiskSyncInfo) {
		if (source !== "disk") return

		// components are global (no app scope), so react regardless of which app is open. Re-fetching
		// the definition re-renders its instances reactively — no page rebuild needed.
		if (doctype === "Studio Component") {
			await useComponentStore().reloadComponent(name)
			return
		}

		if (studio_app !== store.activeApp?.name) return

		if (doctype === "Studio App") {
			const app = await fetchApp(studio_app)
			if (app) store.activeApp = app
		} else if (doctype === "Studio Page") {
			await store.setAppPages(studio_app)
			// rebuild the open page's canvas from the synced blocks if it's the one that changed
			if (name === store.selectedPage) await store.setPage(name)
		}
	}

	// 2. A custom .vue component was added/removed/renamed in a studio folder (Vite emits this in
	// dev; content edits hot-reload on their own). Reload the app's component set.
	const onCustomComponentsChanged = () => store.loadCustomVueComponents()

	onMounted(() => {
		socket?.on("studio_doc_update", onDiskSync)
		import.meta.hot?.on("studio:custom-components-changed", onCustomComponentsChanged)
	})
	onBeforeUnmount(() => {
		socket?.off("studio_doc_update", onDiskSync)
		import.meta.hot?.off("studio:custom-components-changed", onCustomComponentsChanged)
	})
}

// payload of the studio_doc_update realtime event (studio/realtime.py)
type DiskSyncInfo = { doctype: string; name: string; studio_app: string; source: string }
