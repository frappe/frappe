import { inject, onMounted, onBeforeUnmount, type Ref } from "vue"
import { useDebounceFn } from "@vueuse/core"

import type { StudioPage } from "@/types/Studio/StudioPage"

// Re-render the preview when the open page changes in the DB — an editor save, an AI edit, or a disk
// edit synced by the watcher (studio_doc_update from studio/realtime.py). Debounced so a burst of
// autosaves coalesces into one reload.
export function useLivePreview(page: Ref<StudioPage | null>, reload: () => void) {
	const socket = inject<any>("socket")
	const reloadDebounced = useDebounceFn(reload, 300)

	const onDocUpdate = (info: any) => {
		if (info?.doctype === "Studio Page" && info?.name === page.value?.name) reloadDebounced()
	}

	onMounted(() => socket?.on("studio_doc_update", onDocUpdate))
	onBeforeUnmount(() => socket?.off("studio_doc_update", onDocUpdate))
}
