// What a writer knows of its record: the page's context while it is mounted, else what the store kept of it.
import { toast } from "frappe-ui";
import type { UploadTransport } from "@framework/ui/FileUpload";
import type { WriterItem } from "@/recordPage/types";
import {
	composerKept,
	composerRecord,
	composerState,
	type WriterContext,
} from "@/shell/composer";
import { attachTransport } from "../feed/files";
import { composerBuiltins } from "./composerHost";

/** The open record's context, or a detached one with no page, no `onPost` and the shell's toast. */
export function openWriterContext(): WriterContext {
	return (
		composerRecord() ?? {
			doctype: composerState.doctype,
			docname: composerState.name,
			...composerKept(),
			toast,
		}
	);
}

/** The open record's writers; away from it, only the built-ins, since a script's writer takes `page`. */
export function openWriterItems(): WriterItem[] {
	return composerRecord()?.writers ?? composerBuiltins(composerKept().perms);
}

/** A reader who may write the record attaches onto it, and the Files tab shows it while the page is live. */
export function recordUploads(context: WriterContext): UploadTransport | undefined {
	if (!context.perms.write) return undefined;
	return context.uploadTransport?.() ?? attachTransport(context, () => {});
}
