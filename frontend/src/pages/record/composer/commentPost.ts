// The comment writer's send: a pending row at once, the server's key on it after, the draft back on a failure.
import { addPendingActivity, type UserInfo } from "@framework/ui/ActivityTimeline";
import { addComment, type Comment } from "@framework/ui/api";
import { errorMessage } from "@/recordPage";
import {
	clearComposerDraft,
	closeComposer,
	composerRecordFor,
	composerState,
	openComposer,
	replaceComposerDraft,
	type ComposerWindow,
	type WriterContext,
} from "@/shell/composer";
import {
	COMMENT_WRITER,
	isBlankDraft,
	mergeDrafts,
	readCommentDraft,
	type CommentDraft,
} from "./commentDraft";

/** Collapses and clears at once; the answer names the row, and a failure puts everything back. */
export async function postComment(
	context: WriterContext,
	author: UserInfo,
	draft: CommentDraft
) {
	const { doctype, docname } = context;
	// A failed post reopens the writer where it was, floating over another page too.
	const window = composerState.window;
	clearComposerDraft(doctype, docname, COMMENT_WRITER);
	closeComposer();
	const pending = addPendingActivity(doctype, docname, pendingRow(author, draft));
	let key: string;
	try {
		key = await send(doctype, docname, draft, pending);
	} catch (error) {
		pending.drop();
		restore(context, draft, window);
		context.toast.error(errorMessage(error));
		return;
	}
	// `onPost` is the record page's, so it fires only if that page is up when the answer comes.
	if (key) await composerRecordFor(doctype, docname)?.firePost?.(key);
}

async function send(
	doctype: string,
	docname: string,
	draft: CommentDraft,
	pending: ReturnType<typeof addPendingActivity>
) {
	const attachments = draft.attachments.map((file) => file.name);
	const { data } = await addComment(doctype, docname, draft.content, {
		attachments,
	});
	// The comment was written: the feed retires the row when the echo's text matches it.
	if (!data.added) return "";
	const key = `comment:${data.added}`;
	pending.resolve(key, creationOf(data.comments, data.added));
	return key;
}

// No timestamp: the feed sorts a row without one last, as the newest.
function pendingRow(author: UserInfo, draft: CommentDraft) {
	const attachments = draft.attachments.map(({ file_url, file_name }) => ({
		file_url,
		file_name,
		is_private: 1 as const,
	}));
	return {
		type: "comment" as const,
		author,
		data: { name: "", content: draft.content, attachments },
	};
}

function creationOf(comments: Comment[], name: string) {
	return comments.find((comment) => comment.name === name)?.creation;
}

// A newer draft in the open writer keeps its text after the failed one; the writer redraws both.
function restore(context: WriterContext, failed: CommentDraft, window: ComposerWindow) {
	const { doctype, docname } = context;
	const current = readCommentDraft(doctype, docname);
	const draft = isBlankDraft(current) ? { ...failed } : mergeDrafts(failed, current);
	replaceComposerDraft(doctype, docname, COMMENT_WRITER, draft);
	reopen(doctype, docname, window);
}

// A composer the reader opened on another record since keeps the store.
function reopen(doctype: string, docname: string, window: ComposerWindow) {
	const elsewhere =
		composerState.active && (composerState.doctype !== doctype || composerState.name !== docname);
	if (!elsewhere) openComposer(doctype, docname, COMMENT_WRITER, undefined, window);
}
