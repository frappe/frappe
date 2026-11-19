// The email writer's send: a pending row at once, the server's key on it after, the draft back on a failure.
import { addPendingActivity, type UserInfo } from "@framework/ui/ActivityTimeline";
import { runMethod } from "@framework/ui/api";
import { errorMessage } from "@/recordPage";
import {
	activeWriter,
	clearComposerDraft,
	closeComposer,
	composerRecordFor,
	composerState,
	keepComposerRecord,
	openComposer,
	replaceComposerDraft,
	type ComposerWindow,
	type WriterContext,
} from "@/shell/composer";
import {
	EMAIL_WRITER,
	isBlankEmailDraft,
	mergeEmailDrafts,
	readEmailDraft,
	type EmailDraft,
} from "./emailDraft";

const MAKE = "frappe.core.doctype.communication.email.make";

/** `message` goes, the body with any quote under it; a failure reopens `draft` in `placement`. */
export async function postEmail(
	context: WriterContext,
	author: UserInfo,
	draft: EmailDraft,
	message: string,
	placement: ComposerWindow
) {
	const { doctype, docname } = context;
	clearComposerDraft(doctype, docname, EMAIL_WRITER);
	// A send that waited on the senders may find the reader in another writer, here or elsewhere.
	if (activeWriter(doctype, docname) === EMAIL_WRITER) closeComposer();
	const pending = addPendingActivity(doctype, docname, pendingRow(author, draft, message));
	let key: string;
	try {
		const args = makeArgs(doctype, docname, author, draft, message);
		const { data } = await runMethod<{ name: string }>(MAKE, args);
		key = `email:${data.name}`;
	} catch (error) {
		pending.drop();
		restore(context, draft, placement);
		context.toast.error(errorMessage(error));
		return;
	}
	// `make` sends no time: the row keeps none until the feed's echo of the email retires it.
	pending.resolve(key);
	// `onPost` is the record page's, so it fires only if that page is up when the answer comes.
	await composerRecordFor(doctype, docname)?.firePost?.(key);
}

function makeArgs(
	doctype: string,
	docname: string,
	author: UserInfo,
	draft: EmailDraft,
	message: string
) {
	return {
		doctype,
		name: docname,
		content: message,
		subject: draft.subject,
		recipients: draft.to.join(", "),
		cc: draft.cc.join(", "),
		bcc: draft.bcc.join(", "),
		sender: draft.from || undefined,
		sender_full_name: author.fullname,
		send_email: 1,
		attachments: draft.attachments.map((file) => file.name),
		in_reply_to: draft.inReplyTo || undefined,
	};
}

function pendingRow(author: UserInfo, draft: EmailDraft, message: string) {
	const attachments = draft.attachments.map(({ file_url, file_name }) => ({
		file_url,
		file_name,
		is_private: 1 as const,
	}));
	return {
		type: "email" as const,
		author,
		data: {
			name: "",
			subject: draft.subject,
			sender: draft.from || author.email,
			to: draft.to.join(", "),
			cc: draft.cc.join(", "),
			bcc: draft.bcc.join(", "),
			content: message,
			attachments,
		},
	};
}

// A newer draft in the open writer keeps its text after the failed one; the writer redraws both.
function restore(context: WriterContext, failed: EmailDraft, placement: ComposerWindow) {
	const { doctype, docname } = context;
	keepComposerRecord(context);
	const current = readEmailDraft(doctype, docname);
	const draft = isBlankEmailDraft(current) ? { ...failed } : mergeEmailDrafts(failed, current);
	replaceComposerDraft(doctype, docname, EMAIL_WRITER, draft);
	reopen(doctype, docname, placement);
}

// A composer the reader opened on another record since keeps the store.
function reopen(doctype: string, docname: string, placement: ComposerWindow) {
	const elsewhere =
		composerState.active && (composerState.doctype !== doctype || composerState.name !== docname);
	if (!elsewhere) openComposer(doctype, docname, EMAIL_WRITER, undefined, placement);
}
