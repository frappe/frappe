// `page.composer`'s host half for one record, and the page's built-in writers.
import { currentSession } from "@framework/ui/useSession";
import type { ComposerHost } from "@/recordPage";
import type { PostComment } from "@/recordPage/commentAct";
import type { WriterItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import {
	activeWriter,
	closeComposer,
	composerRecordFor,
	composerState,
	openComposer,
	preferredWindow,
	setComposerWindow,
} from "@/shell/composer";
import { COMMENT_WRITER } from "./commentDraft";
import { EMAIL_WRITER } from "./emailDraft";
import { commentAuthor, sendComment } from "./commentPost";
import { openEmail, type EmailSeedContext } from "./emailSeed";

export function composerHost(
	doctype: string,
	docname: string,
	email?: EmailSeedContext
): ComposerHost & { postComment: PostComment } {
	return {
		postComment: (html) => agentComment(doctype, docname, html),
		openWriter: (name, options) => {
			if (name === EMAIL_WRITER)
				openEmail(doctype, docname, email, options.draft, options.window);
			else openComposer(doctype, docname, name, options.draft, options.window);
		},
		closeWriter: () => {
			if (activeWriter(doctype, docname)) closeComposer();
		},
		activeWriter: () => activeWriter(doctype, docname),
		windowState: () =>
			activeWriter(doctype, docname) ? composerState.window : preferredWindow(),
		setWindow: (placement) => {
			if (activeWriter(doctype, docname)) setComposerWindow(placement);
		},
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

/** The comment goes through the record's registered writer context, the page's `onPost` among it; the person's draft stays. */
async function agentComment(doctype: string, docname: string, html: string) {
	const context = composerRecordFor(doctype, docname);
	const user = currentSession()?.user;
	if (!context || !user) throw new Error("This record is not open in the tab");
	return sendComment(context, commentAuthor(user), { content: html, attachments: [] });
}
