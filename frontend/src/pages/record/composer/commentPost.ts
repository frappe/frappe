// The comment writer's send: a pending row at once, the server's key on it after, the draft back on a failure.
import { addPendingActivity, type UserInfo } from "@framework/ui/ActivityTimeline";
import { addComment, type Comment } from "@framework/ui/api";
import type { UploadedFile } from "@framework/ui/Composer";
import { errorMessage, type RecordPageController } from "@/recordPage";
import {
	clearComposerDraft,
	closeComposer,
	composerState,
	openComposer,
	saveComposerDraft,
} from "@/shell/composer";

export const COMMENT_WRITER = "comment";

export interface CommentDraft {
	content: string;
	attachments: UploadedFile[];
}

/** Collapses and clears at once; the answer names the row, and a failure puts everything back. */
export async function postComment(
	controller: RecordPageController,
	author: UserInfo,
	draft: CommentDraft
) {
	const { doctype, docname } = controller.page;
	clearComposerDraft(doctype, docname, COMMENT_WRITER);
	closeComposer();
	const pending = addPendingActivity(doctype, docname, pendingRow(author, draft));
	let key: string;
	try {
		key = await send(doctype, docname, draft, pending);
	} catch (error) {
		pending.drop();
		restore(controller, draft);
		controller.page.toast.error(errorMessage(error));
		return;
	}
	if (key) await controller.firePost(key);
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
	if (!data.added) {
		pending.drop();
		return "";
	}
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

// A composer the reader opened on another record since keeps the store.
function restore(controller: RecordPageController, draft: CommentDraft) {
	const { doctype, docname } = controller.page;
	saveComposerDraft(doctype, docname, COMMENT_WRITER, { ...draft });
	const elsewhere =
		composerState.active && (composerState.doctype !== doctype || composerState.name !== docname);
	if (!elsewhere) openComposer(doctype, docname, COMMENT_WRITER);
}
