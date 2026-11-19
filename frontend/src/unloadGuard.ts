import { onMounted, onUnmounted } from "vue";

/** The browser asks before a reload or a tab close while `unsaved` is true. */
export function useUnloadGuard(unsaved: () => boolean) {
	function onBeforeUnload(event: BeforeUnloadEvent) {
		if (unsaved()) event.preventDefault();
	}

	onMounted(() => window.addEventListener("beforeunload", onBeforeUnload));
	onUnmounted(() => window.removeEventListener("beforeunload", onBeforeUnload));
}
