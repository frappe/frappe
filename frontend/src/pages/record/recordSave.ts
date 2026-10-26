// A record page's save from the header and from Ctrl/Cmd+S, and the browser's question before
// a reload or a tab close loses unsaved changes.
import { onMounted, onUnmounted } from "vue";
import { toast } from "frappe-ui";
import { errorMessage, type RecordPageApi } from "@/recordPage";
import { shownInDialog } from "./saveResponse";

/** Not through an action runner: a failed save keeps the draft on screen and toasts, unless a dialog showed it. */
export async function runSave(page: RecordPageApi | undefined) {
	try {
		await page?.save();
	} catch (exception) {
		if (!shownInDialog(exception)) toast.error(errorMessage(exception));
	}
}

/** Ctrl/Cmd+S calls `save` once per press, only from inside `dialog` when one is given, else never from a dialog or a dropdown; a reload or a tab close asks while `unsaved` is true. */
export function useSaveKeys(options: {
	save: () => void;
	unsaved: () => boolean;
	dialog?: () => Element | null | undefined;
}) {
	function onKeydown(event: KeyboardEvent) {
		if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "s") return;
		event.preventDefault();
		if (event.repeat || overlayOf(event.target) !== (options.dialog?.() ?? null)) return;
		options.save();
	}

	function onBeforeUnload(event: BeforeUnloadEvent) {
		if (options.unsaved()) event.preventDefault();
	}

	onMounted(() => {
		window.addEventListener("keydown", onKeydown);
		window.addEventListener("beforeunload", onBeforeUnload);
	});
	onUnmounted(() => {
		window.removeEventListener("keydown", onKeydown);
		window.removeEventListener("beforeunload", onBeforeUnload);
	});
}

/** A dropdown that frappe-ui portals to `<body>` from inside a dialog is not inside that dialog. */
function overlayOf(target: EventTarget | null): Element | null {
	return target instanceof Element ? target.closest('[role="dialog"],[role="listbox"],[role="menu"]') : null;
}
