import { inject, onMounted, onBeforeUnmount } from "vue"

import { fetchApp } from "@/utils/helpers"
import useStudioStore from "@/stores/studioStore"
import useComponentStore from "@/stores/componentStore"

// Refresh the open editor when its app changes on disk (studio_doc_update from studio/realtime.py).
// Call once at the editor root (App.vue). Only external (disk) edits refresh the editor — its own
// saves are already live on the canvas, and rebuilding from them would drop selection/undo.
export function useDiskSync() {
	const socket = inject<any>("socket")
	const store = useStudioStore()

	async function sync({ doctype, name, studio_app, source }: { doctype: string; name: string; studio_app: string; source: string }) {
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

	onMounted(() => socket?.on("studio_doc_update", sync))
	onBeforeUnmount(() => socket?.off("studio_doc_update", sync))
}