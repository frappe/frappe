// A DocType change forgets its meta, form layouts and list settings; open pages keep theirs.
import type { RealtimeSocket } from "@framework/ui/socket";
import { dropDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { dropFormLayouts } from "@/recordPage/formLayoutSource/useFormLayout";
import { dropListSettings } from "@/list/useListSettings";

const DOCTYPE_UPDATE = "doctype_update";

/** The next page of a changed DocType fetches its memos again; returns the stop. */
export function watchDoctypeUpdates(socket: RealtimeSocket | undefined): () => void {
	const onUpdate = (...args: unknown[]) => {
		const { doctype } = (args[0] ?? {}) as { doctype?: unknown };
		if (typeof doctype !== "string" || !doctype) return;
		dropDoctypeMeta(doctype);
		dropFormLayouts(doctype);
		dropListSettings(doctype);
	};
	socket?.on(DOCTYPE_UPDATE, onUpdate);
	return () => socket?.off(DOCTYPE_UPDATE, onUpdate);
}
