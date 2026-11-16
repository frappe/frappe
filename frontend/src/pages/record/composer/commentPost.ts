// The comment writer's send: a pending row at once, the server's key on it after, the draft back on a failure.
import { addPendingActivity, type UserInfo } from "@framework/ui/ActivityTimeline";
import { addComment, type Comment, type SessionUser } from "@framework/ui/api";
import { errorMessage } from "@/recordPage";
import {
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
	const placement = composerState.window;
	clearComposerDraft(doctype, docname, COMMENT_WRITER);
	closeComposer();
	let name: string;
	try {
		name = await submit(context, author, draft);
	} catch (error) {
		restore(context, draft, placement);
		context.toast.error(errorMessage(error));
		return;
	}
	await firePost(context, name);
}

/** The send alone, for a caller with no writer: the draft in the store stays. A failure throws; the comment's name resolves. */
export async function sendComment(context: WriterContext, author: UserInfo, draft: CommentDraft) {
	const name = await submit(context, author, draft);
	await firePost(context, name);
	return name;
}

// `onPost` is the record page's, so it fires only if that page is up when the answer comes.
async function firePost({ doctype, docname }: WriterContext, name: string) {
	if (name) await composerRecordFor(doctype, docname)?.firePost?.(`comment:${name}`);
}

async function submit(context: WriterContext, author: UserInfo, draft: CommentDraft) {
	const { doctype, docname } = context;
	const pending = addPendingActivity(doctype, docname, pendingRow(author, draft));
	try {
		return await send(doctype, docname, draft, pending);
	} catch (error) {
		pending.drop();
		throw error;
	}
}

/** The comment writer's author, from the session's user. */
export function commentAuthor(user: SessionUser): UserInfo {
	return {
		name: user.name,
		email: user.email,
		fullname: user.full_name,
		image: user.user_image ?? undefined,
	};
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
	pending.resolve(`comment:${data.added}`, creationOf(data.comments, data.added));
	return data.added;
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
function restore(context: WriterContext, failed: CommentDraft, placement: ComposerWindow) {
	const { doctype, docname } = context;
	keepComposerRecord(context);
	const current = readCommentDraft(doctype, docname);
	const draft = isBlankDraft(current) ? { ...failed } : mergeDrafts(failed, current);
	replaceComposerDraft(doctype, docname, COMMENT_WRITER, draft);
	reopen(doctype, docname, placement);
}

// A composer the reader opened on another record since keeps the store.
function reopen(doctype: string, docname: string, placement: ComposerWindow) {
	const elsewhere =
		composerState.active && (composerState.doctype !== doctype || composerState.name !== docname);
	if (!elsewhere) openComposer(doctype, docname, COMMENT_WRITER, undefined, placement);
}
