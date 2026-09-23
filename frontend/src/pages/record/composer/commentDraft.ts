// The comment writer's draft as the store keeps it: read back, tested for content, and merged.
import type { UploadedFile } from "@framework/ui/Composer";
import { composerDraft } from "@/shell/composer";

export const COMMENT_WRITER = "comment";

export type CommentDraft = {
	content: string;
	attachments: UploadedFile[];
};

export function readCommentDraft(doctype: string, docname: string): CommentDraft {
	const draft = composerDraft(doctype, docname, COMMENT_WRITER) ?? {};
	return {
		content: typeof draft.content === "string" ? draft.content : "",
		attachments: Array.isArray(draft.attachments) ? (draft.attachments as UploadedFile[]) : [],
	};
}

export function isBlankDraft({ content, attachments }: CommentDraft) {
	return !attachments.length && isBlankHtml(content);
}

/** The failed post's content first, then the newer draft's; a file in both is kept once. */
export function mergeDrafts(failed: CommentDraft, current: CommentDraft): CommentDraft {
	const names = new Set(failed.attachments.map((file) => file.name));
	const newer = current.attachments.filter((file) => !names.has(file.name));
	return {
		content: [failed.content, current.content].filter((html) => !isBlankHtml(html)).join(""),
		attachments: [...failed.attachments, ...newer],
	};
}

// Media alone is content, the way the editor counts it.
function isBlankHtml(html: string) {
	const body = new DOMParser().parseFromString(html, "text/html").body;
	return !body.textContent?.trim() && !body.querySelector("img, video, iframe, embed, object");
}
