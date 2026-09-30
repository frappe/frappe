// A DocType change marks its meta, form layouts and list settings stale; open pages keep theirs.
import type { RealtimeSocket } from "@framework/ui/socket";
import { markDoctypeMetaStale } from "@framework/ui/composables/useDoctypeMeta";
import { markFormLayoutsStale } from "@/recordPage/formLayoutSource/useFormLayout";
import { markListSettingsStale } from "@/list/useListSettings";

const DOCTYPE_UPDATE = "doctype_update";

/** The next page of a changed DocType shows the stale memos and fetches fresh ones; returns the stop. */
export function watchDoctypeUpdates(socket: RealtimeSocket | undefined): () => void {
	const onUpdate = (...args: unknown[]) => {
		const { doctype } = (args[0] ?? {}) as { doctype?: unknown };
		if (typeof doctype !== "string" || !doctype) return;
		markDoctypeMetaStale(doctype);
		markFormLayoutsStale(doctype);
		markListSettingsStale(doctype);
	};
	socket?.on(DOCTYPE_UPDATE, onUpdate);
	return () => socket?.off(DOCTYPE_UPDATE, onUpdate);
}
