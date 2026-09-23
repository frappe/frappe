// `page.composer`'s host half for one record, and the page's built-in writers.
import type { ComposerHost } from "@/recordPage";
import type { WriterItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import { activeWriter, closeComposer, openComposer } from "@/shell/composer";
import { COMMENT_WRITER } from "./commentDraft";
import { EMAIL_WRITER } from "./emailDraft";
import { openEmail, type EmailSeedContext } from "./emailSeed";

export function composerHost(
	doctype: string,
	docname: string,
	email?: EmailSeedContext
): ComposerHost {
	return {
		openWriter: (name, options) => {
			if (name === EMAIL_WRITER) openEmail(doctype, docname, email, options.draft);
			else openComposer(doctype, docname, name, options.draft);
		},
		closeWriter: () => {
			if (activeWriter(doctype, docname)) closeComposer();
		},
		activeWriter: () => activeWriter(doctype, docname),
	};
}

/** The editors are the page's own, so the items name no component; `email` needs the right. */
export function composerBuiltins(perms: Record<string, any> = {}): WriterItem[] {
	const writers: WriterItem[] = [
		{
			name: COMMENT_WRITER,
			label: __("Comment"),
			icon: "lucide-message-square",
		},
	];
	if (perms.email)
		writers.push({ name: EMAIL_WRITER, label: __("Email"), icon: "lucide-mail" });
	return writers;
}
