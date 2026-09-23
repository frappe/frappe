// `page.composer`'s host half for one record, and the page's built-in writer.
import type { ComposerHost } from "@/recordPage";
import type { WriterItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import { activeWriter, closeComposer, openComposer } from "@/shell/composer";
import { COMMENT_WRITER } from "./commentDraft";

export function composerHost(doctype: string, docname: string): ComposerHost {
	return {
		openWriter: (name, options) => openComposer(doctype, docname, name, options.draft),
		closeWriter: () => {
			if (activeWriter(doctype, docname)) closeComposer();
		},
		activeWriter: () => activeWriter(doctype, docname),
	};
}

/** The editor is the page's own, so the item names no component. */
export function composerBuiltins(): WriterItem[] {
	return [
		{
			name: COMMENT_WRITER,
			label: __("Comment"),
			icon: "lucide-message-square",
		},
	];
}
