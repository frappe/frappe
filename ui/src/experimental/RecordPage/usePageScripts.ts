import { onScopeDispose } from "vue";
import { getSocketInstance } from "../../socket";
import { loadPageScripts, reloadPageScripts } from "./pageScripts";
import { PAGE_SCRIPT_CHANGED } from "./pageScriptTypes";

export interface UsePageScripts {
	/** Resolves once the tier has registered; the first replay waits on it. */
	ready: Promise<void>;
}

/**
 * Loads a Record page's Page Script tier and keeps it live: a script saved or
 * deleted anywhere re-fetches the tier and replays it, so the editor's
 * save-and-walk-back loop needs no reload.
 */
export function usePageScripts(
	doctype: string,
	options: { onChange: () => void },
): UsePageScripts {
	const ready = loadPageScripts(doctype);
	const socket = getSocketInstance();

	if (socket) {
		socket.on(PAGE_SCRIPT_CHANGED, onScriptChanged);
		onScopeDispose(() => socket.off(PAGE_SCRIPT_CHANGED, onScriptChanged));
	}

	async function onScriptChanged(...args: unknown[]) {
		const payload = args[0] as { dt?: string; view?: string } | undefined;
		if (payload?.dt !== doctype || payload?.view !== "Record") return;
		await reloadPageScripts(doctype);
		options.onChange();
	}

	return { ready };
}
