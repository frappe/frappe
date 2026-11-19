// What a writer knows of its record: the page's context while it is mounted, else what the store kept of it.
import { watch } from "vue";
import { toast } from "frappe-ui";
import type { UploadTransport } from "@framework/ui/FileUpload";
import type { RecordPageController } from "@/recordPage";
import type { WriterItem } from "@/recordPage/types";
import {
	composerKept,
	composerRecord,
	composerState,
	registerComposerRecord,
	type WriterContext,
} from "@/shell/composer";
import { attachTransport } from "../feed/files";
import type { RecordFeeds } from "../feed/recordFeeds";
import { composerBuiltins } from "./composerHost";
import { titleOf } from "./emailSeed";

/** The open record's context, or a detached one with no page, no `onPost` and the shell's toast. */
export function openWriterContext(): WriterContext {
	const { title, perms } = composerKept();
	return (
		composerRecord() ?? {
			doctype: composerState.doctype,
			docname: composerState.name,
			title,
			perms,
			toast,
		}
	);
}

/** The open record's writers; away from it, the plain ones its page last showed. */
export function openWriterItems(): WriterItem[] {
	const kept = composerKept();
	return composerRecord()?.writers ?? kept.writers ?? composerBuiltins(kept.perms);
}

/** A reader who may write the record attaches onto it, and the Files tab shows it while the page is live. */
export function recordUploads(context: WriterContext): UploadTransport | undefined {
	if (!context.perms.write) return undefined;
	return context.uploadTransport?.() ?? attachTransport(context, () => {});
}

/** The record page's context for its writers, registered while `controller` is its live one. */
export function useComposerRecord(
	controller: () => RecordPageController | null | undefined,
	feeds?: RecordFeeds | null
) {
	watch(
		controller,
		(live, _old, onCleanup) => {
			if (!live) return;
			const { doctype, docname } = live.page;
			onCleanup(registerComposerRecord(doctype, docname, recordContext(live, feeds)));
		},
		{ immediate: true }
	);
}

function recordContext(
	controller: RecordPageController,
	feeds?: RecordFeeds | null
): WriterContext {
	const { page } = controller;
	return {
		doctype: page.doctype,
		docname: page.docname,
		get title() {
			return titleOf(page);
		},
		get perms() {
			return page.perms ?? {};
		},
		get writers() {
			return controller.composer.visible();
		},
		page,
		toast: page.toast,
		firePost: (key) => controller.firePost(key),
		uploadTransport: feeds
			? () => feeds.uploadTransport(page.doctype, page.docname)
			: undefined,
	};
}
