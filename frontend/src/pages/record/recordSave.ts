// A record page's save from the header, the settings dialog's Ctrl/Cmd+S, and the browser's
// question before a reload or a tab close loses unsaved changes.
import { onMounted, onUnmounted } from "vue";
import { toast } from "frappe-ui";
import { errorMessage, type RecordPageApi } from "@/recordPage";
import { overlayOf } from "@/shell/actKeys";
import { shownInDialog } from "./saveResponse";

/** Not through an action runner: a failed save keeps the draft on screen and toasts, unless a dialog showed it. */
export async function runSave(page: RecordPageApi | undefined) {
	try {
		await page?.save();
	} catch (exception) {
		if (!shownInDialog(exception)) toast.error(errorMessage(exception));
	}
}

/** Ctrl/Cmd+S from inside `dialog` calls `save` once per press; a reload or a tab close asks while `unsaved` is true. */
export function useSaveKeys(options: {
	save: () => void;
	unsaved: () => boolean;
	dialog: () => Element | null | undefined;
}) {
	function onKeydown(event: KeyboardEvent) {
		if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "s") return;
		event.preventDefault();
		if (event.repeat || overlayOf(event.target) !== (options.dialog() ?? null)) return;
		options.save();
	}

	useUnloadGuard(options.unsaved);
	onMounted(() => window.addEventListener("keydown", onKeydown));
	onUnmounted(() => window.removeEventListener("keydown", onKeydown));
}

/** The browser asks before a reload or a tab close while `unsaved` is true. */
export function useUnloadGuard(unsaved: () => boolean) {
	function onBeforeUnload(event: BeforeUnloadEvent) {
		if (unsaved()) event.preventDefault();
	}

	onMounted(() => window.addEventListener("beforeunload", onBeforeUnload));
	onUnmounted(() => window.removeEventListener("beforeunload", onBeforeUnload));
}
